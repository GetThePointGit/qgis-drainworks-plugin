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

from drainworks_plugin.io.geopackage_store import (
    MeasurementRow,
    point_along_wkt,
    read_manholes,
    read_pipes,
    replace_measurements,
)

# Number of segments to sample a measurement-less pipe into (BOB fallback).
BOB_SAMPLES = 5


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
    return len(rows)
