"""Schema-version stamping + base-GeoPackage validation (issue: old gpkg crashes)."""

from drainworks_plugin.io.geopackage_store import (
    SCHEMA_VERSION,
    check_base_schema,
    read_schema_version,
    write_base,
    write_meta,
)

import rgs_ribx


def _write(tmp_gpkg, fixtures_dir):
    res = rgs_ribx.build_from_ribx(fixtures_dir / "inclined.ribx")
    write_base(tmp_gpkg, res.manholes, res.pipes, res.raw_measurements)


def test_write_base_stamps_schema_version(fixtures_dir, tmp_gpkg):
    _write(tmp_gpkg, fixtures_dir)
    assert read_schema_version(tmp_gpkg) == SCHEMA_VERSION


def test_check_base_schema_accepts_fresh_gpkg(fixtures_dir, tmp_gpkg):
    _write(tmp_gpkg, fixtures_dir)
    assert check_base_schema(tmp_gpkg) is None


def test_check_base_schema_rejects_foreign_gpkg(tmp_path):
    # A GeoPackage with an unrelated layer (no manholes/pipes) -> clear message.
    from osgeo import ogr, osr

    path = tmp_path / "foreign.gpkg"
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(28992)
    ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(path))
    ds.CreateLayer("something_else", srs, ogr.wkbPoint)
    ds = None

    problem = check_base_schema(path)
    assert problem is not None
    assert "Drainworks" in problem


def test_check_base_schema_rejects_missing_fields(tmp_path):
    # manholes/pipes present but pipes lacks the required Drainworks fields.
    from osgeo import ogr, osr

    path = tmp_path / "oldschema.gpkg"
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(28992)
    ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(path))
    ds.CreateLayer("manholes", srs, ogr.wkbPoint)
    pipes = ds.CreateLayer("pipes", srs, ogr.wkbLineString)
    pipes.CreateField(ogr.FieldDefn("id", ogr.OFTString))  # not the Drainworks schema
    ds = None

    problem = check_base_schema(path)
    assert problem is not None
    assert "velden" in problem  # mentions missing fields


def test_check_base_schema_rejects_other_version(fixtures_dir, tmp_gpkg):
    _write(tmp_gpkg, fixtures_dir)
    write_meta(tmp_gpkg, {"schema_version": SCHEMA_VERSION + 99})
    problem = check_base_schema(tmp_gpkg)
    assert problem is not None
    assert str(SCHEMA_VERSION) in problem
