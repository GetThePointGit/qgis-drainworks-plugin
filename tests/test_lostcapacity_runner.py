import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    MeasurementRow,
    write_geopackage,
)
from drainworks_plugin.lostcapacity.runner import compute_and_store


def test_compute_and_store_writes_flooded_pct(tmp_gpkg):
    manholes = [
        rgs_ribx.Manhole(code="P1", is_sink=True),
        rgs_ribx.Manhole(code="P2", is_sink=True),
    ]
    pipes = [
        rgs_ribx.Pipe(code="L1", manhole1="P1", manhole2="P2",
                      bob1=-2.0, bob2=-2.0, diameter=0.3, shape="A", length=30.0),
    ]
    measurements = [MeasurementRow(pipe_code="L1", dist=15.0, bob=-2.3, obb=-2.0)]
    write_geopackage(tmp_gpkg, manholes, pipes, measurements)

    n = compute_and_store(tmp_gpkg)
    assert n == 1

    from osgeo import ogr

    ds = ogr.Open(str(tmp_gpkg))
    feat = ds.GetLayerByName("measurements").GetNextFeature()
    assert feat.GetField("water_level") is not None
    assert feat.GetField("flooded_pct") > 0


def test_compute_and_store_bob_fallback_without_measurements(tmp_gpkg):
    # No measurements at all: a valley at P2 (lower than the P1 sink and P3) must
    # still produce flooded points from the BOB line, with map geometry.
    manholes = [
        rgs_ribx.Manhole(code="P1", geometry_wkt="POINT (0 0)", is_sink=True),
        rgs_ribx.Manhole(code="P2", geometry_wkt="POINT (30 0)"),
        rgs_ribx.Manhole(code="P3", geometry_wkt="POINT (60 0)"),
    ]
    pipes = [
        rgs_ribx.Pipe(code="L1", manhole1="P1", manhole2="P2", bob1=-2.0, bob2=-2.5,
                      diameter=0.3, shape="A", length=30.0, geometry_wkt="LINESTRING (0 0, 30 0)"),
        rgs_ribx.Pipe(code="L2", manhole1="P2", manhole2="P3", bob1=-2.5, bob2=-2.0,
                      diameter=0.3, shape="A", length=30.0, geometry_wkt="LINESTRING (30 0, 60 0)"),
    ]
    write_geopackage(tmp_gpkg, manholes, pipes, measurements=[])  # nothing measured

    n = compute_and_store(tmp_gpkg)
    assert n > 0  # BOB fallback synthesized points

    from osgeo import ogr

    ds = ogr.Open(str(tmp_gpkg))
    layer = ds.GetLayerByName("measurements")
    flooded = [feat.GetField("flooded_pct") for feat in layer]
    assert any((v or 0) > 0 for v in flooded)  # the valley at P2 holds water
    layer.ResetReading()
    assert layer.GetNextFeature().GetGeometryRef() is not None  # points have geometry
