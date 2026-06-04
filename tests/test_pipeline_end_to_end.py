from drainworks_plugin.io.geopackage_store import read_segments, write_base
from drainworks_plugin.pipeline.berging import compute_berging
from drainworks_plugin.pipeline.enrich import enrich

import rgs_ribx
from rgs_ribx.model.raw import RawMeasurements


def _write(tmp_gpkg):
    manholes = [rgs_ribx.Manhole(code="P1", is_sink=True, geometry_wkt="POINT (0 0)"),
                rgs_ribx.Manhole(code="P2", is_sink=True, geometry_wkt="POINT (30 0)")]
    pipes = [rgs_ribx.Pipe(code="L1", manhole1="P1", manhole2="P2", bob1=-2.0, bob2=-2.0,
                           diameter=0.5, length=30.0, shape="A",
                           geometry_wkt="LINESTRING (0 0, 30 0)")]
    raw = {"L1": RawMeasurements("L1", "AA", reverse=False, points=[
        {"dist": 0.0, "value": 0.0}, {"dist": 10.0, "value": -0.3},
        {"dist": 20.0, "value": -0.3}, {"dist": 30.0, "value": 0.0}])}
    write_base(tmp_gpkg, manholes, pipes, raw)


def test_full_pipeline_then_reenrich_clears_berging(tmp_gpkg):
    _write(tmp_gpkg)
    enrich(tmp_gpkg, correct_bob=False)
    compute_berging(tmp_gpkg, resolution="accurate")
    assert any((s.get("flooded_pct") or 0) > 0 for s in read_segments(tmp_gpkg))

    # Re-running step 2 must wipe step-3 results (segments recreated empty).
    enrich(tmp_gpkg, correct_bob=False)
    assert all((s.get("flooded_pct") in (None, 0, 0.0)) for s in read_segments(tmp_gpkg))
