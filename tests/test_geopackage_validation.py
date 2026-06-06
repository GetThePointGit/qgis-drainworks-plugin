from drainworks_plugin.io.geopackage_store import set_validation, write_base

import rgs_ribx


def test_set_validation_writes_valid_and_issues(tmp_gpkg):
    manholes = [rgs_ribx.Manhole(code="A", geometry_wkt="POINT (0 0)"),
                rgs_ribx.Manhole(code="B", geometry_wkt="POINT (30 0)")]
    pipes = [
        rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="B", bob1=-2.0, bob2=-2.1,
                      diameter=0.3, length=30.0, geometry_wkt="LINESTRING (0 0, 30 0)"),
        rgs_ribx.Pipe(code="L2", manhole1="A", manhole2="Z", bob1=-2.0, bob2=None,
                      diameter=5.0, length=30.0, geometry_wkt="LINESTRING (0 0, 30 0)"),
    ]
    write_base(tmp_gpkg, manholes, pipes, raw_measurements={})

    validation = rgs_ribx.validate_network(manholes, pipes)
    set_validation(tmp_gpkg, validation)

    from osgeo import ogr
    ds = ogr.Open(str(tmp_gpkg))
    layer = ds.GetLayerByName("pipes")
    by_code = {}
    for feat in layer:
        by_code[feat.GetField("code")] = (feat.GetField("valid"), feat.GetField("issues"))
    assert by_code["L1"][0] == 1
    assert by_code["L1"][1] in (None, "")
    assert by_code["L2"][0] == 0
    assert "bob" in (by_code["L2"][1] or "").lower()
