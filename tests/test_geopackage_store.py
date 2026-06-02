import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    MeasurementRow,
    read_pipes,
    write_geopackage,
)


def _build(fixtures_dir):
    return rgs_ribx.build_from_ribx(fixtures_dir / "minimal.ribx")


def test_write_creates_three_layers(fixtures_dir, tmp_gpkg):
    result = _build(fixtures_dir)
    write_geopackage(tmp_gpkg, result.manholes, result.pipes, measurements=[])

    from osgeo import ogr

    ds = ogr.Open(str(tmp_gpkg))
    names = {ds.GetLayer(i).GetName() for i in range(ds.GetLayerCount())}
    assert {"manholes", "pipes", "measurements"} <= names


def test_pipe_roundtrip_preserves_attributes(fixtures_dir, tmp_gpkg):
    result = _build(fixtures_dir)
    write_geopackage(tmp_gpkg, result.manholes, result.pipes, measurements=[])

    pipes = {p.code: p for p in read_pipes(tmp_gpkg)}
    assert "L001" in pipes
    pipe = pipes["L001"]
    assert pipe.manhole1 == "P001"
    assert pipe.bob1 == -2.5
    assert pipe.diameter == 0.3
    assert pipe.geometry_wkt.startswith("LINESTRING")


def test_measurements_written_and_typed(fixtures_dir, tmp_gpkg):
    result = _build(fixtures_dir)
    rows = [MeasurementRow(pipe_code="L001", dist=15.0, bob=-2.3, obb=-2.0,
                           water_level=-2.0, flooded_pct=0.5)]
    write_geopackage(tmp_gpkg, result.manholes, result.pipes, measurements=rows)

    from osgeo import ogr

    ds = ogr.Open(str(tmp_gpkg))
    layer = ds.GetLayerByName("measurements")
    assert layer.GetFeatureCount() == 1
    feat = layer.GetNextFeature()
    assert feat.GetField("pipe_code") == "L001"
    assert feat.GetField("flooded_pct") == 0.5
