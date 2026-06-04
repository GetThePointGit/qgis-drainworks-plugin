# Import the plugin package first: drainworks_plugin/__init__ purges and reloads
# rgs_ribx from sys.modules (for QGIS Plugin Reloader). Capturing rgs_ribx class
# references before that purge would leave them pointing at a stale class object,
# breaking the isinstance check below. Importing the plugin first makes the reload
# happen up front, so the rgs_ribx symbols we import afterwards are the live ones.
from drainworks_plugin.io.geopackage_store import read_raw_measurements, write_base

import rgs_ribx
from rgs_ribx.model.raw import RawMeasurements


def _base(fixtures_dir):
    res = rgs_ribx.build_from_ribx(fixtures_dir / "inclined.ribx")
    return res


def test_write_base_creates_layers_with_raw(fixtures_dir, tmp_gpkg):
    res = _base(fixtures_dir)
    write_base(tmp_gpkg, res.manholes, res.pipes, res.raw_measurements)

    from osgeo import ogr
    ds = ogr.Open(str(tmp_gpkg))
    names = {ds.GetLayer(i).GetName() for i in range(ds.GetLayerCount())}
    assert {"manholes", "pipes", "measurements_raw"} <= names
    pipes_layer = ds.GetLayerByName("pipes")
    field_names = {pipes_layer.GetLayerDefn().GetFieldDefn(i).GetName()
                   for i in range(pipes_layer.GetLayerDefn().GetFieldCount())}
    assert {"valid", "issues"} <= field_names


def test_read_raw_measurements_roundtrip(fixtures_dir, tmp_gpkg):
    res = _base(fixtures_dir)
    write_base(tmp_gpkg, res.manholes, res.pipes, res.raw_measurements)

    raw = read_raw_measurements(tmp_gpkg)
    assert "L001" in raw
    assert isinstance(raw["L001"], RawMeasurements)
    assert raw["L001"].measurement_type == "J"
    assert raw["L001"].reverse is False
    dists = sorted(p["dist"] for p in raw["L001"].points)
    assert dists == [0.0, 15.0, 30.0]
