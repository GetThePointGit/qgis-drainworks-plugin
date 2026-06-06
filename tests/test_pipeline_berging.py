from drainworks_plugin.io.geopackage_store import read_segments, write_base
from drainworks_plugin.pipeline.berging import compute_berging
from drainworks_plugin.pipeline.enrich import enrich

import rgs_ribx
from rgs_ribx.model.raw import RawMeasurements


def _setup(tmp_gpkg):
    # A dip in the middle of a flat pipe between two sinks -> water collects.
    manholes = [rgs_ribx.Manhole(code="P1", is_sink=True, geometry_wkt="POINT (0 0)"),
                rgs_ribx.Manhole(code="P2", is_sink=True, geometry_wkt="POINT (30 0)")]
    pipes = [rgs_ribx.Pipe(code="L1", manhole1="P1", manhole2="P2", bob1=-2.0, bob2=-2.0,
                           diameter=0.5, length=30.0, shape="A",
                           geometry_wkt="LINESTRING (0 0, 30 0)")]
    raw = {"L1": RawMeasurements("L1", "AA", reverse=False, points=[
        {"dist": 0.0, "value": 0.0}, {"dist": 10.0, "value": -0.3},
        {"dist": 20.0, "value": -0.3}, {"dist": 30.0, "value": 0.0}])}
    write_base(tmp_gpkg, manholes, pipes, raw)
    enrich(tmp_gpkg, correct_bob=False)
    return tmp_gpkg


def test_compute_berging_accurate_fills_segments(tmp_gpkg):
    _setup(tmp_gpkg)
    n = compute_berging(tmp_gpkg, resolution="accurate")
    segs = read_segments(tmp_gpkg)
    assert n == len(segs)
    flooded = [s for s in segs if (s.get("flooded_pct") or 0) > 0]
    assert flooded, "the dip should flood at least one segment"
    assert all((s.get("flooded_pct_max") or 0) >= (s.get("flooded_pct") or 0) for s in segs)


def test_compute_berging_fast_runs(tmp_gpkg):
    _setup(tmp_gpkg)
    n = compute_berging(tmp_gpkg, resolution="fast")
    assert n == len(read_segments(tmp_gpkg))


def test_accurate_writes_per_point_water_to_profile(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import read_profile
    _setup(tmp_gpkg)
    compute_berging(tmp_gpkg, resolution="accurate")
    pts = read_profile(tmp_gpkg)["L1"]
    assert any(p.water_level is not None for p in pts)


def test_fast_leaves_profile_water_empty(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import read_profile
    _setup(tmp_gpkg)
    compute_berging(tmp_gpkg, resolution="fast")
    pts = read_profile(tmp_gpkg)["L1"]
    assert all(p.water_level is None for p in pts)


def test_accurate_fills_water_depth_max(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import read_segments
    _setup(tmp_gpkg)
    compute_berging(tmp_gpkg, resolution="accurate")
    segs = read_segments(tmp_gpkg)
    # the dip floods -> at least one segment has a positive max water depth
    assert any((s.get("water_depth_max") or 0) > 0 for s in segs)
    # depth is never negative
    assert all((s.get("water_depth_max") or 0) >= 0 for s in segs)


def test_berging_writes_meta(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import (berging_fingerprint, read_meta,
                                                       total_lost_volume)
    _setup(tmp_gpkg)
    compute_berging(tmp_gpkg, resolution="fast")
    meta = read_meta(tmp_gpkg)
    assert meta["berging_settings"] == {"resolution": "fast"}
    assert meta["sinks"] == ["P1", "P2"]
    assert round(meta["berging_total"], 4) == round(total_lost_volume(tmp_gpkg), 4)
    assert meta["berging_fingerprint"] == berging_fingerprint(
        meta["enrich_fingerprint"], ["P1", "P2"])
