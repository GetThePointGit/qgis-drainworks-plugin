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


def _parse_linestring_wkt(line_wkt):
    """Return [(x, y), ...] vertices of a WKT LINESTRING, or [] if not parseable."""
    if not line_wkt or "LINESTRING" not in line_wkt.upper():
        return []
    try:
        inside = line_wkt[line_wkt.index("(") + 1: line_wkt.rindex(")")]
    except ValueError:
        return []
    pts = []
    for part in inside.split(","):
        xy = part.split()
        if len(xy) >= 2:
            pts.append((float(xy[0]), float(xy[1])))
    return pts


def _cumulative(pts):
    cum = [0.0]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        cum.append(cum[-1] + ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
    return cum


def _interpolate(pts, cum, dist):
    dist = min(max(dist, 0.0), cum[-1])
    for i in range(len(pts) - 1):
        if cum[i] <= dist <= cum[i + 1]:
            seg = cum[i + 1] - cum[i]
            t = 0.0 if seg == 0 else (dist - cum[i]) / seg
            return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t,
                    pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)
    return pts[-1]


def point_along_wkt(line_wkt, dist):
    """Return the WKT POINT at ``dist`` metres along a WKT LINESTRING, or None."""
    pts = _parse_linestring_wkt(line_wkt)
    if len(pts) < 2:
        return None
    x, y = _interpolate(pts, _cumulative(pts), dist)
    return f"POINT ({x:.3f} {y:.3f})"


def linestring_substring_wkt(line_wkt, d0, d1):
    """Return the WKT LINESTRING of the part of ``line_wkt`` between d0 and d1."""
    pts = _parse_linestring_wkt(line_wkt)
    if len(pts) < 2 or d1 <= d0:
        return None
    cum = _cumulative(pts)
    d0 = min(max(d0, 0.0), cum[-1])
    d1 = min(max(d1, 0.0), cum[-1])
    out = [_interpolate(pts, cum, d0)]
    for i, c in enumerate(cum):
        if d0 < c < d1:
            out.append(pts[i])
    out.append(_interpolate(pts, cum, d1))
    if len(out) < 2:
        return None
    return "LINESTRING (" + ", ".join(f"{x:.3f} {y:.3f}" for x, y in out) + ")"


def write_geopackage(path, manholes, pipes, measurements) -> Path:
    """Create (overwrite) a GeoPackage with manholes, pipes, measurements."""
    path = Path(path)
    if path.exists():
        path.unlink()

    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(str(path))
    srs = _srs()

    # One transaction around all inserts — without it, every feature is its own
    # SQLite commit (hundreds of thousands of measurement points take minutes).
    bottom_levels = _manhole_bottom_levels(pipes)
    ds.StartTransaction()
    _write_manholes(ds, srs, manholes, bottom_levels)
    _write_pipes(ds, srs, pipes)
    _write_measurements(ds, srs, measurements)
    ds.CommitTransaction()

    ds = None  # flush + close
    return path


def _manhole_bottom_levels(pipes) -> dict:
    """{manhole_code: lowest connected pipe BOB} — the put's bottom (bodemhoogte)."""
    levels = {}
    for p in pipes:
        for code, bob in ((p.manhole1, p.bob1), (p.manhole2, p.bob2)):
            if code and bob is not None:
                levels[code] = bob if code not in levels else min(levels[code], bob)
    return levels


def _write_manholes(ds, srs, manholes, bottom_levels=None) -> None:
    bottom_levels = bottom_levels or {}
    layer = ds.CreateLayer("manholes", srs, ogr.wkbPoint)
    layer.CreateField(ogr.FieldDefn("code", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("node_type", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("ground_level", ogr.OFTReal))   # maaiveld / putdeksel
    layer.CreateField(ogr.FieldDefn("bottom_level", ogr.OFTReal))   # bodemhoogte (laagste bob)
    layer.CreateField(ogr.FieldDefn("is_sink", ogr.OFTInteger))
    layer.CreateField(ogr.FieldDefn("valid", ogr.OFTInteger))
    layer.CreateField(ogr.FieldDefn("issues", ogr.OFTString))
    defn = layer.GetLayerDefn()
    for m in manholes:
        feat = ogr.Feature(defn)
        _set(feat, "code", m.code)
        _set(feat, "node_type", m.node_type)
        _set(feat, "ground_level", m.ground_level)
        _set(feat, "bottom_level", bottom_levels.get(m.code))
        feat.SetField("is_sink", 1 if m.is_sink else 0)
        if m.geometry_wkt:
            feat.SetGeometry(ogr.CreateGeometryFromWkt(m.geometry_wkt))
        layer.CreateFeature(feat)
        feat = None


def _write_pipes(ds, srs, pipes) -> None:
    layer = ds.CreateLayer("pipes", srs, ogr.wkbLineString)
    str_fields = ["code", "manhole1", "manhole2", "shape", "material",
                  "sewerage_type", "inspection_date", "issues"]
    real_fields = ["diameter", "width", "bob1", "bob2", "length", "bob_avg", "slope"]
    for name in str_fields:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTString))
    for name in real_fields:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("valid", ogr.OFTInteger))
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
        # Derived: mean BOB (hoogteligging) and slope/verhang (per metre).
        if p.bob1 is not None and p.bob2 is not None:
            _set(feat, "bob_avg", (p.bob1 + p.bob2) / 2.0)
            if p.length:
                _set(feat, "slope", abs(p.bob1 - p.bob2) / p.length)
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
    # Drop and recreate the layer (fast) instead of deleting features one by one.
    for i in range(ds.GetLayerCount()):
        if ds.GetLayer(i).GetName() == "measurements":
            ds.DeleteLayer(i)
            break
    ds.StartTransaction()
    _write_measurements(ds, _srs(), rows)
    ds.CommitTransaction()
    ds = None
    return len(rows)


def write_berging_lines(path, line_rows) -> int:
    """Create/replace the ``berging`` LineString layer (aggregated lost-storage).

    Each row is a dict with ``pipe_code, dist_start, dist_end, length,
    flooded_pct, water_level, lost_volume, geometry_wkt``.
    """
    ds = ogr.Open(str(path), update=1)
    for i in range(ds.GetLayerCount()):
        if ds.GetLayer(i).GetName() == "berging":
            ds.DeleteLayer(i)
            break
    layer = ds.CreateLayer("berging", _srs(), ogr.wkbLineString)
    layer.CreateField(ogr.FieldDefn("pipe_code", ogr.OFTString))
    for name in ["dist_start", "dist_end", "length", "flooded_pct",
                 "water_level", "lost_volume"]:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
    defn = layer.GetLayerDefn()
    ds.StartTransaction()
    for row in line_rows:
        feat = ogr.Feature(defn)
        _set(feat, "pipe_code", row.get("pipe_code"))
        _set(feat, "dist_start", row.get("dist_start"))
        _set(feat, "dist_end", row.get("dist_end"))
        _set(feat, "length", row.get("length"))
        _set(feat, "flooded_pct", row.get("flooded_pct"))
        _set(feat, "water_level", row.get("water_level"))
        _set(feat, "lost_volume", row.get("lost_volume"))
        if row.get("geometry_wkt"):
            feat.SetGeometry(ogr.CreateGeometryFromWkt(row["geometry_wkt"]))
        layer.CreateFeature(feat)
    ds.CommitTransaction()
    ds = None
    return len(line_rows)


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


def _write_measurements_raw(ds, srs, raw_measurements) -> None:
    """Write the un-integrated measurements as a geometry-less attribute table."""
    layer = ds.CreateLayer("measurements_raw", srs, ogr.wkbNone)
    layer.CreateField(ogr.FieldDefn("pipe_code", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("dist", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("value", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("mtype", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("reverse", ogr.OFTInteger))
    defn = layer.GetLayerDefn()
    for code, raw in (raw_measurements or {}).items():
        for point in raw.points:
            feat = ogr.Feature(defn)
            _set(feat, "pipe_code", code)
            _set(feat, "dist", point.get("dist"))
            _set(feat, "value", point.get("value"))
            _set(feat, "mtype", raw.measurement_type)
            feat.SetField("reverse", 1 if raw.reverse else 0)
            layer.CreateFeature(feat)
            feat = None


def write_base(path, manholes, pipes, raw_measurements) -> Path:
    """Create (overwrite) the step-1 GeoPackage: manholes, pipes, measurements_raw.

    No integrated heights, no segments, no validation — those are step 2.
    """
    path = Path(path)
    if path.exists():
        path.unlink()
    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(str(path))
    srs = _srs()
    bottom_levels = _manhole_bottom_levels(pipes)
    ds.StartTransaction()
    _write_manholes(ds, srs, manholes, bottom_levels)
    _write_pipes(ds, srs, pipes)
    _write_measurements_raw(ds, srs, raw_measurements)
    ds.CommitTransaction()
    ds = None
    return path


def read_raw_measurements(path) -> dict:
    """Read ``measurements_raw`` back into ``{pipe_code: RawMeasurements}``."""
    from rgs_ribx.model.raw import RawMeasurements

    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("measurements_raw")
    grouped = {}
    meta = {}
    if layer is None:
        return grouped
    for feat in layer:
        code = feat.GetField("pipe_code")
        grouped.setdefault(code, []).append(
            {"dist": feat.GetField("dist"), "value": feat.GetField("value")})
        if code not in meta:
            meta[code] = (feat.GetField("mtype") or "", bool(feat.GetField("reverse")))
    result = {}
    for code, points in grouped.items():
        mtype, reverse = meta[code]
        result[code] = RawMeasurements(pipe_code=code, measurement_type=mtype,
                                       reverse=reverse, points=points)
    return result
