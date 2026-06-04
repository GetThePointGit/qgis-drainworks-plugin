"""Step 3 — lost storage (verloren berging) on segments.

Flood-fills a per-pipe profile and aggregates the result onto each pre-built
segment. ``resolution='accurate'`` (default) floods the detailed ``profile``
points; ``'fast'`` floods the coarse segment endpoints.
"""

import math

import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    read_manholes,
    read_pipes,
    read_profile,
    read_segments,
    update_segments_berging,
)


def _area(point):
    """Flooded cross-section area (m²) at a flood-filled MeasurementPoint."""
    pct = point.flooded_pct
    if not pct:
        return 0.0
    diameter = point.obb - point.bob
    return pct * math.pi * (diameter / 2.0) ** 2


def _endpoint_profile(pipe, seg_rows):
    """Build a coarse profile from a pipe's segment endpoints (sorted)."""
    rows = sorted(seg_rows, key=lambda s: s["dist_from"])
    diam = pipe.diameter or 0.0
    pts = [rgs_ribx.MeasurementPoint(dist=s["dist_from"], bob=s["bob_start"],
                                     obb=s["bob_start"] + diam) for s in rows]
    last = rows[-1]
    pts.append(rgs_ribx.MeasurementPoint(dist=last["dist_to"], bob=last["bob_end"],
                                         obb=last["bob_end"] + diam))
    return pts


def _aggregate(points):
    """Length-weighted berging aggregates over consecutive flood-filled points."""
    pts = sorted(points, key=lambda p: p.dist)
    total = flooded_len = vol = pct_w = water_w = water_len = pct_max = 0.0
    for a, b in zip(pts, pts[1:]):
        length = b.dist - a.dist
        if length <= 0:
            continue
        pa = a.flooded_pct or 0.0
        pb = b.flooded_pct or 0.0
        total += length
        pct_w += 0.5 * (pa + pb) * length
        pct_max = max(pct_max, pa, pb)
        vol += 0.5 * (_area(a) + _area(b)) * length
        if max(pa, pb) > 0:
            flooded_len += length
        waters = [w for w in (a.water_level, b.water_level) if w is not None]
        if waters:
            water_w += (sum(waters) / len(waters)) * length
            water_len += length
    return {
        "flooded_pct": (pct_w / total) if total else 0.0,
        "flooded_pct_max": pct_max,
        "lost_volume": vol,
        "flooded_length": flooded_len,
        "water_level": (water_w / water_len) if water_len else None,
    }


def compute_berging(gpkg_path, resolution="accurate") -> int:
    """Flood-fill + fill segment berging fields. Returns the segment count."""
    manholes = {m.code: m for m in read_manholes(gpkg_path)}
    pipes = {p.code: p for p in read_pipes(gpkg_path)}
    segments = read_segments(gpkg_path)
    profile_pts = read_profile(gpkg_path)

    segs_by_pipe = {}
    for seg in segments:
        segs_by_pipe.setdefault(seg["pipe_code"], []).append(seg)

    profiles = {}
    for code, pipe in pipes.items():
        if resolution == "accurate" and profile_pts.get(code):
            profiles[code] = profile_pts[code]
        elif segs_by_pipe.get(code):
            profiles[code] = _endpoint_profile(pipe, segs_by_pipe[code])
    rgs_ribx.compute_lost_capacity(manholes, pipes, profiles)

    updates = {}
    for seg in segments:
        pts = profiles.get(seg["pipe_code"], [])
        d0, d1 = seg["dist_from"], seg["dist_to"]
        window = [p for p in pts if d0 - 1e-6 <= p.dist <= d1 + 1e-6]
        if len(window) < 2:
            window = pts
        updates[seg["fid"]] = _aggregate(window)
    update_segments_berging(gpkg_path, updates)
    return len(segments)
