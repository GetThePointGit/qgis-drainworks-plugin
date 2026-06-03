"""Write/read the sewer GeoPackage. Pure OGR (no QGIS) so it is testable.

Layers (EPSG:28992): manholes (Point), pipes (LineString), measurements (Point,
empty geometry — used as an attribute table for lost-capacity results).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from osgeo import ogr, osr

import rgs_ribx

RD_EPSG = 28992


@dataclass
class MeasurementRow:
    """A row for the ``measurements`` layer (lost-capacity output)."""

    pipe_code: str
    dist: float
    bob: float
    obb: float
    water_level: Optional[float] = None
    flooded_pct: Optional[float] = None


def _srs() -> "osr.SpatialReference":
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(RD_EPSG)
    return srs


def _set(feature, name, value) -> None:
    """Set a field, leaving it NULL when value is None."""
    if value is None:
        feature.SetFieldNull(name)
    else:
        feature.SetField(name, value)


def write_geopackage(path, manholes, pipes, measurements) -> Path:
    """Create (overwrite) a GeoPackage with manholes, pipes, measurements."""
    path = Path(path)
    if path.exists():
        path.unlink()

    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(str(path))
    srs = _srs()

    _write_manholes(ds, srs, manholes)
    _write_pipes(ds, srs, pipes)
    _write_measurements(ds, srs, measurements)

    ds = None  # flush + close
    return path


def _write_manholes(ds, srs, manholes) -> None:
    layer = ds.CreateLayer("manholes", srs, ogr.wkbPoint)
    layer.CreateField(ogr.FieldDefn("code", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("node_type", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("ground_level", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("is_sink", ogr.OFTInteger))
    defn = layer.GetLayerDefn()
    for m in manholes:
        feat = ogr.Feature(defn)
        _set(feat, "code", m.code)
        _set(feat, "node_type", m.node_type)
        _set(feat, "ground_level", m.ground_level)
        feat.SetField("is_sink", 1 if m.is_sink else 0)
        if m.geometry_wkt:
            feat.SetGeometry(ogr.CreateGeometryFromWkt(m.geometry_wkt))
        layer.CreateFeature(feat)
        feat = None


def _write_pipes(ds, srs, pipes) -> None:
    layer = ds.CreateLayer("pipes", srs, ogr.wkbLineString)
    str_fields = ["code", "manhole1", "manhole2", "shape", "material",
                  "sewerage_type", "inspection_date"]
    real_fields = ["diameter", "width", "bob1", "bob2", "length"]
    for name in str_fields:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTString))
    for name in real_fields:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
    defn = layer.GetLayerDefn()
    for p in pipes:
        feat = ogr.Feature(defn)
        _set(feat, "code", p.code)
        _set(feat, "manhole1", p.manhole1)
        _set(feat, "manhole2", p.manhole2)
        _set(feat, "shape", p.shape)
        _set(feat, "material", p.material)
        _set(feat, "sewerage_type", p.sewerage_type)
        _set(feat, "inspection_date", p.inspection_date.isoformat() if p.inspection_date else None)
        _set(feat, "diameter", p.diameter)
        _set(feat, "width", p.width)
        _set(feat, "bob1", p.bob1)
        _set(feat, "bob2", p.bob2)
        _set(feat, "length", p.length)
        if p.geometry_wkt:
            feat.SetGeometry(ogr.CreateGeometryFromWkt(p.geometry_wkt))
        layer.CreateFeature(feat)
        feat = None


def _write_measurements(ds, srs, measurements) -> None:
    layer = ds.CreateLayer("measurements", srs, ogr.wkbPoint)
    layer.CreateField(ogr.FieldDefn("pipe_code", ogr.OFTString))
    for name in ["dist", "bob", "obb", "water_level", "flooded_pct"]:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
    defn = layer.GetLayerDefn()
    for row in measurements:
        feat = ogr.Feature(defn)
        _set(feat, "pipe_code", row.pipe_code)
        _set(feat, "dist", row.dist)
        _set(feat, "bob", row.bob)
        _set(feat, "obb", row.obb)
        _set(feat, "water_level", row.water_level)
        _set(feat, "flooded_pct", row.flooded_pct)
        layer.CreateFeature(feat)
        feat = None


def read_pipes(path) -> list:
    """Read the ``pipes`` layer back into rgs_ribx.Pipe entities."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("pipes")
    pipes = []
    for feat in layer:
        geom = feat.GetGeometryRef()
        date_str = feat.GetField("inspection_date")
        inspection_date = None
        if date_str:
            from datetime import date

            inspection_date = date.fromisoformat(date_str)
        # Fall back to the geometry length when the stored length is missing or
        # zero, so routing/profile distances are always available.
        length = feat.GetField("length")
        if (not length) and geom is not None:
            length = geom.Length()
        pipes.append(
            rgs_ribx.Pipe(
                code=feat.GetField("code"),
                manhole1=feat.GetField("manhole1"),
                manhole2=feat.GetField("manhole2"),
                geometry_wkt=geom.ExportToWkt() if geom else None,
                shape=feat.GetField("shape") or "A",
                diameter=feat.GetField("diameter"),
                width=feat.GetField("width"),
                bob1=feat.GetField("bob1"),
                bob2=feat.GetField("bob2"),
                length=length,
                material=feat.GetField("material"),
                sewerage_type=feat.GetField("sewerage_type"),
                inspection_date=inspection_date,
            )
        )
    return pipes


def read_manholes(path) -> list:
    """Read the ``manholes`` layer back into rgs_ribx.Manhole entities."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("manholes")
    manholes = []
    for feat in layer:
        geom = feat.GetGeometryRef()
        manholes.append(
            rgs_ribx.Manhole(
                code=feat.GetField("code"),
                geometry_wkt=geom.ExportToWkt() if geom else None,
                node_type=feat.GetField("node_type"),
                ground_level=feat.GetField("ground_level"),
                is_sink=bool(feat.GetField("is_sink")),
            )
        )
    return manholes
