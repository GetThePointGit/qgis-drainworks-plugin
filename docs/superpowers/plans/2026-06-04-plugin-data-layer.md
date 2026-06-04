# Plugin Data Layer (3-step pipeline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewire the plugin's GeoPackage store and runners onto the new `rgs-ribx` enrich API as three persisted, independently re-runnable steps — import (base + raw measurements), enrich (validate + heights + segments), and lost storage (berging on segments).

**Architecture:** Additive and non-breaking. New store functions (`write_base`, `measurements_raw`/`profile`/`segments` layers, validation writer) and two new runner modules (`pipeline/enrich.py`, `pipeline/berging.py`) sit alongside the existing `write_geopackage`/`lostcapacity/runner.py`, which keep the current plugin working. Plan C swaps the GUI over to the new functions and deletes the old path. Everything here is pure `osgeo.ogr` + `rgs_ribx` (no `qgis.*`), so it runs under headless pytest exactly like the existing `tests/`.

**Tech Stack:** Python 3.9 (QGIS-LTR2 bundle), `osgeo.ogr`/`osr`, `rgs_ribx` (Plan A: `integrate_profiles`, `build_segments`, `validate_network`, `RawMeasurements`, `compute_lost_capacity`), pytest.

**Spec:** `docs/superpowers/specs/2026-06-04-drainworks-1.0-refinements-design.md` (section 1).

**Repo:** `~/Documents/GitHub/qgis-drainworks-plugin`.

### Test command (headless)

Every test step uses the QGIS-LTR2 Python with PROJ/GDAL env and `rgs-ribx/src` on the path. Define this once per shell:

```bash
cd ~/Documents/GitHub/qgis-drainworks-plugin
export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3"
export PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj"
export PROJ_DATA="$PROJ_LIB"
export GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal"
export PYTHONPATH="$PWD:$HOME/Documents/GitHub/rgs-ribx/src"
```
Then run tests with `"$QGIS_PY" -m pytest <args>`. A teardown segfault (exit 139) AFTER the pytest summary line is harmless (see memory `dev-test-environment`).

> **Git (user rule):** never commit on `main`. Start with `git switch -c feature/plugin-data-layer`. Never `git push`.

---

## File Structure

```
drainworks_plugin/
├── io/
│   └── geopackage_store.py    # MODIFY (additive): write_base, measurements_raw/profile/segments
│                              #   layers, validation writer, segment berging updater, readers.
│                              #   Add valid/issues fields to _write_manholes/_write_pipes.
├── pipeline/                  # CREATE package
│   ├── __init__.py            # CREATE (empty)
│   ├── enrich.py              # CREATE: enrich() — step 2
│   └── berging.py             # CREATE: compute_berging() — step 3
tests/
├── test_geopackage_store_base.py   # CREATE
├── test_geopackage_validation.py   # CREATE
├── test_geopackage_profile_segments.py  # CREATE
├── test_pipeline_enrich.py         # CREATE
├── test_pipeline_berging.py        # CREATE
└── test_pipeline_end_to_end.py     # CREATE
```

Layer schema introduced (EPSG:28992):
- `measurements_raw` (no geometry) — `pipe_code, dist, value, mtype, reverse`.
- `manholes`/`pipes` — gain `valid` (int 0/1) + `issues` (text), written empty in step 1, filled in step 2.
- `profile` (Point) — `pipe_code, dist, bob, obb`.
- `segments` (LineString) — `pipe_code, dist_from, dist_to, length, bob_start, bob_end, bob_highest, slope_avg, diameter, n_measurements, source`, plus berging fields `water_level, flooded_pct, lost_volume, flooded_length, flooded_pct_max` (empty until step 3).

---

## Task 1: Base write (manholes + pipes + measurements_raw)

**Files:**
- Modify: `drainworks_plugin/io/geopackage_store.py`
- Test: `tests/test_geopackage_store_base.py`

Add `valid`/`issues` fields to the pipe & manhole writers, a `measurements_raw`
layer, `write_base(...)`, and `read_raw_measurements(...)`.

- [ ] **Step 1: Write the failing test** `tests/test_geopackage_store_base.py`:

```python
import rgs_ribx
from rgs_ribx.model.raw import RawMeasurements

from drainworks_plugin.io.geopackage_store import read_raw_measurements, write_base


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
    # pipes gained validation fields
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
```

> The `inclined.ribx` fixture lives in `rgs-ribx/tests/fixtures/`. Copy it into the plugin's fixtures first: `cp ~/Documents/GitHub/rgs-ribx/tests/fixtures/inclined.ribx ~/Documents/GitHub/qgis-drainworks-plugin/tests/fixtures/inclined.ribx` (commit it with this task).

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_geopackage_store_base.py -v`
Expected: FAIL with `ImportError: cannot import name 'write_base'`.

- [ ] **Step 3: Implement in `drainworks_plugin/io/geopackage_store.py`.**

(a) Add `valid`/`issues` fields to `_write_manholes`. After the `is_sink` field line:
```python
    layer.CreateField(ogr.FieldDefn("is_sink", ogr.OFTInteger))
    layer.CreateField(ogr.FieldDefn("valid", ogr.OFTInteger))
    layer.CreateField(ogr.FieldDefn("issues", ogr.OFTString))
```

(b) Add the same two fields to `_write_pipes`. The function currently builds
`str_fields` and `real_fields`. Append `"issues"` to `str_fields` and add a
`valid` integer field explicitly. Change:
```python
    str_fields = ["code", "manhole1", "manhole2", "shape", "material",
                  "sewerage_type", "inspection_date"]
    real_fields = ["diameter", "width", "bob1", "bob2", "length", "bob_avg", "slope"]
    for name in str_fields:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTString))
    for name in real_fields:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
```
to:
```python
    str_fields = ["code", "manhole1", "manhole2", "shape", "material",
                  "sewerage_type", "inspection_date", "issues"]
    real_fields = ["diameter", "width", "bob1", "bob2", "length", "bob_avg", "slope"]
    for name in str_fields:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTString))
    for name in real_fields:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("valid", ogr.OFTInteger))
```

(c) Add a `measurements_raw` writer and the public `write_base` + reader. Add at
the end of the file:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass + no regressions**

Run: `"$QGIS_PY" -m pytest tests/test_geopackage_store_base.py tests/test_geopackage_store.py -v`
Expected: new tests PASS; the existing `test_geopackage_store.py` still PASSES (the added `valid`/`issues` columns don't disturb its assertions).

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/io/geopackage_store.py tests/test_geopackage_store_base.py tests/fixtures/inclined.ribx
git commit -m "feat: write_base + measurements_raw layer + validation fields"
```

---

## Task 2: Validation writer

**Files:**
- Modify: `drainworks_plugin/io/geopackage_store.py`
- Test: `tests/test_geopackage_validation.py`

Write the `validate_network` result onto the `pipes` and `manholes` layers
(`valid` 0/1, `issues` joined text).

- [ ] **Step 1: Write the failing test** `tests/test_geopackage_validation.py`:

```python
import rgs_ribx

from drainworks_plugin.io.geopackage_store import set_validation, write_base


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_geopackage_validation.py -v`
Expected: FAIL with `ImportError: cannot import name 'set_validation'`.

- [ ] **Step 3: Implement `set_validation` in `geopackage_store.py`** (add at end):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_geopackage_validation.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/io/geopackage_store.py tests/test_geopackage_validation.py
git commit -m "feat: set_validation writes valid/issues onto pipes + manholes"
```

---

## Task 3: Profile + segments layers

**Files:**
- Modify: `drainworks_plugin/io/geopackage_store.py`
- Test: `tests/test_geopackage_profile_segments.py`

Add `write_profile`/`read_profile` and `write_segments`/`read_segments`/
`update_segments_berging`.

- [ ] **Step 1: Write the failing test** `tests/test_geopackage_profile_segments.py`:

```python
import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    read_profile,
    read_segments,
    update_segments_berging,
    write_base,
    write_profile,
    write_segments,
)


def _gpkg(tmp_gpkg):
    manholes = [rgs_ribx.Manhole(code="A", geometry_wkt="POINT (0 0)")]
    pipes = [rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="B", bob1=-2.0, bob2=-2.6,
                           diameter=0.3, length=30.0, geometry_wkt="LINESTRING (0 0, 30 0)")]
    write_base(tmp_gpkg, manholes, pipes, raw_measurements={})
    return tmp_gpkg


def test_profile_roundtrip(tmp_gpkg):
    _gpkg(tmp_gpkg)
    rows = [
        {"pipe_code": "L1", "dist": 0.0, "bob": -2.0, "obb": -1.7, "geometry_wkt": "POINT (0 0)"},
        {"pipe_code": "L1", "dist": 30.0, "bob": -2.6, "obb": -2.3, "geometry_wkt": "POINT (30 0)"},
    ]
    assert write_profile(tmp_gpkg, rows) == 2
    got = read_profile(tmp_gpkg)
    assert [round(p.dist, 1) for p in got["L1"]] == [0.0, 30.0]
    assert got["L1"][0].obb == -1.7


def test_segments_roundtrip_and_berging_update(tmp_gpkg):
    _gpkg(tmp_gpkg)
    rows = [{
        "pipe_code": "L1", "dist_from": 0.0, "dist_to": 15.0, "length": 15.0,
        "bob_start": -2.0, "bob_end": -2.3, "bob_highest": -2.0, "slope_avg": -0.02,
        "diameter": 0.3, "n_measurements": 2, "source": "measured",
        "geometry_wkt": "LINESTRING (0 0, 15 0)",
    }]
    assert write_segments(tmp_gpkg, rows) == 1
    segs = read_segments(tmp_gpkg)
    assert len(segs) == 1
    seg = segs[0]
    assert seg["pipe_code"] == "L1" and seg["source"] == "measured"
    assert "fid" in seg

    update_segments_berging(tmp_gpkg, {seg["fid"]: {
        "water_level": -2.1, "flooded_pct": 0.4, "lost_volume": 0.5,
        "flooded_length": 10.0, "flooded_pct_max": 0.6}})
    seg2 = read_segments(tmp_gpkg)[0]
    assert round(seg2["flooded_pct"], 2) == 0.4
    assert round(seg2["flooded_pct_max"], 2) == 0.6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_geopackage_profile_segments.py -v`
Expected: FAIL with `ImportError: cannot import name 'write_profile'`.

- [ ] **Step 3: Implement in `geopackage_store.py`** (add at end). Note `read_profile`
returns `rgs_ribx.MeasurementPoint` objects (so the berging runner can flood-fill
them directly):

```python
SEGMENT_BERGING_FIELDS = ["water_level", "flooded_pct", "lost_volume",
                          "flooded_length", "flooded_pct_max"]


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
    for name in ("dist", "bob", "obb"):
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
    defn = layer.GetLayerDefn()
    ds.StartTransaction()
    for row in rows:
        feat = ogr.Feature(defn)
        _set(feat, "pipe_code", row.get("pipe_code"))
        _set(feat, "dist", row.get("dist"))
        _set(feat, "bob", row.get("bob"))
        _set(feat, "obb", row.get("obb"))
        if row.get("geometry_wkt"):
            feat.SetGeometry(ogr.CreateGeometryFromWkt(row["geometry_wkt"]))
        layer.CreateFeature(feat)
        feat = None
    ds.CommitTransaction()
    ds = None
    return len(rows)


def read_profile(path) -> dict:
    """Return ``{pipe_code: [MeasurementPoint]}`` from the ``profile`` layer."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("profile")
    grouped = {}
    if layer is None:
        return grouped
    for feat in layer:
        grouped.setdefault(feat.GetField("pipe_code"), []).append(
            rgs_ribx.MeasurementPoint(dist=feat.GetField("dist"),
                                      bob=feat.GetField("bob"),
                                      obb=feat.GetField("obb")))
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
    for name in ("dist_from", "dist_to", "length", "bob_start", "bob_end",
                 "bob_highest", "slope_avg", "diameter", *SEGMENT_BERGING_FIELDS):
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
    defn = layer.GetLayerDefn()
    ds.StartTransaction()
    for row in rows:
        feat = ogr.Feature(defn)
        _set(feat, "pipe_code", row.get("pipe_code"))
        _set(feat, "source", row.get("source"))
        feat.SetField("n_measurements", int(row.get("n_measurements") or 0))
        for name in ("dist_from", "dist_to", "length", "bob_start", "bob_end",
                     "bob_highest", "slope_avg", "diameter"):
            _set(feat, name, row.get(name))
        if row.get("geometry_wkt"):
            feat.SetGeometry(ogr.CreateGeometryFromWkt(row["geometry_wkt"]))
        layer.CreateFeature(feat)
        feat = None
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
    for feat in layer:
        out.append({
            "fid": feat.GetFID(),
            "pipe_code": feat.GetField("pipe_code"),
            "source": feat.GetField("source"),
            "n_measurements": feat.GetField("n_measurements"),
            "dist_from": feat.GetField("dist_from"),
            "dist_to": feat.GetField("dist_to"),
            "length": feat.GetField("length"),
            "bob_start": feat.GetField("bob_start"),
            "bob_end": feat.GetField("bob_end"),
            "bob_highest": feat.GetField("bob_highest"),
            "slope_avg": feat.GetField("slope_avg"),
            "diameter": feat.GetField("diameter"),
        })
    return out


def update_segments_berging(path, by_fid) -> int:
    """Set the berging fields on ``segments`` features keyed by OGR fid."""
    ds = ogr.Open(str(path), update=1)
    layer = ds.GetLayerByName("segments")
    ds.StartTransaction()
    for fid, values in by_fid.items():
        feat = layer.GetFeature(fid)
        if feat is None:
            continue
        for name in SEGMENT_BERGING_FIELDS:
            _set(feat, name, values.get(name))
        layer.SetFeature(feat)
        feat = None
    ds.CommitTransaction()
    ds = None
    return len(by_fid)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_geopackage_profile_segments.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/io/geopackage_store.py tests/test_geopackage_profile_segments.py
git commit -m "feat: profile + segments layers (write/read/berging-update)"
```

---

## Task 4: Enrich runner (step 2)

**Files:**
- Create: `drainworks_plugin/pipeline/__init__.py` (empty)
- Create: `drainworks_plugin/pipeline/enrich.py`
- Test: `tests/test_pipeline_enrich.py`

`enrich()` reads the (possibly edited) base + raw, validates, integrates heights
to a `profile` layer, builds `segments`, and wipes any berging.

- [ ] **Step 1: Create `drainworks_plugin/pipeline/__init__.py`** as an empty file:

```python
```
(zero bytes / just a newline)

- [ ] **Step 2: Write the failing test** `tests/test_pipeline_enrich.py`:

```python
import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    read_profile,
    read_segments,
    write_base,
)
from drainworks_plugin.pipeline.enrich import enrich


def test_enrich_builds_profile_and_segments(fixtures_dir, tmp_gpkg):
    res = rgs_ribx.build_from_ribx(fixtures_dir / "inclined.ribx")
    write_base(tmp_gpkg, res.manholes, res.pipes, res.raw_measurements)

    summary = enrich(tmp_gpkg, correct_bob=True)

    profile = read_profile(tmp_gpkg)
    assert "L001" in profile and len(profile["L001"]) >= 2

    segs = read_segments(tmp_gpkg)
    assert segs and all(s["pipe_code"] == "L001" for s in segs)
    assert all(s["source"] == "measured" for s in segs)
    # berging not computed yet -> NULL
    assert all(s.get("flooded_pct") in (None, 0, 0.0) for s in segs)

    assert summary["n_segments"] == len(segs)
    assert "n_pipes_with_issues" in summary


def test_enrich_rerun_reflects_edited_bob(fixtures_dir, tmp_gpkg):
    res = rgs_ribx.build_from_ribx(fixtures_dir / "inclined.ribx")
    write_base(tmp_gpkg, res.manholes, res.pipes, res.raw_measurements)
    enrich(tmp_gpkg, correct_bob=True)
    first_end = read_profile(tmp_gpkg)["L001"][-1].bob

    # Edit bob2 directly in the pipes layer, then re-run enrich.
    from osgeo import ogr
    ds = ogr.Open(str(tmp_gpkg), update=1)
    layer = ds.GetLayerByName("pipes")
    feat = layer.GetNextFeature()
    feat.SetField("bob2", feat.GetField("bob2") - 1.0)
    layer.SetFeature(feat)
    ds = None

    enrich(tmp_gpkg, correct_bob=True)
    second_end = read_profile(tmp_gpkg)["L001"][-1].bob
    assert round(second_end - first_end, 2) == -1.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_pipeline_enrich.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'drainworks_plugin.pipeline.enrich'`.

- [ ] **Step 4: Write `drainworks_plugin/pipeline/enrich.py`:**

```python
"""Step 2 — enrich base data: validate, integrate heights, build segments.

Reads the (possibly edited) ``manholes``/``pipes``/``measurements_raw`` from the
GeoPackage and writes ``profile`` + ``segments``, plus ``valid``/``issues`` on the
base layers. Any previously computed berging is wiped (segments are recreated
empty); step 3 fills them.
"""

import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    linestring_substring_wkt,
    point_along_wkt,
    read_manholes,
    read_pipes,
    read_raw_measurements,
    set_validation,
    write_profile,
    write_segments,
)

# Defaults (configurable via the dock in Plan C).
MIN_SEGMENT = 1.0   # m, measured pipes
BOB_SEGMENT = 5.0   # m, pipes without measurements


def enrich(gpkg_path, correct_bob=True, min_segment=MIN_SEGMENT,
           bob_segment=BOB_SEGMENT) -> dict:
    """Run step 2 over a GeoPackage. Returns a summary dict."""
    manholes = read_manholes(gpkg_path)
    pipes = read_pipes(gpkg_path)
    pipes_by_code = {p.code: p for p in pipes}
    raw = read_raw_measurements(gpkg_path)

    # 1. Validation (measured length = furthest raw point per pipe).
    measured_length = {code: max((pt["dist"] for pt in rm.points), default=0.0)
                       for code, rm in raw.items()}
    validation = rgs_ribx.validate_network(manholes, pipes, measured_length=measured_length)
    set_validation(gpkg_path, validation)

    # 2. Heights -> profile points (with map geometry interpolated along the pipe).
    profiles = rgs_ribx.integrate_profiles(pipes_by_code, raw, correct_bob=correct_bob)
    profile_rows = []
    for code, points in profiles.items():
        pipe = pipes_by_code.get(code)
        wkt = pipe.geometry_wkt if pipe else None
        for mp in points:
            profile_rows.append({
                "pipe_code": code, "dist": mp.dist, "bob": mp.bob, "obb": mp.obb,
                "geometry_wkt": point_along_wkt(wkt, mp.dist) if wkt else None,
            })
    write_profile(gpkg_path, profile_rows)

    # 3. Segments (measured aggregation, BOB fallback for the rest).
    segment_rows = []
    for code, pipe in pipes_by_code.items():
        segs = rgs_ribx.build_segments(pipe, profiles.get(code, []),
                                       min_length=min_segment, bob_length=bob_segment)
        for seg in segs:
            geom = linestring_substring_wkt(pipe.geometry_wkt, seg["dist_from"], seg["dist_to"]) \
                if pipe.geometry_wkt else None
            segment_rows.append({**seg, "geometry_wkt": geom})
    write_segments(gpkg_path, segment_rows)

    n_pipe_issues = sum(1 for v in validation["pipes"].values() if v)
    n_manhole_issues = sum(1 for v in validation["manholes"].values() if v)
    return {
        "n_profile_points": len(profile_rows),
        "n_segments": len(segment_rows),
        "n_pipes_with_issues": n_pipe_issues,
        "n_manholes_with_issues": n_manhole_issues,
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_pipeline_enrich.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add drainworks_plugin/pipeline/__init__.py drainworks_plugin/pipeline/enrich.py tests/test_pipeline_enrich.py
git commit -m "feat: enrich runner (step 2: validate + heights + segments)"
```

---

## Task 5: Berging runner (step 3)

**Files:**
- Create: `drainworks_plugin/pipeline/berging.py`
- Test: `tests/test_pipeline_berging.py`

Flood-fill and fill the segment berging fields. Resolution *accurate* (default):
flood-fill the detailed `profile` points, aggregate onto each segment. *fast*:
flood-fill segment endpoints directly.

- [ ] **Step 1: Write the failing test** `tests/test_pipeline_berging.py`:

```python
import rgs_ribx

from drainworks_plugin.io.geopackage_store import read_segments, write_base
from drainworks_plugin.pipeline.berging import compute_berging
from drainworks_plugin.pipeline.enrich import enrich


def _setup(tmp_gpkg):
    # A dip in the middle of a flat pipe between two sinks -> water collects.
    manholes = [rgs_ribx.Manhole(code="P1", is_sink=True, geometry_wkt="POINT (0 0)"),
                rgs_ribx.Manhole(code="P2", is_sink=True, geometry_wkt="POINT (30 0)")]
    pipes = [rgs_ribx.Pipe(code="L1", manhole1="P1", manhole2="P2", bob1=-2.0, bob2=-2.0,
                           diameter=0.5, length=30.0, shape="A",
                           geometry_wkt="LINESTRING (0 0, 30 0)")]
    raw = {"L1": rgs_ribx.model.raw.RawMeasurements("L1", "AA", reverse=False, points=[
        {"dist": 0.0, "value": 0.0}, {"dist": 10.0, "value": -0.3},
        {"dist": 20.0, "value": -0.3}, {"dist": 30.0, "value": 0.0}])}
    write_base(tmp_gpkg, manholes, pipes, raw)
    enrich(tmp_gpkg, correct_bob=False)
    return tmp_gpkg


def test_compute_berging_accurate_fills_segments(tmp_gpkg):
    import rgs_ribx.model.raw  # noqa: F401  (ensure submodule import works)
    _setup(tmp_gpkg)
    n = compute_berging(tmp_gpkg, resolution="accurate")
    segs = read_segments(tmp_gpkg)
    assert n == len(segs)
    flooded = [s for s in segs if (s.get("flooded_pct") or 0) > 0]
    assert flooded, "the dip should flood at least one segment"
    assert all((s.get("flooded_pct_max") or 0) >= (s.get("flooded_pct") or 0) for s in segs)


def test_compute_berging_fast_runs(tmp_gpkg):
    import rgs_ribx.model.raw  # noqa: F401
    _setup(tmp_gpkg)
    n = compute_berging(tmp_gpkg, resolution="fast")
    assert n == len(read_segments(tmp_gpkg))
```

> If `rgs_ribx.model.raw` is not importable as an attribute in the test, replace
> `rgs_ribx.model.raw.RawMeasurements` with an explicit
> `from rgs_ribx.model.raw import RawMeasurements` at the top and use `RawMeasurements(...)`.

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_pipeline_berging.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'drainworks_plugin.pipeline.berging'`.

- [ ] **Step 3: Write `drainworks_plugin/pipeline/berging.py`:**

```python
"""Step 3 — lost storage (verloren berging) on segments.

Flood-fills a per-pipe profile and aggregates the result onto each pre-built
segment. ``resolution='accurate'`` (default) floods the detailed ``profile``
points; ``'fast'`` floods the coarse segment endpoints.
"""

import math

import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    read_manholes,
    read_pipes,
    read_profile,
    read_segments,
    update_segments_berging,
)


def _area(point):
    """Flooded cross-section area (m²) at a flood-filled MeasurementPoint."""
    pct = point.flooded_pct
    if not pct:
        return 0.0
    diameter = point.obb - point.bob
    return pct * math.pi * (diameter / 2.0) ** 2


def _endpoint_profile(pipe, seg_rows):
    """Build a coarse profile from a pipe's segment endpoints (sorted)."""
    rows = sorted(seg_rows, key=lambda s: s["dist_from"])
    diam = pipe.diameter or 0.0
    pts = [rgs_ribx.MeasurementPoint(dist=s["dist_from"], bob=s["bob_start"],
                                     obb=s["bob_start"] + diam) for s in rows]
    last = rows[-1]
    pts.append(rgs_ribx.MeasurementPoint(dist=last["dist_to"], bob=last["bob_end"],
                                         obb=last["bob_end"] + diam))
    return pts


def _aggregate(points):
    """Length-weighted berging aggregates over consecutive flood-filled points."""
    pts = sorted(points, key=lambda p: p.dist)
    total = flooded_len = vol = pct_w = water_w = water_len = pct_max = 0.0
    for a, b in zip(pts, pts[1:]):
        length = b.dist - a.dist
        if length <= 0:
            continue
        pa = a.flooded_pct or 0.0
        pb = b.flooded_pct or 0.0
        total += length
        pct_w += 0.5 * (pa + pb) * length
        pct_max = max(pct_max, pa, pb)
        vol += 0.5 * (_area(a) + _area(b)) * length
        if max(pa, pb) > 0:
            flooded_len += length
        waters = [w for w in (a.water_level, b.water_level) if w is not None]
        if waters:
            water_w += (sum(waters) / len(waters)) * length
            water_len += length
    return {
        "flooded_pct": (pct_w / total) if total else 0.0,
        "flooded_pct_max": pct_max,
        "lost_volume": vol,
        "flooded_length": flooded_len,
        "water_level": (water_w / water_len) if water_len else None,
    }


def compute_berging(gpkg_path, resolution="accurate") -> int:
    """Flood-fill + fill segment berging fields. Returns the segment count."""
    manholes = {m.code: m for m in read_manholes(gpkg_path)}
    pipes = {p.code: p for p in read_pipes(gpkg_path)}
    segments = read_segments(gpkg_path)
    profile_pts = read_profile(gpkg_path)

    segs_by_pipe = {}
    for seg in segments:
        segs_by_pipe.setdefault(seg["pipe_code"], []).append(seg)

    # Per-pipe profile for the flood-fill graph.
    profiles = {}
    for code, pipe in pipes.items():
        if resolution == "accurate" and profile_pts.get(code):
            profiles[code] = profile_pts[code]
        elif segs_by_pipe.get(code):
            profiles[code] = _endpoint_profile(pipe, segs_by_pipe[code])
    rgs_ribx.compute_lost_capacity(manholes, pipes, profiles)

    # Aggregate each segment from its pipe's (now flood-filled) points within span.
    updates = {}
    for seg in segments:
        pts = profiles.get(seg["pipe_code"], [])
        d0, d1 = seg["dist_from"], seg["dist_to"]
        window = [p for p in pts if d0 - 1e-6 <= p.dist <= d1 + 1e-6]
        if len(window) < 2:
            window = pts  # coarse pipe: one segment spans the whole profile
        updates[seg["fid"]] = _aggregate(window)
    update_segments_berging(gpkg_path, updates)
    return len(segments)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_pipeline_berging.py -v`
Expected: PASS (2 passed). If `test_compute_berging_accurate_fills_segments`
finds no flooded segment, do NOT weaken the assertion — STOP and report; it likely
means the dip/sink setup isn't connecting in the graph (check that both manholes are
sinks and the profile dips below the BOB line).

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/pipeline/berging.py tests/test_pipeline_berging.py
git commit -m "feat: berging runner (step 3: flood-fill + per-segment aggregation)"
```

---

## Task 6: End-to-end pipeline test + finish

**Files:**
- Test: `tests/test_pipeline_end_to_end.py`

Prove the three steps chain on one GeoPackage, and that re-running step 2 alone
clears the step-3 berging (re-enrich → segments empty again).

- [ ] **Step 1: Write the test** `tests/test_pipeline_end_to_end.py`:

```python
import rgs_ribx
from rgs_ribx.model.raw import RawMeasurements

from drainworks_plugin.io.geopackage_store import read_segments, write_base
from drainworks_plugin.pipeline.berging import compute_berging
from drainworks_plugin.pipeline.enrich import enrich


def _write(tmp_gpkg):
    manholes = [rgs_ribx.Manhole(code="P1", is_sink=True, geometry_wkt="POINT (0 0)"),
                rgs_ribx.Manhole(code="P2", is_sink=True, geometry_wkt="POINT (30 0)")]
    pipes = [rgs_ribx.Pipe(code="L1", manhole1="P1", manhole2="P2", bob1=-2.0, bob2=-2.0,
                           diameter=0.5, length=30.0, shape="A",
                           geometry_wkt="LINESTRING (0 0, 30 0)")]
    raw = {"L1": RawMeasurements("L1", "AA", reverse=False, points=[
        {"dist": 0.0, "value": 0.0}, {"dist": 10.0, "value": -0.3},
        {"dist": 20.0, "value": -0.3}, {"dist": 30.0, "value": 0.0}])}
    write_base(tmp_gpkg, manholes, pipes, raw)


def test_full_pipeline_then_reenrich_clears_berging(tmp_gpkg):
    _write(tmp_gpkg)
    enrich(tmp_gpkg, correct_bob=False)
    compute_berging(tmp_gpkg, resolution="accurate")
    assert any((s.get("flooded_pct") or 0) > 0 for s in read_segments(tmp_gpkg))

    # Re-running step 2 must wipe step-3 results (segments recreated empty).
    enrich(tmp_gpkg, correct_bob=False)
    assert all((s.get("flooded_pct") in (None, 0, 0.0)) for s in read_segments(tmp_gpkg))
```

- [ ] **Step 2: Run the full plugin suite**

Run: `"$QGIS_PY" -m pytest -q`
Expected: all tests pass (the new pipeline tests + the original 18, which remain
green because every change was additive). A trailing exit-139 segfault after the
summary is harmless.

- [ ] **Step 3: Commit**

```bash
git add tests/test_pipeline_end_to_end.py
git commit -m "test: end-to-end import->enrich->berging; re-enrich clears berging"
```

- [ ] **Step 4: Finish the branch**

REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch`. Do NOT push (user's global rule).

---

## Notes for the follow-up plan (C)

Plan C (GUI & UX) will:
- Rewire `plugin.py` / a new dock to three buttons (Importeren / Verrijk basisdata /
  Bereken verloren berging) calling `write_base` (via a thin import controller),
  `pipeline.enrich.enrich`, `pipeline.berging.compute_berging`, each in a `QgsTask`
  with a progress bar; surface the enrich summary via the message bar.
- Load/style the new `profile` + `segments` layers (graduated renderer on
  `flooded_pct`), add staleness tracking on layer edits, and remove the now-unused
  `write_geopackage` / `lostcapacity/runner.py` / old `measurements` layer path.
- Implement the trajectory/side-view/sinks/opmaak UX from spec section 2.
- The `min_segment` / `bob_segment` / `correct_bob` / resolution settings become dock controls.
```
