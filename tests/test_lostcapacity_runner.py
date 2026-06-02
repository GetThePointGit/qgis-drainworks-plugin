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
