"""Write/read the sewer GeoPackage. Pure OGR (no QGIS) so it is testable.

Layers (EPSG:28992): manholes (Point), pipes (LineString), and the pipeline
layers produced downstream (measurements_raw, profile, segments).
"""

from pathlib import Path

from osgeo import ogr, osr

import rgs_ribx

RD_EPSG = 28992

# Bumped whenever the base layers' schema changes incompatibly. Written into the
# GeoPackage's ``dw_meta`` table by :func:`write_base` so :func:`check_base_schema`
# can recognise (and refuse) GeoPackages from other tools or older plug-in versions.
SCHEMA_VERSION = 1

# Commit the feature inserts in batches of this many. A single transaction over
# millions of features holds an unbounded SQLite journal in memory and can crash the
# GDAL/SQLite write on Windows; committing periodically bounds it. Module-level so
# tests can lower it to exercise the batch boundary.
WRITE_BATCH = 50000

# Minimal set of fields a Drainworks base GeoPackage must expose per layer; used to
# tell a real Drainworks gpkg apart from a foreign/old one before reading it.
_REQUIRED_FIELDS = {
    "pipes": ("code", "manhole1", "manhole2", "bob1", "bob2"),
    "manholes": ("code", "ground_level", "is_sink"),
}


def _srs() -> "osr.SpatialReference":
    """Return the RD New (EPSG:28992) spatial reference for the GeoPackage layers."""
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(RD_EPSG)
    return srs


def _set(feature, name, value) -> None:
    """Set a field, leaving it NULL when value is None."""
    if value is None:
        feature.SetFieldNull(name)
    else:
        feature.SetField(name, value)


def _seti(feature, idx, value) -> None:
    """Set a field by integer index, leaving it NULL when value is None.

    OGR resolves a field name to an index on every ``SetField(name, ...)`` /
    ``GetField(name)`` call; using the index skips that per-call lookup, which
    dominates read/write time over millions of features.
    """
    if value is None:
        feature.SetFieldNull(idx)
    else:
        feature.SetField(idx, value)


def _field_index(layer) -> dict:
    """Return ``{field_name: index}`` for ``layer``, resolved once.

    Callers look indices up here before iterating features and then read/write by
    index, avoiding OGR's per-call name->index resolution. A name absent from the
    layer simply won't be a key (``dict.get`` returns None).
    """
    defn = layer.GetLayerDefn()
    return {defn.GetFieldDefn(i).GetName(): i for i in range(defn.GetFieldCount())}


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
    """Return the cumulative chainage [0.0, ...] along the ``(x, y)`` vertices ``pts``."""
    cum = [0.0]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        cum.append(cum[-1] + ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
    return cum


def _interpolate(pts, cum, dist):
    """Return the ``(x, y)`` point at ``dist`` along ``pts`` (chainage ``cum``), clamped to the ends."""
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


def _manhole_bottom_levels(pipes) -> dict:
    """{manhole_code: lowest connected pipe BOB} — the put's bottom (bodemhoogte)."""
    levels = {}
    for p in pipes:
        for code, bob in ((p.manhole1, p.bob1), (p.manhole2, p.bob2)):
            if code and bob is not None:
                levels[code] = bob if code not in levels else min(levels[code], bob)
    return levels


def _write_manholes(ds, srs, manholes, bottom_levels=None) -> None:
    """Create the ``manholes`` Point layer and write one feature per manhole.

    Parameters
    ----------
    ds : osgeo.ogr.DataSource
        Open, writable GeoPackage datasource.
    srs : osr.SpatialReference
        Spatial reference for the new layer.
    manholes : iterable of rgs_ribx.Manhole
        Manholes to write.
    bottom_levels : dict, optional
        ``{manhole_code: bottom_level}`` lowest connected pipe BOB; missing codes
        leave ``bottom_level`` NULL.
    """
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
    """Create the ``pipes`` LineString layer and write one feature per pipe.

    Derives and stores ``bob_avg`` (mean BOB) and ``slope`` (verhang per metre)
    when both BOBs and a length are available.

    Parameters
    ----------
    ds : osgeo.ogr.DataSource
        Open, writable GeoPackage datasource.
    srs : osr.SpatialReference
        Spatial reference for the new layer.
    pipes : iterable of rgs_ribx.Pipe
        Pipes to write.
    """
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


def read_pipes(path) -> list:
    """Read the ``pipes`` layer back into rgs_ribx.Pipe entities."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("pipes")
    fi = _field_index(layer)
    pipes = []
    for feat in layer:
        geom = feat.GetGeometryRef()
        date_str = feat.GetField(fi["inspection_date"])
        inspection_date = None
        if date_str:
            from datetime import date

            inspection_date = date.fromisoformat(date_str)
        # Fall back to the geometry length when the stored length is missing or
        # zero, so routing/profile distances are always available.
        length = feat.GetField(fi["length"])
        if (not length) and geom is not None:
            length = geom.Length()
        pipes.append(
            rgs_ribx.Pipe(
                code=feat.GetField(fi["code"]),
                manhole1=feat.GetField(fi["manhole1"]),
                manhole2=feat.GetField(fi["manhole2"]),
                geometry_wkt=geom.ExportToWkt() if geom else None,
                shape=feat.GetField(fi["shape"]) or "A",
                diameter=feat.GetField(fi["diameter"]),
                width=feat.GetField(fi["width"]),
                bob1=feat.GetField(fi["bob1"]),
                bob2=feat.GetField(fi["bob2"]),
                length=length,
                material=feat.GetField(fi["material"]),
                sewerage_type=feat.GetField(fi["sewerage_type"]),
                inspection_date=inspection_date,
            )
        )
    return pipes


def read_manholes(path) -> list:
    """Read the ``manholes`` layer back into rgs_ribx.Manhole entities."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("manholes")
    fi = _field_index(layer)
    manholes = []
    for feat in layer:
        geom = feat.GetGeometryRef()
        manholes.append(
            rgs_ribx.Manhole(
                code=feat.GetField(fi["code"]),
                geometry_wkt=geom.ExportToWkt() if geom else None,
                node_type=feat.GetField(fi["node_type"]),
                ground_level=feat.GetField(fi["ground_level"]),
                is_sink=bool(feat.GetField(fi["is_sink"])),
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


def read_manhole_points(path):
    """Return {code: (x, y)} for all manholes with a point geometry."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("manholes")
    i_code = _field_index(layer)["code"]
    points = {}
    for feat in layer:
        geom = feat.GetGeometryRef()
        if geom is not None:
            points[feat.GetField(i_code)] = (geom.GetX(), geom.GetY())
    return points


def _write_measurements_raw(ds, srs, raw_measurements, on_batch=None) -> None:
    """Write the un-integrated measurements as a geometry-less attribute table.

    There can be millions of measurement points, so this sets fields by their
    integer index (stable in creation order) instead of by name. OGR resolves a
    field name to an index on every ``SetField(name, ...)`` call; by index that
    lookup is skipped, which dominates the write time for large inspections.
    ``on_batch(fraction)`` (0..1), if given, is called after each committed batch.
    """
    layer = ds.CreateLayer("measurements_raw", srs, ogr.wkbNone)
    layer.CreateField(ogr.FieldDefn("pipe_code", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("dist", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("value", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("mtype", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("reverse", ogr.OFTInteger))
    defn = layer.GetLayerDefn()
    f_code, f_dist, f_value, f_mtype, f_reverse = 0, 1, 2, 3, 4  # creation order
    total = sum(len(r.points) for r in (raw_measurements or {}).values()) or 1
    n = 0
    ds.StartTransaction()
    for code, raw in (raw_measurements or {}).items():
        mtype = raw.measurement_type
        reverse = 1 if raw.reverse else 0
        for point in raw.points:
            feat = ogr.Feature(defn)
            if code is None:
                feat.SetFieldNull(f_code)
            else:
                feat.SetField(f_code, code)
            dist = point.get("dist")
            if dist is None:
                feat.SetFieldNull(f_dist)
            else:
                feat.SetField(f_dist, dist)
            value = point.get("value")
            if value is None:
                feat.SetFieldNull(f_value)
            else:
                feat.SetField(f_value, value)
            if mtype is None:
                feat.SetFieldNull(f_mtype)
            else:
                feat.SetField(f_mtype, mtype)
            feat.SetField(f_reverse, reverse)
            layer.CreateFeature(feat)
            feat = None
            n += 1
            if n % WRITE_BATCH == 0:        # bound the transaction size (Windows safety)
                ds.CommitTransaction()
                ds.StartTransaction()
                if on_batch is not None:
                    on_batch(n / total)
    ds.CommitTransaction()
    if on_batch is not None:
        on_batch(1.0)


def write_base(path, manholes, pipes, raw_measurements, on_progress=None) -> Path:
    """Create (overwrite) the step-1 GeoPackage: manholes, pipes, measurements_raw.

    No integrated heights, no segments, no validation — those are step 2.
    ``on_progress(fraction, label)`` (0..1), if given, reports write progress.

    NOTE: this does GDAL/SQLite I/O and must run on the main (GUI) thread — running
    it in a ``QgsTask`` worker thread crashes QGIS on Windows when finalising a large
    GeoPackage (access violation in the SQLite file-lock handling).
    """
    def _report(frac, label):
        if on_progress is not None:
            try:
                on_progress(frac, label)
            except Exception:
                pass

    path = Path(path)
    if path.exists():
        path.unlink()
    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(str(path))
    srs = _srs()
    bottom_levels = _manhole_bottom_levels(pipes)
    _report(0.02, "GeoPackage wegschrijven…")
    ds.StartTransaction()
    _write_manholes(ds, srs, manholes, bottom_levels)
    _write_pipes(ds, srs, pipes)
    ds.CommitTransaction()
    # measurements_raw can be millions of rows -> it manages its own batched
    # transactions (committing periodically) rather than one giant transaction.
    _write_measurements_raw(ds, srs, raw_measurements,
                            on_batch=lambda f: _report(0.05 + 0.92 * f, "Metingen wegschrijven…"))
    ds = None
    # Stamp the schema version so the GeoPackage can be recognised on re-open.
    write_meta(path, {"schema_version": SCHEMA_VERSION})
    _report(1.0, "Klaar")
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
    fi = _field_index(layer)
    i_code, i_dist, i_value = fi["pipe_code"], fi["dist"], fi["value"]
    i_mtype, i_reverse = fi["mtype"], fi["reverse"]
    for feat in layer:
        code = feat.GetField(i_code)
        grouped.setdefault(code, []).append(
            {"dist": feat.GetField(i_dist), "value": feat.GetField(i_value)})
        if code not in meta:
            meta[code] = (feat.GetField(i_mtype) or "", bool(feat.GetField(i_reverse)))
    result = {}
    for code, points in grouped.items():
        mtype, reverse = meta[code]
        result[code] = RawMeasurements(pipe_code=code, measurement_type=mtype,
                                       reverse=reverse, points=points)
    return result


def _apply_issues(layer, issues_by_code) -> None:
    """Set valid/issues on every feature of ``layer`` keyed by its ``code``."""
    layer.ResetReading()
    for feat in layer:
        issues = issues_by_code.get(feat.GetField("code"), [])
        feat.SetField("valid", 0 if issues else 1)
        if issues:
            feat.SetField("issues", "; ".join(issues))
        else:
            feat.SetFieldNull("issues")
        layer.SetFeature(feat)


def set_validation(path, validation) -> None:
    """Write a ``validate_network`` result onto the pipes + manholes layers.

    ``validation`` is ``{"pipes": {code: [issues]}, "manholes": {code: [issues]}}``.
    """
    ds = ogr.Open(str(path), update=1)
    ds.StartTransaction()
    _apply_issues(ds.GetLayerByName("pipes"), validation.get("pipes", {}))
    _apply_issues(ds.GetLayerByName("manholes"), validation.get("manholes", {}))
    ds.CommitTransaction()
    ds = None


def refresh_pipe_derived(path) -> None:
    """Recompute ``bob_avg``/``slope`` on the pipes layer from bob1/bob2/length.

    ``write_base`` derives these once at import; hand-edited BOBs would otherwise
    keep stale derived values (they only feed the thematic map styling). NULL when
    either BOB is missing; slope NULL without a usable length.
    """
    ds = ogr.Open(str(path), update=1)
    layer = ds.GetLayerByName("pipes")
    fi = _field_index(layer)
    ds.StartTransaction()
    layer.ResetReading()
    for feat in layer:
        bob1 = _opt_idx(feat, fi.get("bob1"))
        bob2 = _opt_idx(feat, fi.get("bob2"))
        length = _opt_idx(feat, fi.get("length"))
        bob_avg = slope = None
        if bob1 is not None and bob2 is not None:
            bob_avg = (bob1 + bob2) / 2.0
            if length:
                slope = abs(bob1 - bob2) / length
        _seti(feat, fi["bob_avg"], bob_avg)
        _seti(feat, fi["slope"], slope)
        layer.SetFeature(feat)
    ds.CommitTransaction()
    ds = None


SEGMENT_BERGING_FIELDS = ["water_level", "flooded_pct", "lost_volume",
                          "flooded_length", "flooded_pct_max", "water_depth_max"]


def _replace_layer(ds, name) -> None:
    """Drop ``name`` if present (caller recreates it in the same datasource)."""
    for i in range(ds.GetLayerCount()):
        if ds.GetLayer(i).GetName() == name:
            ds.DeleteLayer(i)
            return


def write_profile(path, rows) -> int:
    """Create/replace the ``profile`` Point layer (detailed computed heights)."""
    ds = ogr.Open(str(path), update=1)
    _replace_layer(ds, "profile")
    layer = ds.CreateLayer("profile", _srs(), ogr.wkbPoint)
    layer.CreateField(ogr.FieldDefn("pipe_code", ogr.OFTString))
    for name in ("dist", "bob", "obb", "water_level", "flooded_pct"):
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
    defn = layer.GetLayerDefn()
    # Field indices in creation order; set by index (millions of profile points).
    f_code, f_dist, f_bob, f_obb, f_wl, f_fp = 0, 1, 2, 3, 4, 5
    ds.StartTransaction()
    for n, row in enumerate(rows, 1):
        feat = ogr.Feature(defn)
        _seti(feat, f_code, row.get("pipe_code"))
        _seti(feat, f_dist, row.get("dist"))
        _seti(feat, f_bob, row.get("bob"))
        _seti(feat, f_obb, row.get("obb"))
        _seti(feat, f_wl, row.get("water_level"))
        _seti(feat, f_fp, row.get("flooded_pct"))
        if row.get("geometry_wkt"):
            feat.SetGeometry(ogr.CreateGeometryFromWkt(row["geometry_wkt"]))
        layer.CreateFeature(feat)
        feat = None
        if n % WRITE_BATCH == 0:        # bound the transaction size (Windows safety)
            ds.CommitTransaction()
            ds.StartTransaction()
    ds.CommitTransaction()
    ds = None
    return len(rows)


def _opt_idx(feat, idx):
    """Return field ``idx`` or None when the index is absent (-1/None) or NULL."""
    if idx is None or idx < 0 or feat.IsFieldNull(idx):
        return None
    return feat.GetField(idx)


def read_profile(path) -> dict:
    """Return ``{pipe_code: [MeasurementPoint]}`` from the ``profile`` layer."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("profile")
    grouped = {}
    if layer is None:
        return grouped
    fi = _field_index(layer)
    i_code, i_dist, i_bob, i_obb = fi["pipe_code"], fi["dist"], fi["bob"], fi["obb"]
    i_wl, i_fp = fi.get("water_level"), fi.get("flooded_pct")  # absent on old layers
    for feat in layer:
        mp = rgs_ribx.MeasurementPoint(dist=feat.GetField(i_dist),
                                       bob=feat.GetField(i_bob),
                                       obb=feat.GetField(i_obb))
        wl = _opt_idx(feat, i_wl)
        fp = _opt_idx(feat, i_fp)
        if wl is not None:
            mp.water_level = wl
        if fp is not None:
            mp.flooded_pct = fp
        grouped.setdefault(feat.GetField(i_code), []).append(mp)
    for points in grouped.values():
        points.sort(key=lambda p: p.dist)
    return grouped


def write_segments(path, rows) -> int:
    """Create/replace the ``segments`` LineString layer (empty berging fields)."""
    ds = ogr.Open(str(path), update=1)
    _replace_layer(ds, "segments")
    layer = ds.CreateLayer("segments", _srs(), ogr.wkbLineString)
    layer.CreateField(ogr.FieldDefn("pipe_code", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("source", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("n_measurements", ogr.OFTInteger))
    real_names = ("dist_from", "dist_to", "length", "bob_start", "bob_end",
                  "bob_highest", "slope_avg", "diameter")
    for name in (*real_names, *SEGMENT_BERGING_FIELDS):
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
    defn = layer.GetLayerDefn()
    fi = _field_index(layer)  # resolve once; set by index below
    i_real = [fi[name] for name in real_names]
    ds.StartTransaction()
    for n, row in enumerate(rows, 1):
        feat = ogr.Feature(defn)
        _seti(feat, fi["pipe_code"], row.get("pipe_code"))
        _seti(feat, fi["source"], row.get("source"))
        feat.SetField(fi["n_measurements"], int(row.get("n_measurements") or 0))
        for name, idx in zip(real_names, i_real):
            _seti(feat, idx, row.get(name))
        if row.get("geometry_wkt"):
            feat.SetGeometry(ogr.CreateGeometryFromWkt(row["geometry_wkt"]))
        layer.CreateFeature(feat)
        feat = None
        if n % WRITE_BATCH == 0:        # bound the transaction size (Windows safety)
            ds.CommitTransaction()
            ds.StartTransaction()
    ds.CommitTransaction()
    ds = None
    return len(rows)


def read_segments(path) -> list:
    """Return the ``segments`` rows as dicts (including OGR ``fid``)."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("segments")
    out = []
    if layer is None:
        return out
    fi = _field_index(layer)
    plain = ("pipe_code", "source", "n_measurements", "dist_from", "dist_to",
             "length", "bob_start", "bob_end", "bob_highest", "slope_avg", "diameter")
    cols = [(name, fi[name]) for name in (*plain, *SEGMENT_BERGING_FIELDS)]
    for feat in layer:
        row = {"fid": feat.GetFID()}
        for name, idx in cols:
            row[name] = feat.GetField(idx)
        out.append(row)
    return out


def update_segments_berging(path, by_fid) -> int:
    """Set the berging fields on ``segments`` features keyed by OGR fid."""
    ds = ogr.Open(str(path), update=1)
    layer = ds.GetLayerByName("segments")
    fi = _field_index(layer)
    idxs = [(name, fi[name]) for name in SEGMENT_BERGING_FIELDS]
    ds.StartTransaction()
    n = 0
    for fid, values in by_fid.items():
        feat = layer.GetFeature(fid)
        if feat is None:
            continue
        for name, idx in idxs:
            _seti(feat, idx, values.get(name))
        layer.SetFeature(feat)
        feat = None
        n += 1
        if n % WRITE_BATCH == 0:        # bound the transaction size (Windows safety)
            ds.CommitTransaction()
            ds.StartTransaction()
    ds.CommitTransaction()
    ds = None
    return len(by_fid)


def layer_counts(path) -> dict:
    """Return feature counts: ``{'manholes': n, 'pipes': n, 'measurements': n}``."""
    ds = ogr.Open(str(path))
    if ds is None:
        return {"manholes": 0, "pipes": 0, "measurements": 0}

    def _count(name):
        """Return the feature count of layer ``name`` (0 if the layer is absent)."""
        layer = ds.GetLayerByName(name)
        return layer.GetFeatureCount() if layer is not None else 0

    measurements = _count("measurements_raw")
    if ds.GetLayerByName("measurements_raw") is None:
        measurements = _count("measurements")  # legacy gpkg
    return {"manholes": _count("manholes"), "pipes": _count("pipes"),
            "measurements": measurements}


def total_lost_volume(path) -> float:
    """Return the summed ``lost_volume`` over the ``segments`` layer (0.0 if none)."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("segments") if ds is not None else None
    if layer is None:
        return 0.0
    total = 0.0
    for feat in layer:
        value = feat.GetField("lost_volume")
        if value is not None:
            total += value
    return total


def read_manhole_bottom_levels(path) -> dict:
    """Return ``{manhole_code: bottom_level}`` (NULL bottoms omitted)."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("manholes") if ds is not None else None
    levels = {}
    if layer is None:
        return levels
    for feat in layer:
        if not feat.IsFieldNull("bottom_level"):
            levels[feat.GetField("code")] = feat.GetField("bottom_level")
    return levels


def _round6(value):
    """Round ``value`` to 6 decimals (None stays None) for stable fingerprinting."""
    return None if value is None else round(float(value), 6)


def _fingerprint_parts(pipes, raw, manholes) -> list:
    """Build the stable tuple list base_fingerprint hashes (shared by both entries)."""
    parts = []
    for p in sorted(pipes, key=lambda x: x.code or ""):
        parts.append(("P", p.code, p.manhole1, p.manhole2, _round6(p.bob1), _round6(p.bob2),
                      _round6(p.diameter), _round6(p.length), p.shape))
    for code in sorted(raw):
        rm = raw[code]
        for pt in sorted(rm.points, key=lambda d: d.get("dist") or 0.0):
            parts.append(("M", code, _round6(pt.get("dist")), _round6(pt.get("value")),
                          rm.measurement_type, rm.reverse))
    for m in sorted(manholes, key=lambda x: x.code or ""):
        parts.append(("K", m.code, _round6(m.ground_level), m.geometry_wkt is not None))
    return parts


def base_fingerprint_from(pipes, raw, manholes) -> str:
    """``base_fingerprint`` computed from already-loaded base data (no re-read).

    Identical hash to :func:`base_fingerprint` for the same data; lets ``enrich``
    reuse the pipes/raw/manholes it already read instead of reading them again.
    """
    import hashlib

    return hashlib.sha1(
        repr(_fingerprint_parts(pipes, raw, manholes)).encode("utf-8")).hexdigest()


def base_fingerprint(path) -> str:
    """A stable SHA-1 over the base data that drives the enrich output."""
    return base_fingerprint_from(
        read_pipes(path), read_raw_measurements(path), read_manholes(path))


def berging_fingerprint(enrich_fp, sinks) -> str:
    """SHA-1 over the enrich fingerprint + the sorted sink codes."""
    import hashlib

    return hashlib.sha1(repr((enrich_fp, sorted(sinks or []))).encode("utf-8")).hexdigest()


def read_meta(path) -> dict:
    """Read the ``dw_meta`` key/value table into a dict (JSON-decoded values)."""
    import json

    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("dw_meta") if ds is not None else None
    out = {}
    if layer is None:
        return out
    for feat in layer:
        try:
            out[feat.GetField("key")] = json.loads(feat.GetField("value"))
        except (ValueError, TypeError):
            continue
    return out


def write_meta(path, values) -> None:
    """Merge ``values`` into the ``dw_meta`` table (JSON-encoded values)."""
    import json

    merged = read_meta(path)
    merged.update(values)
    ds = ogr.Open(str(path), update=1)
    _replace_layer(ds, "dw_meta")
    layer = ds.CreateLayer("dw_meta", _srs(), ogr.wkbNone)
    layer.CreateField(ogr.FieldDefn("key", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("value", ogr.OFTString))
    defn = layer.GetLayerDefn()
    ds.StartTransaction()
    for key, value in merged.items():
        feat = ogr.Feature(defn)
        feat.SetField("key", key)
        feat.SetField("value", json.dumps(value))
        layer.CreateFeature(feat)
        feat = None
    ds.CommitTransaction()
    ds = None


def read_schema_version(path):
    """Return the GeoPackage's stored ``schema_version`` (int), or None if absent."""
    return read_meta(path).get("schema_version")


def check_base_schema(path) -> "str | None":
    """Validate that ``path`` is a Drainworks base GeoPackage this plug-in can open.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the GeoPackage to open.

    Returns
    -------
    str or None
        ``None`` when the GeoPackage has the expected Drainworks layers/fields and a
        compatible schema version. Otherwise a human-readable Dutch reason why it
        cannot be opened (suitable for a message bar) — typically because it was made
        with another tool or an older/newer plug-in version.
    """
    ds = ogr.Open(str(path))
    if ds is None:
        return "Het bestand kon niet als GeoPackage geopend worden."
    missing_layers = [name for name in _REQUIRED_FIELDS if ds.GetLayerByName(name) is None]
    if missing_layers:
        return (
            f"Deze GeoPackage mist de Drainworks-laag/-lagen ({', '.join(missing_layers)}). "
            "Hij is waarschijnlijk met een ander programma of een oudere versie gemaakt. "
            "Maak hem opnieuw aan door het RIBX/SUFRIB-bestand te importeren.")
    for layer_name, required in _REQUIRED_FIELDS.items():
        defn = ds.GetLayerByName(layer_name).GetLayerDefn()
        present = {defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())}
        missing = [f for f in required if f not in present]
        if missing:
            version = read_schema_version(path)
            vtext = (f"schemaversie {version}" if version is not None
                     else "geen Drainworks-schemaversie")
            return (
                f"De laag '{layer_name}' mist verwachte velden ({', '.join(missing)}). "
                f"De GeoPackage heeft {vtext} en is niet compatibel met deze plug-inversie "
                f"(verwacht schemaversie {SCHEMA_VERSION}). Maak hem opnieuw aan via Importeren.")
    version = read_schema_version(path)
    if version is not None and version != SCHEMA_VERSION:
        return (
            f"Deze GeoPackage heeft schemaversie {version}, maar deze plug-in verwacht "
            f"versie {SCHEMA_VERSION}. Maak hem opnieuw aan via Importeren.")
    return None
