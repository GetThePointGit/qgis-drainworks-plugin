from drainworks_plugin.io.geopackage_store import (
    layer_counts,
    total_lost_volume,
    update_segments_berging,
    write_base,
    write_segments,
)

import rgs_ribx
from rgs_ribx.model.raw import RawMeasurements


def _gpkg(tmp_gpkg):
    manholes = [rgs_ribx.Manhole(code="A", geometry_wkt="POINT (0 0)"),
                rgs_ribx.Manhole(code="B", geometry_wkt="POINT (30 0)")]
    pipes = [rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="B", bob1=-2.0, bob2=-2.6,
                           diameter=0.3, length=30.0, geometry_wkt="LINESTRING (0 0, 30 0)")]
    raw = {"L1": RawMeasurements("L1", "AA", reverse=False,
                                 points=[{"dist": 0.0, "value": 0.0},
                                         {"dist": 30.0, "value": 0.0}])}
    write_base(tmp_gpkg, manholes, pipes, raw)


def test_layer_counts(tmp_gpkg):
    _gpkg(tmp_gpkg)
    c = layer_counts(tmp_gpkg)
    assert c["manholes"] == 2
    assert c["pipes"] == 1
    assert c["measurements"] == 2


def test_total_lost_volume_sums_segments(tmp_gpkg):
    _gpkg(tmp_gpkg)
    assert total_lost_volume(tmp_gpkg) == 0.0   # no segments yet
    rows = [{"pipe_code": "L1", "dist_from": 0.0, "dist_to": 30.0, "length": 30.0,
             "bob_start": -2.0, "bob_end": -2.6, "bob_highest": -2.0, "slope_avg": 0.0,
             "diameter": 0.3, "n_measurements": 2, "source": "measured",
             "geometry_wkt": "LINESTRING (0 0, 30 0)"}]
    write_segments(tmp_gpkg, rows)
    seg = __import__("drainworks_plugin.io.geopackage_store", fromlist=["read_segments"]).read_segments(tmp_gpkg)[0]
    update_segments_berging(tmp_gpkg, {seg["fid"]: {"lost_volume": 1.25, "flooded_pct": 0.3,
                                                    "flooded_pct_max": 0.4, "water_level": -2.2,
                                                    "flooded_length": 10.0}})
    assert round(total_lost_volume(tmp_gpkg), 2) == 1.25


def test_read_manhole_bottom_levels(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import read_manhole_bottom_levels
    _gpkg(tmp_gpkg)
    levels = read_manhole_bottom_levels(tmp_gpkg)
    # bottom_level = lowest connected pipe BOB; pipe L1 has bob1=-2.0, bob2=-2.6
    assert round(levels["A"], 1) == -2.0
    assert round(levels["B"], 1) == -2.6


def test_layer_counts_falls_back_to_legacy_measurements(tmp_path):
    from osgeo import ogr, osr
    from drainworks_plugin.io.geopackage_store import layer_counts
    path = tmp_path / "old.gpkg"
    ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(path))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(28992)
    ds.CreateLayer("manholes", srs, ogr.wkbPoint)
    ds.CreateLayer("pipes", srs, ogr.wkbLineString)
    meas = ds.CreateLayer("measurements", srs, ogr.wkbPoint)
    defn = meas.GetLayerDefn()
    for _ in range(3):
        meas.CreateFeature(ogr.Feature(defn))
    ds = None
    counts = layer_counts(str(path))
    assert counts["measurements"] == 3   # falls back to the legacy layer
