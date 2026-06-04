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
