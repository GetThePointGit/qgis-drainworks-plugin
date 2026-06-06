# Pipeline GUI + Async (C1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the new three-step pipeline (import → enrich → lost storage) drivable from the dock — three buttons, each running in a `QgsTask` with a progress bar — load and style the new `profile`/`segments` layers, track staleness, and retire the old `write_geopackage`/`runner.py`/`measurements` path.

**Architecture:** Split the work into a *testable core* and *GUI wiring*. The testable core (`import_to_base` step-1 function, a pure `PipelineState` staleness machine, and `QgsTask` subclasses whose `run()` is callable directly in a test) is built TDD. The GUI wiring (dock buttons + settings, `plugin.py` dispatch, layer loading/styling) ships complete code and is verified with a provided headless smoke script plus a manual QGIS check, because the repo has no `QgsApplication` test harness. The side-view's data source moves from `measurements` to `profile`/`segments`; C1 repoints it so it keeps working (visual rework is C2).

**Tech Stack:** PyQt5/`qgis.core`/`qgis.gui` (`QgsTask`, `QgsApplication.taskManager`, `QgsGraduatedSymbolRenderer`), `osgeo.ogr`, the Plan B store + `pipeline.enrich`/`pipeline.berging`, pytest.

**Spec:** `docs/superpowers/specs/2026-06-04-drainworks-1.0-refinements-design.md` (section 1, the data flow + async; the staleness/triggers).

**Repo:** `~/Documents/GitHub/qgis-drainworks-plugin`. Headless test/env recipe (use this exact prefix for every pytest/python command):
```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3" PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj" PROJ_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/proj" GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal" PYTHONPATH="/Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin:/Users/bastiaanroos/Documents/GitHub/rgs-ribx/src" && "$QGIS_PY" -m pytest <args>
```
A teardown segfault (exit 139) AFTER the pytest summary line is harmless; judge by the summary counts (run without `-q` if the segfault hides the summary).

> **Git (user rule):** never commit on `main`. Start with `git switch -c feature/pipeline-gui-async`. Never `git push`.

---

## File Structure

```
drainworks_plugin/
├── io/import_controller.py   # MODIFY: import_to_base() (step 1), load_pipeline_layers()
├── pipeline/
│   ├── state.py              # CREATE: PipelineState (staleness machine, pure)
│   └── tasks.py              # CREATE: ImportTask / EnrichTask / BergingTask (QgsTask)
├── styling/symbology.py      # MODIFY: style_segments(), style_profile()
├── ui/dock.py                # MODIFY: 3 step buttons + settings + staleness; repoint side-view
└── plugin.py                 # MODIFY: dispatch the three steps via tasks
# REMOVED at the end: lostcapacity/runner.py, write_geopackage path, old import funcs, measurements layer
```

---

## Task 1: Step-1 import to base (headless)

**Files:**
- Modify: `drainworks_plugin/io/import_controller.py`
- Test: `tests/test_import_to_base.py`

A pure (no-QGIS-layer) function that parses RIBX/SUFRIB and writes the step-1
base GeoPackage via `write_base`. This replaces the parsing+integration that the
old `_store_and_load` did (integration now happens in step 2/enrich).

- [ ] **Step 1: Write the failing test** `tests/test_import_to_base.py`:

```python
from drainworks_plugin.io.import_controller import import_to_base

import rgs_ribx  # noqa: F401  (import after the plugin module; see note)


def test_import_ribx_to_base_writes_layers(fixtures_dir, tmp_gpkg):
    out = import_to_base(str(fixtures_dir / "inclined.ribx"), None, str(tmp_gpkg))
    assert str(out) == str(tmp_gpkg)

    from osgeo import ogr
    ds = ogr.Open(str(tmp_gpkg))
    names = {ds.GetLayer(i).GetName() for i in range(ds.GetLayerCount())}
    assert {"manholes", "pipes", "measurements_raw"} <= names
    assert ds.GetLayerByName("measurements_raw").GetFeatureCount() == 3  # L001 BXA points


def test_import_to_base_no_heights_yet(fixtures_dir, tmp_gpkg):
    # Step 1 must NOT create profile/segments (those are step 2).
    import_to_base(str(fixtures_dir / "inclined.ribx"), None, str(tmp_gpkg))
    from osgeo import ogr
    ds = ogr.Open(str(tmp_gpkg))
    names = {ds.GetLayer(i).GetName() for i in range(ds.GetLayerCount())}
    assert "profile" not in names and "segments" not in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_import_to_base.py -v`
Expected: FAIL with `ImportError: cannot import name 'import_to_base'`.

- [ ] **Step 3: Add `import_to_base` to `drainworks_plugin/io/import_controller.py`.**
Add this function (near the top, after the imports). It dispatches by extension
and writes the base GeoPackage. It does NOT load any QGIS layers.

```python
def import_to_base(input_path, measurement_path, gpkg_path):
    """Parse RIBX/SUFRIB and write the step-1 base GeoPackage. Returns the path.

    Dispatches by extension: ``.rib``/``.hel`` -> SUFRIB (with optional
    ``measurement_path``), otherwise RIBX. No height integration, no segments —
    those are produced by step 2 (enrich).
    """
    from drainworks_plugin.io.geopackage_store import write_base

    lower = input_path.lower()
    if lower.endswith((".rib", ".hel")):
        paths = [input_path] + ([measurement_path] if measurement_path else [])
        result = rgs_ribx.build_from_sufrib(paths)
    else:
        result = rgs_ribx.build_from_ribx(input_path)
    return write_base(gpkg_path, result.manholes, result.pipes, result.raw_measurements)
```
(`import rgs_ribx` is already at the top of the file.)

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_import_to_base.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/io/import_controller.py tests/test_import_to_base.py
git commit -m "feat: import_to_base (step 1: parse + write_base)"
```

---

## Task 2: PipelineState staleness machine (headless)

**Files:**
- Create: `drainworks_plugin/pipeline/state.py`
- Test: `tests/test_pipeline_state.py`

A pure object tracking which steps are stale, so the dock can label buttons
("Verrijk opnieuw" / "Herbereken"). No QGIS imports.

- [ ] **Step 1: Write the failing test** `tests/test_pipeline_state.py`:

```python
from drainworks_plugin.pipeline.state import PipelineState


def test_fresh_import_marks_enrich_required():
    s = PipelineState()
    s.mark_imported()
    assert s.enrich_stale is True   # never enriched yet
    assert s.berging_stale is True


def test_enrich_then_berging_clears_staleness():
    s = PipelineState()
    s.mark_imported()
    s.mark_enriched()
    assert s.enrich_stale is False
    assert s.berging_stale is True  # enriched but not yet computed
    s.mark_berging_computed()
    assert s.berging_stale is False


def test_editing_base_marks_enrich_and_berging_stale():
    s = PipelineState()
    s.mark_imported(); s.mark_enriched(); s.mark_berging_computed()
    s.mark_base_edited()
    assert s.enrich_stale is True
    assert s.berging_stale is True


def test_changing_sinks_marks_only_berging_stale():
    s = PipelineState()
    s.mark_imported(); s.mark_enriched(); s.mark_berging_computed()
    s.mark_sinks_changed()
    assert s.enrich_stale is False
    assert s.berging_stale is True


def test_enrich_label_and_berging_label():
    s = PipelineState()
    s.mark_imported()
    assert s.enrich_label() == "Verrijk basisdata"   # never run -> plain
    s.mark_enriched(); s.mark_berging_computed()
    s.mark_base_edited()
    assert s.enrich_label() == "Verrijk opnieuw"
    assert s.berging_label() == "Herbereken"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_pipeline_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'drainworks_plugin.pipeline.state'`.

- [ ] **Step 3: Write `drainworks_plugin/pipeline/state.py`:**

```python
"""Pipeline staleness state machine (pure — no QGIS).

Tracks whether step 2 (enrich) and step 3 (berging) are up to date, so the dock
can label its buttons. ``enrich_ran``/``berging_ran`` record whether each step has
ever produced output; the *_stale flags say whether that output is current.
"""


class PipelineState:
    """Track enrich/berging staleness across edits."""

    def __init__(self):
        self.imported = False
        self.enrich_ran = False
        self.berging_ran = False
        self.enrich_stale = False
        self.berging_stale = False

    def mark_imported(self):
        """Fresh base data: enrich + berging both required."""
        self.imported = True
        self.enrich_ran = False
        self.berging_ran = False
        self.enrich_stale = True
        self.berging_stale = True

    def mark_enriched(self):
        """Step 2 produced profile/segments; berging now needs (re)computing."""
        self.enrich_ran = True
        self.enrich_stale = False
        self.berging_stale = True

    def mark_berging_computed(self):
        """Step 3 filled the segment berging fields."""
        self.berging_ran = True
        self.berging_stale = False

    def mark_base_edited(self):
        """Pipes/manholes were edited: both downstream steps are stale."""
        self.enrich_stale = True
        self.berging_stale = True

    def mark_sinks_changed(self):
        """Sinks changed: only the berging is affected."""
        self.berging_stale = True

    def enrich_label(self):
        """Button text for step 2 (stale + previously run -> 'opnieuw')."""
        return "Verrijk opnieuw" if (self.enrich_stale and self.enrich_ran) else "Verrijk basisdata"

    def berging_label(self):
        """Button text for step 3 (stale + previously run -> 'Herbereken')."""
        return "Herbereken" if (self.berging_stale and self.berging_ran) else "Bereken verloren berging"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_pipeline_state.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/pipeline/state.py tests/test_pipeline_state.py
git commit -m "feat: PipelineState staleness machine"
```

---

## Task 3: QgsTask wrappers (run() tested headless)

**Files:**
- Create: `drainworks_plugin/pipeline/tasks.py`
- Test: `tests/test_pipeline_tasks.py`

Three `QgsTask` subclasses wrapping the pure functions. Their `run()` does the
heavy work off-thread and can be called directly in a test; `finished(ok)` invokes
a plain callback (the dock supplies one that touches the GUI on the main thread).

- [ ] **Step 1: Write the failing test** `tests/test_pipeline_tasks.py`:

```python
from drainworks_plugin.io.geopackage_store import read_segments, write_base
from drainworks_plugin.pipeline.tasks import BergingTask, EnrichTask

import rgs_ribx
from rgs_ribx.model.raw import RawMeasurements


def _base(tmp_gpkg):
    manholes = [rgs_ribx.Manhole(code="P1", is_sink=True, geometry_wkt="POINT (0 0)"),
                rgs_ribx.Manhole(code="P2", is_sink=True, geometry_wkt="POINT (30 0)")]
    pipes = [rgs_ribx.Pipe(code="L1", manhole1="P1", manhole2="P2", bob1=-2.0, bob2=-2.0,
                           diameter=0.5, length=30.0, shape="A",
                           geometry_wkt="LINESTRING (0 0, 30 0)")]
    raw = {"L1": RawMeasurements("L1", "AA", reverse=False, points=[
        {"dist": 0.0, "value": 0.0}, {"dist": 10.0, "value": -0.3},
        {"dist": 20.0, "value": -0.3}, {"dist": 30.0, "value": 0.0}])}
    write_base(tmp_gpkg, manholes, pipes, raw)


def test_enrich_task_run_builds_segments(tmp_gpkg):
    _base(tmp_gpkg)
    task = EnrichTask(str(tmp_gpkg), correct_bob=False)
    assert task.run() is True
    assert task.result is not None and task.result["n_segments"] >= 1
    assert read_segments(str(tmp_gpkg))


def test_berging_task_run_fills_segments(tmp_gpkg):
    _base(tmp_gpkg)
    assert EnrichTask(str(tmp_gpkg), correct_bob=False).run() is True
    task = BergingTask(str(tmp_gpkg), resolution="accurate")
    assert task.run() is True
    assert any((s.get("flooded_pct") or 0) > 0 for s in read_segments(str(tmp_gpkg)))


def test_task_run_captures_error(tmp_gpkg):
    # Non-existent gpkg -> run() returns False and stores the exception.
    task = EnrichTask(str(tmp_gpkg) + ".missing", correct_bob=False)
    assert task.run() is False
    assert task.error is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_pipeline_tasks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'drainworks_plugin.pipeline.tasks'`.

- [ ] **Step 3: Write `drainworks_plugin/pipeline/tasks.py`:**

```python
"""QgsTask wrappers so the three pipeline steps run off the GUI thread.

Each task's ``run()`` does the heavy work (callable directly in tests) and stores
``result``/``error``; ``finished(ok)`` runs on the main thread and calls the
``on_done(task)`` callback the dock supplied (for layer loading + messages).
"""

from qgis.core import QgsTask

from drainworks_plugin.io.import_controller import import_to_base
from drainworks_plugin.pipeline.berging import compute_berging
from drainworks_plugin.pipeline.enrich import enrich


class _StepTask(QgsTask):
    """Base: run a callable, capture result/error, fire on_done on the main thread."""

    def __init__(self, description, on_done=None):
        super().__init__(description, QgsTask.CanCancel)
        self.on_done = on_done
        self.result = None
        self.error = None

    def _work(self):
        raise NotImplementedError

    def run(self):  # noqa: D401 (QGIS-required name) — executes off-thread
        try:
            self.result = self._work()
            return True
        except Exception as exc:  # captured; surfaced in finished()
            self.error = exc
            return False

    def finished(self, ok):  # noqa: D401 — main thread
        if self.on_done is not None:
            self.on_done(self)


class ImportTask(_StepTask):
    """Step 1: parse + write_base."""

    def __init__(self, input_path, measurement_path, gpkg_path, on_done=None):
        super().__init__("Drainworks: importeren", on_done)
        self._args = (input_path, measurement_path, gpkg_path)

    def _work(self):
        return import_to_base(*self._args)


class EnrichTask(_StepTask):
    """Step 2: validate + integrate + segments."""

    def __init__(self, gpkg_path, correct_bob=True, min_segment=None,
                 bob_segment=None, on_done=None):
        super().__init__("Drainworks: verrijken", on_done)
        self.gpkg_path = gpkg_path
        self._kwargs = {"correct_bob": correct_bob}
        if min_segment is not None:
            self._kwargs["min_segment"] = min_segment
        if bob_segment is not None:
            self._kwargs["bob_segment"] = bob_segment

    def _work(self):
        return enrich(self.gpkg_path, **self._kwargs)


class BergingTask(_StepTask):
    """Step 3: flood-fill + segment berging."""

    def __init__(self, gpkg_path, resolution="accurate", on_done=None):
        super().__init__("Drainworks: verloren berging", on_done)
        self.gpkg_path = gpkg_path
        self.resolution = resolution

    def _work(self):
        return compute_berging(self.gpkg_path, resolution=self.resolution)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_pipeline_tasks.py -v`
Expected: PASS (3 passed). (Importing `qgis.core.QgsTask` works headlessly; no
QgsApplication run loop is needed to call `run()` directly.)

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/pipeline/tasks.py tests/test_pipeline_tasks.py
git commit -m "feat: QgsTask wrappers for import/enrich/berging steps"
```

---

## Task 4: Segment + profile styling

**Files:**
- Modify: `drainworks_plugin/styling/symbology.py`
- Test: `tests/test_symbology_segments.py`

A graduated renderer on the `segments` layer's `flooded_pct` (so the layer-tree
legend shows the classes), and a simple profile-point style. This test imports
`qgis.core` and builds an in-memory layer — confirm it runs headlessly; if
`QgsApplication` is not initialised the test will guard-skip.

- [ ] **Step 1: Write the failing test** `tests/test_symbology_segments.py`:

```python
import pytest

from drainworks_plugin.styling.symbology import style_segments


def test_style_segments_applies_graduated_renderer():
    from qgis.core import QgsApplication, QgsGraduatedSymbolRenderer, QgsVectorLayer

    if QgsApplication.instance() is None:
        app = QgsApplication([], False)
        app.initQgis()

    layer = QgsVectorLayer(
        "LineString?crs=EPSG:28992&field=flooded_pct:double", "segments", "memory")
    assert layer.isValid()
    style_segments(layer)
    renderer = layer.renderer()
    assert isinstance(renderer, QgsGraduatedSymbolRenderer)
    assert renderer.classAttribute() == "flooded_pct"
    assert len(renderer.ranges()) >= 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_symbology_segments.py -v`
Expected: FAIL with `ImportError: cannot import name 'style_segments'`.

- [ ] **Step 3: Add `style_segments` and `style_profile` to `drainworks_plugin/styling/symbology.py`** (append). `style_segments` mirrors the existing `style_berging_lines` graduated pattern but targets the `segments` layer:

```python
def style_segments(layer) -> None:
    """Graduated blue->red LINE renderer on the ``flooded_pct`` field (0..1).

    Uses a graduated renderer so the layer-tree legend shows the flood classes.
    """
    ranges = []
    steps = [
        (0.0, 0.25, FLOODED_LOW, "0.8"),
        (0.25, 0.5, "#7fcdbb", "1.4"),
        (0.5, 0.75, "#fec44f", "2.2"),
        (0.75, 1.01, FLOODED_HIGH, "3.0"),
    ]
    for lower, upper, hex_color, width in steps:
        symbol = QgsLineSymbol.createSimple({"color": hex_color, "width": width})
        symbol.setColor(QColor(hex_color))
        label = f"{int(lower * 100)}–{int(min(upper, 1.0) * 100)}%"
        ranges.append(QgsRendererRange(lower, upper, symbol, label))
    renderer = QgsGraduatedSymbolRenderer("flooded_pct", ranges)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def style_profile(layer) -> None:
    """Render the detailed profile points as small grey dots."""
    symbol = QgsMarkerSymbol.createSimple(
        {"name": "circle", "color": "#9e9e9e", "size": "1.4",
         "outline_style": "no"})
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.triggerRepaint()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_symbology_segments.py -v`
Expected: PASS (1 passed). If it ERRORs at `QgsApplication([],...)` initialisation
in this environment, wrap the body in `pytest.skip("needs QgsApplication")` via a
try/except around `initQgis()` and report that the renderer is instead verified in
the Task 8 manual QGIS smoke check — do NOT delete the assertions.

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/styling/symbology.py tests/test_symbology_segments.py
git commit -m "feat: style_segments (graduated) + style_profile"
```

---

## Task 5: Layer loading for the pipeline (GUI wiring)

**Files:**
- Modify: `drainworks_plugin/io/import_controller.py`

Add `load_pipeline_layers(gpkg)` that loads manholes/pipes and — when present —
`profile` + `segments`, styled, into a named group. This is GUI code (uses
`qgis.core`); it is verified by the Task 8 smoke script (no pytest).

- [ ] **Step 1: Add `load_pipeline_layers` to `drainworks_plugin/io/import_controller.py`:**

```python
def load_pipeline_layers(gpkg_path):
    """Load manholes/pipes (+ profile/segments if present) into a styled group.

    Returns ``(manhole_layer, pipe_layer, group, segments_layer_or_None)``.
    """
    from drainworks_plugin.styling.symbology import (
        style_manholes,
        style_pipes,
        style_profile,
        style_segments,
    )

    gpkg_path = Path(gpkg_path)
    pipe_layer = QgsVectorLayer(f"{gpkg_path}|layername=pipes", "Leidingen", "ogr")
    manhole_layer = QgsVectorLayer(f"{gpkg_path}|layername=manholes", "Putten", "ogr")
    if not pipe_layer.isValid() or not manhole_layer.isValid():
        raise RuntimeError(f"Could not load layers from {gpkg_path}")
    style_pipes(pipe_layer)
    style_manholes(manhole_layer)

    project = QgsProject.instance()
    # Replace any group of the same name from a previous run.
    root = project.layerTreeRoot()
    existing = root.findGroup(gpkg_path.stem)
    if existing is not None:
        for child in list(existing.findLayers()):
            project.removeMapLayer(child.layerId())
        root.removeChildNode(existing)
    group = root.insertGroup(0, gpkg_path.stem)

    segments_layer = QgsVectorLayer(f"{gpkg_path}|layername=segments", "Segmenten", "ogr")
    profile_layer = QgsVectorLayer(f"{gpkg_path}|layername=profile", "Profielpunten", "ogr")
    if segments_layer.isValid() and segments_layer.featureCount() >= 0:
        style_segments(segments_layer)
    if profile_layer.isValid():
        style_profile(profile_layer)

    # Draw order top->bottom: manholes, pipes, segments, profile.
    ordered = [manhole_layer, pipe_layer]
    if segments_layer.isValid():
        ordered.append(segments_layer)
    if profile_layer.isValid():
        ordered.append(profile_layer)
    for layer in ordered:
        project.addMapLayer(layer, False)
        group.addLayer(layer)
    return manhole_layer, pipe_layer, group, (segments_layer if segments_layer.isValid() else None)
```

- [ ] **Step 2: Commit** (no isolated test — exercised by Task 8 smoke):

```bash
git add drainworks_plugin/io/import_controller.py
git commit -m "feat: load_pipeline_layers (manholes/pipes/segments/profile, styled)"
```

---

## Task 6: Dock — three step buttons + settings + staleness (GUI wiring)

**Files:**
- Modify: `drainworks_plugin/ui/dock.py`
- Modify: `drainworks_plugin/plugin.py`

Replace the single "Bereken berging" flow with three step buttons driven by
`PipelineState`, plus a settings row (Corrigeer BOB / segment lengths / resolutie).
Repoint the side-view feed from the old `measurements` to the new `profile` layer.
Keep the trajectory table and sink section as-is (C2 reworks them).

> This is the largest wiring change. The code below shows the exact methods to add
> or replace; leave all other dock methods untouched.

- [ ] **Step 1: Add the step-button row + settings in `_build_ui`.** Find the action
row block (the `actions` `QHBoxLayout` that adds `btn_import`, `btn_traj`,
`btn_downstream`, `btn_style`) and, immediately AFTER `left_layout.addLayout(actions)`,
insert a step row + settings:

```python
        # --- Pipeline step buttons (import -> enrich -> berging). ---
        steps = QHBoxLayout()
        self.btn_enrich = self._tool_button("Verrijk basisdata", "lost_capacity.svg",
                                            self._on_enrich)
        steps.addWidget(self.btn_enrich)
        steps.addStretch()
        left_layout.addLayout(steps)

        from qgis.PyQt.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox
        settings = QHBoxLayout()
        self.chk_correct_bob = QCheckBox("Corrigeer BOB")
        self.chk_correct_bob.setChecked(True)
        self.cmb_resolution = QComboBox()
        self.cmb_resolution.addItems(["nauwkeurig", "snel"])
        settings.addWidget(self.chk_correct_bob)
        settings.addWidget(QLabel("Resolutie:"))
        settings.addWidget(self.cmb_resolution)
        left_layout.addLayout(settings)

        seg_settings = QHBoxLayout()
        self.spn_min_segment = QDoubleSpinBox(); self.spn_min_segment.setRange(0.1, 50.0)
        self.spn_min_segment.setValue(1.0); self.spn_min_segment.setSuffix(" m")
        self.spn_bob_segment = QDoubleSpinBox(); self.spn_bob_segment.setRange(0.5, 100.0)
        self.spn_bob_segment.setValue(5.0); self.spn_bob_segment.setSuffix(" m")
        seg_settings.addWidget(QLabel("Segment:"))
        seg_settings.addWidget(self.spn_min_segment)
        seg_settings.addWidget(QLabel("BOB-seg:"))
        seg_settings.addWidget(self.spn_bob_segment)
        left_layout.addLayout(seg_settings)
```

- [ ] **Step 2: Add the `PipelineState` to `__init__`.** In `DrainworksDock.__init__`,
after `self.computed_sinks = None`, add:

```python
        from drainworks_plugin.pipeline.state import PipelineState
        self.state = PipelineState()
        self.active_task = None  # the running QgsTask, if any
```

- [ ] **Step 3: Replace `_on_loss` and add `_on_enrich` + step dispatch.** Replace the
existing `_on_loss` method body with the new three-step handlers. Replace:

```python
    def _on_loss(self):
        if not self.sinks:
            self.iface.messageBar().pushWarning("Drainworks", "Kies eerst minimaal één sink.")
            return
        from drainworks_plugin.io.geopackage_store import read_measurements, set_sinks

        # Persist the chosen sinks only now (at computation time), then compute.
        if self.gpkg_path:
            set_sinks(self.gpkg_path, self.sinks)
        self.plugin.on_compute_loss()
        self.computed_sinks = set(self.sinks)
        if self.gpkg_path:
            self.measurements_by_pipe = read_measurements(self.gpkg_path)
        self._update_berging_button()
        self._rebuild()
```
with:

```python
    def _on_enrich(self):
        """Step 2: enrich the (possibly edited) base data, off-thread."""
        if not self.gpkg_path:
            self.iface.messageBar().pushWarning("Drainworks", "Importeer eerst data.")
            return
        from drainworks_plugin.pipeline.tasks import EnrichTask

        task = EnrichTask(self.gpkg_path,
                          correct_bob=self.chk_correct_bob.isChecked(),
                          min_segment=self.spn_min_segment.value(),
                          bob_segment=self.spn_bob_segment.value(),
                          on_done=self._enrich_done)
        self._run_task(task)

    def _enrich_done(self, task):
        if task.error is not None:
            self.iface.messageBar().pushCritical("Drainworks", f"Verrijken mislukt: {task.error}")
            self.active_task = None
            return
        self.state.mark_enriched()
        s = task.result or {}
        self.plugin.reload_pipeline_layers()
        self._reload_profile()
        self._refresh_step_buttons()
        self.active_task = None
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Verrijkt: {s.get('n_segments', 0)} segmenten, "
            f"{s.get('n_pipes_with_issues', 0)} leidingen met problemen.")

    def _on_loss(self):
        """Step 3: compute lost storage with the chosen sinks, off-thread."""
        if not self.gpkg_path:
            self.iface.messageBar().pushWarning("Drainworks", "Importeer eerst data.")
            return
        if not self.sinks:
            self.iface.messageBar().pushWarning("Drainworks", "Kies eerst minimaal één sink.")
            return
        if self.state.enrich_stale:
            self.iface.messageBar().pushWarning(
                "Drainworks", "Verrijk eerst de basisdata (stap 2).")
            return
        from drainworks_plugin.io.geopackage_store import set_sinks
        from drainworks_plugin.pipeline.tasks import BergingTask

        set_sinks(self.gpkg_path, self.sinks)
        resolution = "accurate" if self.cmb_resolution.currentIndex() == 0 else "fast"
        task = BergingTask(self.gpkg_path, resolution=resolution, on_done=self._loss_done)
        self._run_task(task)

    def _loss_done(self, task):
        if task.error is not None:
            self.iface.messageBar().pushCritical("Drainworks", f"Berekening mislukt: {task.error}")
            self.active_task = None
            return
        self.state.mark_berging_computed()
        self.computed_sinks = set(self.sinks)
        self.plugin.reload_pipeline_layers()
        self._refresh_step_buttons()
        self._rebuild()
        self.active_task = None
        self.iface.messageBar().pushSuccess(
            "Drainworks", f"Verloren berging berekend ({task.result} segmenten).")

    def _run_task(self, task):
        """Submit a QgsTask to the task manager, disabling the step buttons."""
        from qgis.core import QgsApplication

        self.active_task = task
        for btn in (self.btn_enrich, self.btn_loss):
            btn.setEnabled(False)
        QgsApplication.taskManager().addTask(task)

    def _refresh_step_buttons(self):
        """Re-enable + relabel the step buttons from the PipelineState."""
        self.btn_enrich.setEnabled(self.gpkg_path is not None)
        self.btn_loss.setEnabled(self.gpkg_path is not None)
        self.btn_enrich.setText(self.state.enrich_label())
        self.btn_enrich.setStyleSheet(
            "color: #c54141; font-weight: bold;" if self.state.enrich_stale and self.state.enrich_ran else "")
        self.btn_loss.setText(self.state.berging_label())
        self.btn_loss.setStyleSheet(
            "color: #c54141; font-weight: bold;" if self.state.berging_stale and self.state.berging_ran else "")
```

- [ ] **Step 4: Repoint the side-view feed + sinks staleness.** In `set_data`, replace
the `read_measurements` import and call so the side-view reads the `profile` layer
(converted to the dict shape `build_profile` expects). Change the import block:
```python
        from drainworks_plugin.io.geopackage_store import (
            read_manhole_points,
            read_manholes,
            read_measurements,
            read_pipes,
        )
```
to:
```python
        from drainworks_plugin.io.geopackage_store import (
            read_manhole_points,
            read_manholes,
            read_pipes,
        )
```
and change `self.measurements_by_pipe = read_measurements(self.gpkg_path)` to:
```python
        self.measurements_by_pipe = self._read_profile_for_sideview()
```
Then add the helper method (reads `profile` MeasurementPoints into the dict shape;
flood fields come from `segments`, not points, so they are None here — the
side-view's flood overlay is re-added in C2):
```python
    def _read_profile_for_sideview(self):
        """Read the profile layer into {code: [dict(dist,bob,obb,flooded_pct,water_level)]}."""
        if not self.gpkg_path:
            return {}
        from drainworks_plugin.io.geopackage_store import read_profile
        out = {}
        for code, points in read_profile(self.gpkg_path).items():
            out[code] = [{"dist": p.dist, "bob": p.bob, "obb": p.obb,
                          "flooded_pct": None, "water_level": None} for p in points]
        return out

    def _reload_profile(self):
        self.measurements_by_pipe = self._read_profile_for_sideview()
        self._rebuild()
```
Also, at the end of `set_data`, after `self._set_data_enabled(True)`, add:
```python
        self.state.mark_imported()
        self._refresh_step_buttons()
```
And in `_apply_sinks`, after `self._update_berging_button()`, add `self.state.mark_sinks_changed()` and `self._refresh_step_buttons()`.

- [ ] **Step 5: Add `reload_pipeline_layers` to `plugin.py`** so the dock can refresh
the styled layers after a step. Add this method to `DrainworksPlugin`:
```python
    def reload_pipeline_layers(self):
        """Reload + restyle the GeoPackage layers (after enrich/berging)."""
        if not self.gpkg_path:
            return
        from drainworks_plugin.io.import_controller import load_pipeline_layers
        manhole_layer, pipe_layer, group, _segments = load_pipeline_layers(self.gpkg_path)
        self.manhole_layer = manhole_layer
        self.pipe_layer = pipe_layer
        self.layer_group = group
        if self.dock is not None:
            self.dock.manhole_layer = manhole_layer
            self.dock.pipe_layer = pipe_layer
        self.iface.mapCanvas().refresh()
```

- [ ] **Step 6: Point `plugin.on_import` at the step-1 task.** Replace the body of
`on_import` so it imports via `import_to_base` then loads with `load_pipeline_layers`.
Replace the dispatch try/except (the `if lower.endswith(".gpkg") ... import_ribx/import_sufrib`
block) with:
```python
        try:
            if lower.endswith(".gpkg"):
                gpkg_out = input_path
            else:
                from drainworks_plugin.io.import_controller import import_to_base
                import_to_base(input_path, meas_path or None, gpkg_path)
                gpkg_out = gpkg_path
            from drainworks_plugin.io.import_controller import load_pipeline_layers
            manhole_layer, pipe_layer, group, _segments = load_pipeline_layers(gpkg_out)
        except Exception as exc:
            self.iface.messageBar().pushCritical("Drainworks", f"Import failed: {exc}")
            return
        self.gpkg_path = gpkg_out
```
(Delete the now-unused `self.gpkg_path = input_path if ... else gpkg_path` line below;
keep the `self.manhole_layer/pipe_layer/layer_group` assignments, the zoom, and the
`self.dock.set_data(...)` + message.)

- [ ] **Step 7: Manual + smoke verification.** Run the existing suite to confirm no
import-time breakage of the dock module:
```bash
"$QGIS_PY" -m pytest -q
```
Expected: all currently-passing tests still pass (the dock/plugin modules import
cleanly). Full GUI behaviour is verified in Task 8.

- [ ] **Step 8: Commit**

```bash
git add drainworks_plugin/ui/dock.py drainworks_plugin/plugin.py
git commit -m "feat: dock three-step buttons + settings + async tasks; repoint side-view to profile"
```

---

## Task 7: Remove the old single-shot path

**Files:**
- Delete: `drainworks_plugin/lostcapacity/runner.py`
- Modify: `drainworks_plugin/io/geopackage_store.py` (remove `write_geopackage`, `_write_measurements`, `_fill_measurement_feature`, `replace_measurements`, `read_measurements`, `MeasurementRow`, `write_berging_lines` IF now unused)
- Modify: `drainworks_plugin/io/import_controller.py` (remove `import_ribx`, `import_sufrib`, `_store_and_load`, `load_geopackage_layers` if unused)
- Modify: `drainworks_plugin/plugin.py` (remove `on_compute_loss`)
- Delete: `tests/test_lostcapacity_runner.py`
- Modify: `tests/test_geopackage_store.py` (drop tests of removed `write_geopackage`/`measurements`)

> Removing code that this plan replaced. Per the user's rule on not silently
> changing test outcomes: the deleted tests cover deleted functions only. Before
> deleting each symbol, grep to confirm nothing still imports it.

- [ ] **Step 1: Grep for remaining references**

Run:
```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin
grep -rn "compute_and_store\|write_geopackage\|read_measurements\|replace_measurements\|MeasurementRow\|import_ribx\|import_sufrib\|load_geopackage_layers\|on_compute_loss\|write_berging_lines\|style_berging_lines\|style_measurements_by_flooded" drainworks_plugin tests | grep -v "\.pyc"
```
Note every hit. Anything in `drainworks_plugin/` (not a definition) must be removed
or repointed before deleting the definition.

- [ ] **Step 2: Delete `drainworks_plugin/lostcapacity/runner.py` and `tests/test_lostcapacity_runner.py`.**

```bash
git rm drainworks_plugin/lostcapacity/runner.py tests/test_lostcapacity_runner.py
```

- [ ] **Step 3: Remove the now-unused functions** from `geopackage_store.py` and
`import_controller.py` that the grep in Step 1 confirmed are unreferenced
(`write_geopackage`, `_write_measurements`, `_fill_measurement_feature`,
`replace_measurements`, `read_measurements`, `MeasurementRow`, `import_ribx`,
`import_sufrib`, `_store_and_load`, `load_geopackage_layers`). Keep
`point_along_wkt`/`linestring_substring_wkt`/`_manhole_bottom_levels`/`add_layer_to_group`
(still used). If `write_berging_lines`/`style_berging_lines`/`style_measurements_by_flooded`
are now unreferenced, remove them too; if still referenced, leave them.

- [ ] **Step 4: Remove `on_compute_loss` from `plugin.py`** (the dock now uses tasks).

- [ ] **Step 5: Trim `tests/test_geopackage_store.py`** — delete the test functions
that call `write_geopackage`/`MeasurementRow`/`read_measurements`
(`test_write_creates_three_layers`, `test_measurements_written_and_typed`, and adjust
`test_set_sinks_flags_only_chosen`/`test_pipe_roundtrip_preserves_attributes` to use
`write_base(..., raw_measurements={})` instead of `write_geopackage(..., measurements=[])`).

- [ ] **Step 6: Run the full suite**

Run: `"$QGIS_PY" -m pytest -q`
Expected: green. Investigate any failure — a failure here means something still
references a removed symbol; repoint or restore it, don't silence the test.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove old write_geopackage/runner/measurements path"
```

---

## Task 8: Headless smoke + manual QGIS check + finish

**Files:**
- Create: `scripts/smoke_pipeline.py`

A headless script that drives the full pipeline through the task layer on the
example GeoPackage, to verify the GUI-adjacent code (tasks + enrich/berging) end
to end without a running QGIS GUI.

- [ ] **Step 1: Write `scripts/smoke_pipeline.py`:**

```python
"""Headless smoke test of the 3-step pipeline via the QgsTask wrappers.

Run with the QGIS-LTR2 python and the PROJ/GDAL env (see the plan header).
Usage: python -u scripts/smoke_pipeline.py path/to/input.ribx /tmp/out.gpkg
"""

import sys

from drainworks_plugin.pipeline.tasks import BergingTask, EnrichTask, ImportTask
from drainworks_plugin.io.geopackage_store import read_segments


def main(input_path, gpkg_path):
    t1 = ImportTask(input_path, None, gpkg_path)
    assert t1.run(), f"import failed: {t1.error}"
    print("imported ->", t1.result, flush=True)

    t2 = EnrichTask(gpkg_path, correct_bob=True)
    assert t2.run(), f"enrich failed: {t2.error}"
    print("enriched ->", t2.result, flush=True)

    t3 = BergingTask(gpkg_path, resolution="accurate")
    assert t3.run(), f"berging failed: {t3.error}"
    segs = read_segments(gpkg_path)
    flooded = [s for s in segs if (s.get("flooded_pct") or 0) > 0]
    print(f"berging -> {t3.result} segments, {len(flooded)} flooded", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

- [ ] **Step 2: Run the smoke script** on the inclined fixture:

```bash
"$QGIS_PY" -u scripts/smoke_pipeline.py tests/fixtures/inclined.ribx /tmp/dw_smoke.gpkg
```
Expected: prints "imported ->", "enriched -> {...}", "berging -> N segments, M flooded".
A trailing exit-139 segfault after the prints is harmless.

- [ ] **Step 3: Manual QGIS check (record the result in the commit message).** In QGIS
with the plugin loaded: Importeren a `.ribx`/`.rib` → Verrijk basisdata (watch the
progress bar; segments/profile layers appear, legend shows flood classes once berging
runs) → pick a sink → Bereken verloren berging (progress bar; segments colour by
flooded_pct; "Herbereken" appears after editing a BOB + committing). Confirm the dock
doesn't freeze during the steps.

- [ ] **Step 4: Run the full suite once more**

Run: `"$QGIS_PY" -m pytest -q`
Expected: green.

- [ ] **Step 5: Commit + finish the branch**

```bash
git add scripts/smoke_pipeline.py
git commit -m "test: headless pipeline smoke script"
```
Then REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch`. Do NOT push.

---

## Notes for the follow-up plan (C2 — UX refinements)

- Trajectory: letter-in-circle markers, wide semi-transparent band, active-point
  highlight, ctrl-click delete + delete-mode, contextual button row, remove the table.
- Side-view: remove the "Langsprofiel" label; gear settings (legend position, white
  bg, line colour/width, show putcodes, reset; persistent via QgsSettings); put as a
  vertical bottom→maaiveld line excluded from auto-zoom; **live BOB-line update** during
  map editing (pipe bob1/bob2) with the detailed `profile` loaded only when the
  trajectory is finalised; re-add the per-point/segment flood overlay + route volume
  reading from `segments`.
- Sinks: table with per-row delete (replacing the label) + "+" icon button.
- Opmaak: brush icon; the graduated renderer (already used for segments) so the layer
  legend updates.
```
