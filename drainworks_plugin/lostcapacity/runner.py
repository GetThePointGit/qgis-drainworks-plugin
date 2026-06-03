"""Compute lost capacity from a GeoPackage and write the results back.

For every pipe we build a longitudinal profile of measurement points:
- if the pipe has measured points (inclination/doorzakking), use those;
- otherwise fall back to the pipe's BOB line, sampled at a few points.

The flood-fill then assigns a water level + flooded fraction to each point, and
the whole ``measurements`` layer is rebuilt (with a map point per sample,
interpolated along the pipe) so the result is always visible — independent of
the chosen sink.
"""

from collections import defaultdict

from osgeo import ogr

import rgs_ribx

import math

from drainworks_plugin.io.geopackage_store import (
    MeasurementRow,
    linestring_substring_wkt,
    point_along_wkt,
    read_manholes,
    read_pipes,
    replace_measurements,
    write_berging_lines,
)

# Number of segments to sample a measurement-less pipe into (BOB fallback).
BOB_SAMPLES = 5
# Minimum length (m) of an aggregated berging line segment.
MIN_SEGMENT = 0.5


def _read_measurement_profiles(gpkg_path) -> dict:
    """Read measured points per pipe into MeasurementPoint objects."""
    ds = ogr.Open(str(gpkg_path))
    layer = ds.GetLayerByName("measurements")
    profiles = defaultdict(list)
    if layer is None:
        return profiles
    for feat in layer:
        profiles[feat.GetField("pipe_code")].append(
            rgs_ribx.MeasurementPoint(
                dist=feat.GetField("dist"),
                bob=feat.GetField("bob"),
                obb=feat.GetField("obb"),
            )
        )
    return profiles


def _bob_profile(pipe):
    """Synthesize a profile along a pipe's straight BOB line (no measurements)."""
    if pipe.bob1 is None or pipe.bob2 is None:
        return []
    length = pipe.length or 0.0
    diam = pipe.diameter or 0.0
    points = []
    for i in range(BOB_SAMPLES + 1):
        frac = i / BOB_SAMPLES
        dist = length * frac
        bob = pipe.bob1 + (pipe.bob2 - pipe.bob1) * frac
        points.append(rgs_ribx.MeasurementPoint(dist=dist, bob=bob, obb=bob + diam))
    return points


def compute_and_store(gpkg_path, correct_bob=False) -> int:
    """Run lost-capacity and rebuild the ``measurements`` layer. Returns point count.

    When ``correct_bob`` is True, measured profiles are de-trended onto the
    pipe's known BOBs (removes inclination-measurement drift) before computing.
    The BOB fallback is already the ideal line, so it is never corrected.
    """
    manholes = {m.code: m for m in read_manholes(gpkg_path)}
    pipes = {p.code: p for p in read_pipes(gpkg_path)}
    measured = _read_measurement_profiles(gpkg_path)

    # Build a profile for every pipe: measured points if present, else BOB line.
    profiles = {}
    for code, pipe in pipes.items():
        if measured.get(code):
            points = measured[code]
            if correct_bob and pipe.bob1 is not None and pipe.bob2 is not None:
                rgs_ribx.correct_profile_to_bobs(points, pipe.bob1, pipe.bob2, pipe.length)
            profiles[code] = points
        else:
            bob_points = _bob_profile(pipe)
            if bob_points:
                profiles[code] = bob_points

    rgs_ribx.compute_lost_capacity(manholes, pipes, profiles)

    rows = []
    for code, points in profiles.items():
        pipe = pipes[code]
        for mp in points:
            rows.append(
                MeasurementRow(
                    pipe_code=code,
                    dist=mp.dist,
                    bob=mp.bob,
                    obb=mp.obb,
                    water_level=mp.water_level,
                    flooded_pct=(float(mp.flooded_pct) if mp.flooded_pct is not None else None),
                    geometry_wkt=point_along_wkt(pipe.geometry_wkt, mp.dist),
                )
            )
    replace_measurements(gpkg_path, rows)

    # Aggregated line layer for the map (≥ MIN_SEGMENT, merged by flood class).
    line_rows = []
    for code, points in profiles.items():
        pipe = pipes[code]
        line_rows.extend(_aggregate_berging_lines(code, points, pipe.geometry_wkt))
    write_berging_lines(gpkg_path, line_rows)
    return len(rows)


def _flood_class(pct):
    """Bucket a flooded fraction: 0 = dry, 1..4 = 0-25/25-50/50-75/75-100%."""
    if not pct or pct < 0.01:
        return 0
    return min(int(pct * 4) + 1, 4)


def _flooded_area(point):
    """Flooded cross-section area (m²) at a measurement point (circular pipe)."""
    pct = point.get("flooded_pct") if isinstance(point, dict) else point.flooded_pct
    if not pct:
        return 0.0
    diameter = (point["obb"] - point["bob"]) if isinstance(point, dict) else (point.obb - point.bob)
    return pct * math.pi * (diameter / 2.0) ** 2


def _aggregate_berging_lines(code, points, pipe_wkt, min_length=MIN_SEGMENT):
    """Aggregate measurement points into ≥min_length line segments per flood class."""
    pts = sorted(points, key=lambda p: p.dist)
    if len(pts) < 2 or not pipe_wkt:
        return []

    # Inter-point segments with class + length-weighted aggregates.
    runs = []
    for a, b in zip(pts, pts[1:]):
        length = b.dist - a.dist
        if length <= 0:
            continue
        pa = a.flooded_pct or 0.0
        pb = b.flooded_pct or 0.0
        cls = _flood_class(max(pa, pb))
        area = 0.5 * (_flooded_area(a) + _flooded_area(b))
        waters = [w for w in (a.water_level, b.water_level) if w is not None]
        seg = {
            "d0": a.dist, "d1": b.dist, "len": length, "cls": cls,
            "pct_w": 0.5 * (pa + pb) * length, "vol": area * length,
            "water_w": (sum(waters) / len(waters) * length) if waters else 0.0,
            "water_len": length if waters else 0.0,
        }
        if runs and runs[-1]["cls"] == cls:
            _merge(runs[-1], seg)
        else:
            runs.append(seg)

    # Merge runs shorter than min_length into the previous run.
    merged = []
    for run in runs:
        if merged and run["len"] < min_length:
            _merge(merged[-1], run)
        else:
            merged.append(run)

    out = []
    for run in merged:
        geom = linestring_substring_wkt(pipe_wkt, run["d0"], run["d1"])
        if geom is None:
            continue
        out.append({
            "pipe_code": code,
            "dist_start": run["d0"],
            "dist_end": run["d1"],
            "length": run["len"],
            "flooded_pct": (run["pct_w"] / run["len"]) if run["len"] else 0.0,
            "water_level": (run["water_w"] / run["water_len"]) if run["water_len"] else None,
            "lost_volume": run["vol"],
            "geometry_wkt": geom,
        })
    return out


def _merge(run, seg):
    run["d1"] = seg["d1"]
    run["len"] += seg["len"]
    run["pct_w"] += seg["pct_w"]
    run["vol"] += seg["vol"]
    run["water_w"] += seg["water_w"]
    run["water_len"] += seg["water_len"]
