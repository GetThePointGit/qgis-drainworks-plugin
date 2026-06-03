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
    """A row for the ``measurements`` layer (lost-capacity output).

    ``geometry_wkt`` is the point on the map (interpolated along the pipe at
    ``dist``); when set, the row renders on the canvas.
    """

    pipe_code: str
    dist: float
    bob: float
    obb: float
    water_level: Optional[float] = None
    flooded_pct: Optional[float] = None
    geometry_wkt: Optional[str] = None


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


def point_along_wkt(line_wkt, dist):
    """Return the WKT POINT at ``dist`` metres along a WKT LINESTRING, or None."""
    if not line_wkt or "LINESTRING" not in line_wkt.upper():
        return None
    try:
        inside = line_wkt[line_wkt.index("(") + 1: line_wkt.rindex(")")]
    except ValueError:
        return None
    pts = []
    for part in inside.split(","):
        xy = part.split()
        if len(xy) >= 2:
            pts.append((float(xy[0]), float(xy[1])))
    if len(pts) < 2:
        return None
    remaining = max(0.0, dist)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        seg = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if seg == 0:
            continue
        if remaining <= seg:
            t = remaining / seg
            return f"POINT ({x1 + (x2 - x1) * t:.3f} {y1 + (y2 - y1) * t:.3f})"
        remaining -= seg
    x, y = pts[-1]
    return f"POINT ({x:.3f} {y:.3f})"


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
        _fill_measurement_feature(ogr.Feature(defn), row, layer)


def _fill_measurement_feature(feat, row, layer) -> None:
    """Populate and create a measurement feature (with geometry if present)."""
    _set(feat, "pipe_code", row.pipe_code)
    _set(feat, "dist", row.dist)
    _set(feat, "bob", row.bob)
    _set(feat, "obb", row.obb)
    _set(feat, "water_level", row.water_level)
    _set(feat, "flooded_pct", row.flooded_pct)
    if getattr(row, "geometry_wkt", None):
        feat.SetGeometry(ogr.CreateGeometryFromWkt(row.geometry_wkt))
    layer.CreateFeature(feat)


def replace_measurements(path, rows) -> int:
    """Replace every feature in the ``measurements`` layer with ``rows``.

    Returns the number of rows written. Used by the lost-capacity runner, which
    rebuilds the whole layer (real + BOB-derived points) on every run.
    """
    ds = ogr.Open(str(path), update=1)
    layer = ds.GetLayerByName("measurements")
    if layer is None:
        ds = None
        return 0
    layer.ResetReading()
    for fid in [feat.GetFID() for feat in layer]:
        layer.DeleteFeature(fid)
    defn = layer.GetLayerDefn()
    for row in rows:
        _fill_measurement_feature(ogr.Feature(defn), row, layer)
    ds = None
    return len(rows)


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


def set_sinks(path, sink_codes) -> int:
    """Set ``is_sink=1`` for manholes whose code is in ``sink_codes``, else 0.

    Returns the number of manholes flagged as sink.
    """
    wanted = set(sink_codes or [])
    ds = ogr.Open(str(path), update=1)
    layer = ds.GetLayerByName("manholes")
    flagged = 0
    layer.ResetReading()
    for feat in layer:
        is_sink = 1 if feat.GetField("code") in wanted else 0
        feat.SetField("is_sink", is_sink)
        layer.SetFeature(feat)
        flagged += is_sink
    ds = None
    return flagged


def read_measurements(path) -> dict:
    """Return {pipe_code: [dict(dist, bob, obb, water_level, flooded_pct)]}.

    Sorted by distance per pipe. Used to draw the measured profile + water level
    in the side-view and to total the lost storage along a trajectory.
    """
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("measurements")
    grouped = {}
    if layer is None:
        return grouped
    for feat in layer:
        grouped.setdefault(feat.GetField("pipe_code"), []).append(
            {
                "dist": feat.GetField("dist"),
                "bob": feat.GetField("bob"),
                "obb": feat.GetField("obb"),
                "water_level": (None if feat.IsFieldNull("water_level")
                                else feat.GetField("water_level")),
                "flooded_pct": (None if feat.IsFieldNull("flooded_pct")
                                else feat.GetField("flooded_pct")),
            }
        )
    for points in grouped.values():
        points.sort(key=lambda m: m["dist"])
    return grouped


def read_manhole_points(path):
    """Return {code: (x, y)} for all manholes with a point geometry."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("manholes")
    points = {}
    for feat in layer:
        geom = feat.GetGeometryRef()
        if geom is not None:
            points[feat.GetField("code")] = (geom.GetX(), geom.GetY())
    return points
