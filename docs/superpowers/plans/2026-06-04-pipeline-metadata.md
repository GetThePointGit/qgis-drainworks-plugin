# Pipeline Metadata + Busy messageBar (C11) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a `dw_meta` table (base-data fingerprint + used settings + summaries + sinks) so re-opening a GeoPackage shows enrich/berging green + filled when up-to-date (fingerprint catches base edits, even across reloads), and show a busy message + indeterminate progress bar in the messageBar while a step runs.

**Architecture:** TDD core (fingerprint + meta store, `PipelineState.restore`, enrich/berging writing meta); GUI wiring for the messageBar busy item and the load-time restore in the dock. Verified by the suite + dock construction smoke + manual check.

**Tech Stack:** PyQt5 / `qgis.core`, `osgeo.ogr`, `hashlib`/`json`, pytest.

**Spec:** `docs/superpowers/specs/2026-06-04-pipeline-metadata-design.md`.

**Repo:** plugin, branch `feature/pipeline-metadata`. Test/env prefix:
```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3" PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj" PROJ_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/proj" GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal" PYTHONPATH="/Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin:/Users/bastiaanroos/Documents/GitHub/rgs-ribx/src" && "$QGIS_PY" -m pytest <args>
```
Teardown segfault after the summary is harmless. **Never push.**

---

## Task 1: Fingerprint + meta store

**Files:** Modify `drainworks_plugin/io/geopackage_store.py`; Test `tests/test_geopackage_meta.py`.

- [ ] **Step 1: Write the failing test** `tests/test_geopackage_meta.py`:
```python
from drainworks_plugin.io.geopackage_store import (
    base_fingerprint,
    berging_fingerprint,
    read_manholes,
    read_meta,
    read_pipes,
    write_base,
    write_meta,
)

import rgs_ribx
from rgs_ribx.model.raw import RawMeasurements


def _base(tmp_gpkg, bob2=-2.6):
    manholes = [rgs_ribx.Manhole(code="A", geometry_wkt="POINT (0 0)", ground_level=0.2),
                rgs_ribx.Manhole(code="B", geometry_wkt="POINT (30 0)", ground_level=0.1)]
    pipes = [rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="B", bob1=-2.0, bob2=bob2,
                           diameter=0.3, length=30.0, geometry_wkt="LINESTRING (0 0, 30 0)")]
    raw = {"L1": RawMeasurements("L1", "AA", reverse=False,
                                 points=[{"dist": 0.0, "value": 0.0}])}
    write_base(tmp_gpkg, manholes, pipes, raw)


def test_fingerprint_stable_and_changes_on_bob_edit(tmp_gpkg, tmp_path):
    _base(tmp_gpkg)
    fp1 = base_fingerprint(tmp_gpkg)
    assert fp1 == base_fingerprint(tmp_gpkg)        # stable
    other = tmp_path / "other.gpkg"
    _base(other, bob2=-3.0)
    assert base_fingerprint(other) != fp1           # a BOB change changes it


def test_berging_fingerprint_depends_on_sinks():
    assert berging_fingerprint("fp", ["A"]) == berging_fingerprint("fp", ["A"])
    assert berging_fingerprint("fp", ["A"]) != berging_fingerprint("fp", ["A", "B"])


def test_meta_roundtrip_and_merge(tmp_gpkg):
    _base(tmp_gpkg)
    assert read_meta(tmp_gpkg) == {}
    write_meta(tmp_gpkg, {"a": 1, "b": {"x": 2}})
    write_meta(tmp_gpkg, {"b": {"x": 3}, "c": [1, 2]})   # merge/replace
    assert read_meta(tmp_gpkg) == {"a": 1, "b": {"x": 3}, "c": [1, 2]}
```

- [ ] **Step 2: Run — expect fail** (`ImportError: ... base_fingerprint`):
`"$QGIS_PY" -m pytest tests/test_geopackage_meta.py -v`

- [ ] **Step 3: Add the helpers** at the END of `geopackage_store.py`:
```python
def _round6(value):
    return None if value is None else round(float(value), 6)


def base_fingerprint(path) -> str:
    """A stable SHA-1 over the base data that drives the enrich output."""
    import hashlib

    parts = []
    for p in sorted(read_pipes(path), key=lambda x: x.code or ""):
        parts.append(("P", p.code, p.manhole1, p.manhole2, _round6(p.bob1), _round6(p.bob2),
                      _round6(p.diameter), _round6(p.length), p.shape))
    raw = read_raw_measurements(path)
    for code in sorted(raw):
        rm = raw[code]
        for pt in sorted(rm.points, key=lambda d: d.get("dist") or 0.0):
            parts.append(("M", code, _round6(pt.get("dist")), _round6(pt.get("value")),
                          rm.measurement_type, rm.reverse))
    for m in sorted(read_manholes(path), key=lambda x: x.code or ""):
        parts.append(("K", m.code, _round6(m.ground_level), m.geometry_wkt is not None))
    return hashlib.sha1(repr(parts).encode("utf-8")).hexdigest()


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
```

- [ ] **Step 4: Run — expect pass:** `"$QGIS_PY" -m pytest tests/test_geopackage_meta.py -v`

- [ ] **Step 5: Commit**
```bash
git add drainworks_plugin/io/geopackage_store.py tests/test_geopackage_meta.py
git commit -m "feat: base_fingerprint + berging_fingerprint + dw_meta store"
```

---

## Task 2: PipelineState.restore

**Files:** Modify `drainworks_plugin/pipeline/state.py`; Test `tests/test_pipeline_state.py` (extend).

- [ ] **Step 1: Append the failing test** to `tests/test_pipeline_state.py`:
```python
def test_restore_sets_flags():
    s = PipelineState()
    s.restore(enrich_ran=True, enrich_fresh=True, berging_ran=True, berging_fresh=True)
    assert s.enrich_ran and not s.enrich_stale
    assert s.berging_ran and not s.berging_stale

    s.restore(enrich_ran=True, enrich_fresh=False, berging_ran=True, berging_fresh=False)
    assert s.enrich_stale and s.berging_stale      # ran but no longer fresh

    s.restore(enrich_ran=False, enrich_fresh=False, berging_ran=False, berging_fresh=False)
    assert s.enrich_stale and s.berging_stale      # not run -> needs running
    assert s.enrich_label() == "Verrijk basisdata"  # not run -> plain label
```

- [ ] **Step 2: Run — expect fail** (`AttributeError: ... restore`):
`"$QGIS_PY" -m pytest tests/test_pipeline_state.py::test_restore_sets_flags -v`

- [ ] **Step 3: Add `restore`** to `PipelineState` (after `mark_sinks_changed`):
```python
    def restore(self, enrich_ran, enrich_fresh, berging_ran, berging_fresh):
        """Set the flags from persisted state on load.

        A step that has not run, or whose stored output no longer matches the data,
        is stale (needs running).
        """
        self.imported = True
        self.enrich_ran = enrich_ran
        self.berging_ran = berging_ran
        self.enrich_stale = (not enrich_ran) or (not enrich_fresh)
        self.berging_stale = (not berging_ran) or (not berging_fresh)
```

- [ ] **Step 4: Run — expect pass:** `"$QGIS_PY" -m pytest tests/test_pipeline_state.py -v`

- [ ] **Step 5: Commit**
```bash
git add drainworks_plugin/pipeline/state.py tests/test_pipeline_state.py
git commit -m "feat: PipelineState.restore for load-time state"
```

---

## Task 3: Enrich writes its metadata

**Files:** Modify `drainworks_plugin/pipeline/enrich.py`; Test `tests/test_pipeline_enrich.py` (extend).

- [ ] **Step 1: Append the failing test** to `tests/test_pipeline_enrich.py`:
```python
def test_enrich_writes_meta(fixtures_dir, tmp_gpkg):
    import rgs_ribx
    from drainworks_plugin.io.geopackage_store import base_fingerprint, read_meta, write_base
    from drainworks_plugin.pipeline.enrich import enrich

    res = rgs_ribx.build_from_ribx(fixtures_dir / "inclined.ribx")
    write_base(tmp_gpkg, res.manholes, res.pipes, res.raw_measurements)
    enrich(tmp_gpkg, correct_bob=True, min_segment=2.0, bob_segment=4.0)
    meta = read_meta(tmp_gpkg)
    assert meta["enrich_fingerprint"] == base_fingerprint(tmp_gpkg)
    assert meta["enrich_settings"] == {"correct_bob": True, "min_segment": 2.0, "bob_segment": 4.0}
    assert "n_segments" in meta["enrich_summary"]
```

- [ ] **Step 2: Run — expect fail** (`KeyError: 'enrich_fingerprint'`):
`"$QGIS_PY" -m pytest tests/test_pipeline_enrich.py::test_enrich_writes_meta -v`

- [ ] **Step 3: Write the meta in `enrich`.** Find the end of `enrich` where it builds the
summary dict and `return`s it:
```python
    return {
        "n_profile_points": len(profile_rows),
        "n_segments": len(segment_rows),
        "n_pipes_with_issues": n_pipe_issues,
        "n_manholes_with_issues": n_manhole_issues,
        "n_errors": n_errors,
        "n_warnings": n_warnings,
    }
```
Replace with (assign to `summary`, write meta, return):
```python
    summary = {
        "n_profile_points": len(profile_rows),
        "n_segments": len(segment_rows),
        "n_pipes_with_issues": n_pipe_issues,
        "n_manholes_with_issues": n_manhole_issues,
        "n_errors": n_errors,
        "n_warnings": n_warnings,
    }
    from drainworks_plugin.io.geopackage_store import base_fingerprint, write_meta
    write_meta(gpkg_path, {
        "enrich_fingerprint": base_fingerprint(gpkg_path),
        "enrich_settings": {"correct_bob": correct_bob, "min_segment": min_segment,
                            "bob_segment": bob_segment},
        "enrich_summary": {"n_segments": summary["n_segments"], "n_errors": summary["n_errors"],
                           "n_warnings": summary["n_warnings"]},
    })
    return summary
```

- [ ] **Step 4: Run — expect pass:** `"$QGIS_PY" -m pytest tests/test_pipeline_enrich.py -v`

- [ ] **Step 5: Commit**
```bash
git add drainworks_plugin/pipeline/enrich.py tests/test_pipeline_enrich.py
git commit -m "feat: enrich writes base fingerprint + settings + summary to dw_meta"
```

---

## Task 4: Berging writes its metadata

**Files:** Modify `drainworks_plugin/pipeline/berging.py`; Test `tests/test_pipeline_berging.py` (extend).

- [ ] **Step 1: Append the failing test** to `tests/test_pipeline_berging.py`:
```python
def test_berging_writes_meta(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import (berging_fingerprint, read_meta,
                                                       total_lost_volume)
    _setup(tmp_gpkg)
    compute_berging(tmp_gpkg, resolution="fast")
    meta = read_meta(tmp_gpkg)
    assert meta["berging_settings"] == {"resolution": "fast"}
    assert meta["sinks"] == ["P1", "P2"]
    assert round(meta["berging_total"], 4) == round(total_lost_volume(tmp_gpkg), 4)
    assert meta["berging_fingerprint"] == berging_fingerprint(
        meta["enrich_fingerprint"], ["P1", "P2"])
```

- [ ] **Step 2: Run — expect fail** (`KeyError: 'berging_settings'`):
`"$QGIS_PY" -m pytest tests/test_pipeline_berging.py::test_berging_writes_meta -v`

- [ ] **Step 3: Write the meta in `compute_berging`.** Find the tail:
```python
    update_segments_berging(gpkg_path, updates)
    return len(segments)
```
Replace with:
```python
    update_segments_berging(gpkg_path, updates)
    from drainworks_plugin.io.geopackage_store import (
        berging_fingerprint, read_manholes, read_meta, total_lost_volume, write_meta)
    enrich_fp = read_meta(gpkg_path).get("enrich_fingerprint")
    sinks = sorted(m.code for m in read_manholes(gpkg_path) if m.is_sink)
    write_meta(gpkg_path, {
        "berging_fingerprint": berging_fingerprint(enrich_fp, sinks),
        "berging_settings": {"resolution": resolution},
        "berging_total": total_lost_volume(gpkg_path),
        "sinks": sinks,
    })
    return len(segments)
```

- [ ] **Step 4: Run — expect pass:** `"$QGIS_PY" -m pytest tests/test_pipeline_berging.py -v`

- [ ] **Step 5: Commit**
```bash
git add drainworks_plugin/pipeline/berging.py tests/test_pipeline_berging.py
git commit -m "feat: berging writes total + settings + sinks + fingerprint to dw_meta"
```

---

## Task 5: Busy messageBar item

**Files:** Create `drainworks_plugin/ui/busy.py`; modify `drainworks_plugin/ui/dock.py`, `drainworks_plugin/plugin.py`.

- [ ] **Step 1: Write `drainworks_plugin/ui/busy.py`:**
```python
"""A messageBar busy indicator with an indeterminate progress bar."""

from qgis.core import Qgis
from qgis.PyQt.QtWidgets import QProgressBar


def start_busy(iface, text):
    """Show a messageBar item with an animated (indeterminate) progress bar; returns it."""
    msg = iface.messageBar().createMessage("Drainworks", text)
    bar = QProgressBar()
    bar.setRange(0, 0)            # indeterminate / animated
    bar.setMaximumWidth(200)
    bar.setTextVisible(False)
    msg.layout().addWidget(bar)
    return iface.messageBar().pushWidget(msg, Qgis.Info)


def stop_busy(iface, item):
    """Remove a busy item (no-op if None)."""
    if item is not None:
        iface.messageBar().popWidget(item)
```

- [ ] **Step 2: Dock — show/hide the busy item around the task.** In `dock.py` `__init__`,
after `self.active_task = None` add `self._busy = None`. In `_run_task`, start the busy
item; the current method is:
```python
    def _run_task(self, task):
        """Submit a QgsTask to the task manager, disabling the step buttons."""
        from qgis.core import QgsApplication

        self.active_task = task
        for btn in (self.btn_enrich, self.btn_loss):
            btn.setEnabled(False)
        QgsApplication.taskManager().addTask(task)
```
Replace with:
```python
    def _run_task(self, task):
        """Submit a QgsTask to the task manager, disabling the step buttons."""
        from qgis.core import QgsApplication

        from drainworks_plugin.ui.busy import start_busy

        self.active_task = task
        self._busy = start_busy(self.iface, task.description() + "…")
        for btn in (self.btn_enrich, self.btn_loss):
            btn.setEnabled(False)
        QgsApplication.taskManager().addTask(task)
```
In both `_enrich_done` and `_loss_done`, at the very first line of the method body add:
```python
        from drainworks_plugin.ui.busy import stop_busy
        stop_busy(self.iface, self._busy)
        self._busy = None
```
(so the busy item is removed on success and error).

- [ ] **Step 3: Plugin — busy item for the import task.** In `plugin.py` `__init__`, after
`self._import_task = None` add `self._busy = None`. In `on_import`, where the import task is
created + added:
```python
        from qgis.core import QgsApplication

        from drainworks_plugin.pipeline.tasks import ImportTask

        self._import_task = ImportTask(input_path, meas_path or None, gpkg_path,
                                       on_done=self._import_done)
        QgsApplication.taskManager().addTask(self._import_task)
```
add a busy start before `addTask`:
```python
        from drainworks_plugin.ui.busy import start_busy

        self._import_task = ImportTask(input_path, meas_path or None, gpkg_path,
                                       on_done=self._import_done)
        self._busy = start_busy(self.iface, "Importeren…")
        QgsApplication.taskManager().addTask(self._import_task)
```
And in `_import_done`, at the first line add:
```python
        from drainworks_plugin.ui.busy import stop_busy
        stop_busy(self.iface, self._busy)
        self._busy = None
```

- [ ] **Step 4: Verify + commit.**
```
"$QGIS_PY" -m pytest
"$QGIS_PY" -c "import drainworks_plugin.ui.busy, drainworks_plugin.ui.dock, drainworks_plugin.plugin; print('ok')"
git add drainworks_plugin/ui/busy.py drainworks_plugin/ui/dock.py drainworks_plugin/plugin.py
git commit -m "feat: busy messageBar item (indeterminate progress) while a step runs"
```

---

## Task 6: Load-time state restore in the dock

**Files:** Modify `drainworks_plugin/ui/dock.py`.

- [ ] **Step 1: Replace the end of `set_data`.** The current tail is:
```python
        self._rebuild()
        self._set_data_enabled(True)
        self.enrich_summary.setText("")
        self.loss_total.setText("")
        self.state.mark_imported()
        self._refresh_step_buttons()
```
Replace with:
```python
        self._rebuild()
        self._set_data_enabled(True)
        self._restore_pipeline_state()
```

- [ ] **Step 2: Add `_restore_pipeline_state`** to the class:
```python
    def _restore_pipeline_state(self):
        """Set step state + summaries + settings from the gpkg's dw_meta + fingerprint."""
        from drainworks_plugin.io.geopackage_store import (
            base_fingerprint, berging_fingerprint, read_meta, read_segments)

        meta = read_meta(self.gpkg_path)
        fingerprint = base_fingerprint(self.gpkg_path)
        enriched = bool(read_segments(self.gpkg_path))
        enrich_fresh = enriched and meta.get("enrich_fingerprint") == fingerprint
        berging_ran = "berging_total" in meta
        berging_fresh = (
            berging_ran and enrich_fresh
            and meta.get("berging_fingerprint")
            == berging_fingerprint(meta.get("enrich_fingerprint"), self.sinks))
        self.state.restore(enrich_ran=enriched, enrich_fresh=enrich_fresh,
                           berging_ran=berging_ran, berging_fresh=berging_fresh)

        s = meta.get("enrich_summary") or {}
        if enriched and enrich_fresh:
            self.enrich_summary.setText(
                f"{s.get('n_segments', 0)} segmenten · {s.get('n_errors', 0)} fouten · "
                f"{s.get('n_warnings', 0)} waarschuwingen")
        else:
            self.enrich_summary.setText("")
        if berging_fresh:
            self.loss_total.setText(
                f"Totaal verloren berging: {meta.get('berging_total', 0.0):.2f} m³")
        else:
            self.loss_total.setText("")

        if meta.get("enrich_settings"):
            self._save_json_settings(self.ENRICH_SETTINGS_KEY, meta["enrich_settings"])
        if meta.get("berging_settings"):
            self._save_json_settings(self.BERGING_SETTINGS_KEY, meta["berging_settings"])
        self._refresh_step_buttons()
```

- [ ] **Step 3: Verify + commit.**
```
"$QGIS_PY" -m pytest
"$QGIS_PY" -c "import drainworks_plugin.ui.dock as d; print('ok', hasattr(d.DrainworksDock,'_restore_pipeline_state'))"
git add drainworks_plugin/ui/dock.py
git commit -m "feat: restore step state + summaries + settings from dw_meta on load"
```

---

## Task 7: End-to-end + construction smoke + manual check + finish

- [ ] **Step 1: Headless end-to-end of the meta round-trip + fingerprint staleness:**
```bash
"$QGIS_PY" -u -c "
import tempfile, os
from drainworks_plugin.pipeline.tasks import ImportTask, EnrichTask, BergingTask
from drainworks_plugin.io.geopackage_store import base_fingerprint, read_meta, set_sinks
out = os.path.join(tempfile.mkdtemp(), 'm.gpkg')
ImportTask('tests/fixtures/inclined.ribx', None, out).run()
EnrichTask(out, correct_bob=True).run()
m = read_meta(out)
print('enrich fresh:', m.get('enrich_fingerprint') == base_fingerprint(out))
set_sinks(out, ['P001'])
BergingTask(out, resolution='accurate').run()
m = read_meta(out)
print('has berging_total:', 'berging_total' in m, 'sinks:', m.get('sinks'))
# simulate a base edit by re-importing different data -> fingerprint differs
"
```
Expected: `enrich fresh: True` and `has berging_total: True sinks: [...]` (segfault harmless).

- [ ] **Step 2: Dock construction smoke** (state restore is exercised on real data; here just
confirm the dock builds and the method exists):
```bash
export QT_QPA_PLATFORM=offscreen
"$QGIS_PY" -u -c "
from qgis.core import QgsApplication
app = QgsApplication([], True); app.initQgis()
from qgis.PyQt.QtWidgets import QMainWindow
mw = QMainWindow()
p = type('P', (), {'iface': type('I', (), {'mainWindow': lambda self: mw})()})()
from drainworks_plugin.ui.dock import DrainworksDock
dock = DrainworksDock(p)
print('DOCK OK', hasattr(dock,'_restore_pipeline_state'), dock._busy)
"
```
Expected: `DOCK OK True None`.

- [ ] **Step 3: Full suite** — `"$QGIS_PY" -m pytest` → green.

- [ ] **Step 4: Manual QGIS check.** Import → Verrijk → Bereken; a busy message with a
running bar shows in the messageBar (top) during each step. Close and re-open the same
GeoPackage: both step cards show "✓ actueel" with their summary + total, and the gear
dialogs show the last-used settings. Edit a pipe BOB + commit: "Verrijk basisdata" flips to
"⚠ verouderd — verrijk opnieuw". Re-open after the edit: still shows verouderd (fingerprint
mismatch).

- [ ] **Step 5: Finish.** REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch`.
Do NOT push.
```
