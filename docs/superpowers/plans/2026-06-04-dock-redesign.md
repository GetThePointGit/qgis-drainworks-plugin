# Dock Redesign (C3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-group the Drainworks dock into a compact main toolbar, a file-info line, two collapsible step cards (each with a wide action button, a ⚙ settings popup, an up-to-date indicator and a summary), and the trajectory edit buttons relocated above the longitudinal profile.

**Architecture:** Mostly a `ui/dock.py` reorganisation built on the existing pipeline. Three supporting pieces are extracted as testable units first: a validation **severity split** in `rgs-ribx` (so the card can show "fouten" vs "waarschuwingen"), and two `geopackage_store` helpers (`layer_counts`, `total_lost_volume`). The dock then gets per-step settings popups (persisted via QgsSettings) and `QgsCollapsibleGroupBox` cards. GUI wiring is verified by import-smoke + the existing headless tests + a manual QGIS check (no QgsApplication GUI-interaction harness).

**Tech Stack:** PyQt5 / `qgis.core` / `qgis.gui` (`QgsCollapsibleGroupBox`, `QgsSettings`), `osgeo.ogr`, `rgs_ribx`, pytest.

**Spec:** `docs/superpowers/specs/2026-06-04-dock-redesign-design.md`.

**Two repos:** Task 1 is in **`~/Documents/GitHub/rgs-ribx`** (branch `feature/validation-severity`, merge to its `main` when done so the plugin sees it). Tasks 2–6 are in **`~/Documents/GitHub/qgis-drainworks-plugin`** (branch `feature/dock-redesign`).

**Test commands:**
- rgs-ribx: `cd ~/Documents/GitHub/rgs-ribx && .venv/bin/python -m pytest` and `.venv/bin/ruff check src tests`.
- plugin (headless, prefix every command):
```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3" PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj" PROJ_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/proj" GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal" PYTHONPATH="/Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin:/Users/bastiaanroos/Documents/GitHub/rgs-ribx/src" && "$QGIS_PY" -m pytest <args>
```
A plugin teardown segfault (exit 139) AFTER the pytest summary is harmless; run without `-q` if it hides the summary.

> **Git (user rule):** never commit on `main`; feature branch per repo. Never `git push`.

---

## File Structure

```
rgs-ribx/src/rgs_ribx/model/validation.py   # MODIFY: Issue(str) + severity tags
drainworks_plugin/
├── io/geopackage_store.py                   # MODIFY: layer_counts(), total_lost_volume()
├── pipeline/enrich.py                       # MODIFY: summary n_errors/n_warnings
├── ui/enrich_settings_dialog.py             # CREATE: enrich ⚙ dialog
├── ui/berging_settings_dialog.py            # CREATE: berging ⚙ dialog
└── ui/dock.py                               # MODIFY: toolbar + file-info + collapsible cards + traj bar above graph
```

---

## Task 1: Validation severity split (rgs-ribx)

**Repo:** `~/Documents/GitHub/rgs-ribx` (branch `feature/validation-severity`).
**Files:**
- Modify: `src/rgs_ribx/model/validation.py`
- Test: `tests/test_validation.py` (extend)

Tag each issue with `error` or `warning` via an `Issue` string subclass, so existing
string-based callers/tests keep working unchanged while the severity is available.

- [ ] **Step 1: Create the branch**

```bash
cd ~/Documents/GitHub/rgs-ribx && git switch -c feature/validation-severity
```

- [ ] **Step 2: Write the failing test** — append to `tests/test_validation.py`:

```python
def test_issues_carry_severity():
    import rgs_ribx
    manholes = [rgs_ribx.Manhole(code="A", geometry_wkt="POINT (0 0)")]
    pipes = [
        rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="Z", bob1=-2.0, bob2=None,
                      diameter=5.0, length=30.0),
    ]
    result = rgs_ribx.validate_network(manholes, pipes)
    issues = result["pipes"]["L1"]
    sev = {str(i): i.severity for i in issues}
    # missing bob2 + dangling manhole2 are errors; diameter out of range is a warning
    assert sev["BOB ontbreekt (begin of eind)"] == "error"
    assert any(s == "error" for k, s in sev.items() if "Knooppunt" in k)
    assert any(s == "warning" for k, s in sev.items() if "Diameter buiten bereik" in k)
    # still plain strings (backward compatible)
    assert "; ".join(issues)  # joinable
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_validation.py::test_issues_carry_severity -v`
Expected: FAIL — `AttributeError: 'str' object has no attribute 'severity'`.

- [ ] **Step 4: Implement in `src/rgs_ribx/model/validation.py`.** Add the `Issue`
class near the top (after the constants):

```python
class Issue(str):
    """A validation message that also carries a severity.

    Subclasses ``str`` so existing callers that join/compare the messages keep
    working; ``severity`` is ``"error"`` (missing/unknown required data) or
    ``"warning"`` (a value outside its expected range).
    """

    def __new__(cls, message, severity="error"):
        obj = super().__new__(cls, message)
        obj.severity = severity
        return obj
```

Then wrap every appended message with `Issue(...)` and the right severity. Replace
the pipe loop's appends:
```python
        if not p.code:
            issues.append("Leidingcode ontbreekt")
        if p.bob1 is None or p.bob2 is None:
            issues.append("BOB ontbreekt (begin of eind)")
        if p.diameter is None:
            issues.append("Diameter ontbreekt")
        else:
            d_mm = p.diameter * 1000.0
            if d_mm < DIAMETER_MIN_MM or d_mm > DIAMETER_MAX_MM:
                issues.append(f"Diameter buiten bereik ({d_mm:.0f} mm)")
        for ref in (p.manhole1, p.manhole2):
            if not ref or ref not in manhole_codes:
                issues.append(f"Knooppunt ontbreekt of onbekend ({ref!r})")
        ml = measured_length.get(p.code)
        if ml is not None and p.length:
            if abs(ml - p.length) > LENGTH_TOLERANCE * p.length:
                issues.append(
                    f"Meetlengte wijkt af (gemeten {ml:.1f} m vs {p.length:.1f} m)"
                )
```
with:
```python
        if not p.code:
            issues.append(Issue("Leidingcode ontbreekt", "error"))
        if p.bob1 is None or p.bob2 is None:
            issues.append(Issue("BOB ontbreekt (begin of eind)", "error"))
        if p.diameter is None:
            issues.append(Issue("Diameter ontbreekt", "error"))
        else:
            d_mm = p.diameter * 1000.0
            if d_mm < DIAMETER_MIN_MM or d_mm > DIAMETER_MAX_MM:
                issues.append(Issue(f"Diameter buiten bereik ({d_mm:.0f} mm)", "warning"))
        for ref in (p.manhole1, p.manhole2):
            if not ref or ref not in manhole_codes:
                issues.append(Issue(f"Knooppunt ontbreekt of onbekend ({ref!r})", "error"))
        ml = measured_length.get(p.code)
        if ml is not None and p.length:
            if abs(ml - p.length) > LENGTH_TOLERANCE * p.length:
                issues.append(Issue(
                    f"Meetlengte wijkt af (gemeten {ml:.1f} m vs {p.length:.1f} m)", "warning"))
```
And the manhole loop appends:
```python
        if not m.code:
            issues.append(Issue("Putcode ontbreekt", "error"))
        if m.geometry_wkt is None:
            issues.append(Issue("Geometrie ontbreekt", "error"))
```

- [ ] **Step 5: Run the full rgs-ribx suite + ruff**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src tests`
Expected: all green (the existing string-based `test_validation.py` assertions still
pass because `Issue` is a `str`).

- [ ] **Step 6: Commit + merge to rgs-ribx main (so the plugin picks it up)**

```bash
cd ~/Documents/GitHub/rgs-ribx
git add src/rgs_ribx/model/validation.py tests/test_validation.py
git commit -m "feat: tag validation issues with error/warning severity"
git checkout main && git merge --no-ff feature/validation-severity -m "Merge feature/validation-severity"
.venv/bin/python -m pytest -q
git branch -d feature/validation-severity
```
Do NOT push.

---

## Task 2: Store helpers — layer_counts + total_lost_volume

**Repo:** plugin (branch `feature/dock-redesign`).
**Files:**
- Modify: `drainworks_plugin/io/geopackage_store.py`
- Test: `tests/test_geopackage_counts.py`

- [ ] **Step 1: Create the plugin branch**

```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && git switch -c feature/dock-redesign
```

- [ ] **Step 2: Write the failing test** `tests/test_geopackage_counts.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_geopackage_counts.py -v`
Expected: FAIL — `ImportError: cannot import name 'layer_counts'`.

- [ ] **Step 4: Add both helpers at the END of `drainworks_plugin/io/geopackage_store.py`:**

```python
def layer_counts(path) -> dict:
    """Return feature counts: ``{'manholes': n, 'pipes': n, 'measurements': n}``."""
    ds = ogr.Open(str(path))
    if ds is None:
        return {"manholes": 0, "pipes": 0, "measurements": 0}

    def _count(name):
        layer = ds.GetLayerByName(name)
        return layer.GetFeatureCount() if layer is not None else 0

    return {"manholes": _count("manholes"), "pipes": _count("pipes"),
            "measurements": _count("measurements_raw")}


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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_geopackage_counts.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && git add drainworks_plugin/io/geopackage_store.py tests/test_geopackage_counts.py && git commit -m "feat: layer_counts + total_lost_volume store helpers"
```

---

## Task 3: Enrich summary — errors + warnings

**Repo:** plugin.
**Files:**
- Modify: `drainworks_plugin/pipeline/enrich.py`
- Test: `tests/test_pipeline_enrich.py` (extend)

Make `enrich` count `n_errors` / `n_warnings` from the validation severities (Task 1).

- [ ] **Step 1: Write the failing test** — append to `tests/test_pipeline_enrich.py`:

```python
def test_enrich_summary_counts_errors_and_warnings(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import write_base
    from drainworks_plugin.pipeline.enrich import enrich
    import rgs_ribx

    manholes = [rgs_ribx.Manhole(code="A", geometry_wkt="POINT (0 0)")]
    pipes = [
        rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="Z", bob1=-2.0, bob2=None,
                      diameter=5.0, length=30.0, geometry_wkt="LINESTRING (0 0, 30 0)"),
    ]
    write_base(tmp_gpkg, manholes, pipes, raw_measurements={})
    summary = enrich(tmp_gpkg, correct_bob=False)
    # missing bob2 + dangling manhole2 -> errors ; diameter 5000 mm -> warning
    assert summary["n_errors"] >= 2
    assert summary["n_warnings"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_pipeline_enrich.py::test_enrich_summary_counts_errors_and_warnings -v`
Expected: FAIL — `KeyError: 'n_errors'`.

- [ ] **Step 3: Implement in `drainworks_plugin/pipeline/enrich.py`.** Find the summary
build at the end of `enrich`:
```python
    n_pipe_issues = sum(1 for v in validation["pipes"].values() if v)
    n_manhole_issues = sum(1 for v in validation["manholes"].values() if v)
    return {
        "n_profile_points": len(profile_rows),
        "n_segments": len(segment_rows),
        "n_pipes_with_issues": n_pipe_issues,
        "n_manholes_with_issues": n_manhole_issues,
    }
```
Replace with:
```python
    n_pipe_issues = sum(1 for v in validation["pipes"].values() if v)
    n_manhole_issues = sum(1 for v in validation["manholes"].values() if v)
    all_issues = [i for v in validation["pipes"].values() for i in v]
    all_issues += [i for v in validation["manholes"].values() for i in v]
    n_errors = sum(1 for i in all_issues if getattr(i, "severity", "error") == "error")
    n_warnings = sum(1 for i in all_issues if getattr(i, "severity", "error") == "warning")
    return {
        "n_profile_points": len(profile_rows),
        "n_segments": len(segment_rows),
        "n_pipes_with_issues": n_pipe_issues,
        "n_manholes_with_issues": n_manhole_issues,
        "n_errors": n_errors,
        "n_warnings": n_warnings,
    }
```

- [ ] **Step 4: Run test to verify it passes (+ existing enrich tests)**

Run: `"$QGIS_PY" -m pytest tests/test_pipeline_enrich.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && git add drainworks_plugin/pipeline/enrich.py tests/test_pipeline_enrich.py && git commit -m "feat: enrich summary counts errors + warnings by severity"
```

---

## Task 4: Step settings dialogs (enrich + berging)

**Repo:** plugin.
**Files:**
- Create: `drainworks_plugin/ui/enrich_settings_dialog.py`
- Create: `drainworks_plugin/ui/berging_settings_dialog.py`

Two small dialogs. They take/return plain dicts; the dock persists them via QgsSettings
(Task 5). GUI — verified by import-smoke.

- [ ] **Step 1: Write `drainworks_plugin/ui/enrich_settings_dialog.py`:**

```python
"""Dialog for the 'Verrijk basisdata' step settings."""

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
)


class EnrichSettingsDialog(QDialog):
    """Edit Corrigeer BOB + segment lengths. ``values()`` returns a dict."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instellingen — basisdata verrijken")
        form = QFormLayout(self)
        self.chk_correct_bob = QCheckBox()
        self.chk_correct_bob.setChecked(bool(settings.get("correct_bob", True)))
        self.spn_min_segment = QDoubleSpinBox()
        self.spn_min_segment.setRange(0.1, 50.0)
        self.spn_min_segment.setSuffix(" m")
        self.spn_min_segment.setValue(float(settings.get("min_segment", 1.0)))
        self.spn_bob_segment = QDoubleSpinBox()
        self.spn_bob_segment.setRange(0.5, 100.0)
        self.spn_bob_segment.setSuffix(" m")
        self.spn_bob_segment.setValue(float(settings.get("bob_segment", 5.0)))
        form.addRow("Corrigeer BOB", self.chk_correct_bob)
        form.addRow("Segment (min.)", self.spn_min_segment)
        form.addRow("BOB-segment", self.spn_bob_segment)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        """Return ``{correct_bob, min_segment, bob_segment}``."""
        return {
            "correct_bob": self.chk_correct_bob.isChecked(),
            "min_segment": self.spn_min_segment.value(),
            "bob_segment": self.spn_bob_segment.value(),
        }
```

- [ ] **Step 2: Write `drainworks_plugin/ui/berging_settings_dialog.py`:**

```python
"""Dialog for the 'Bereken verloren berging' step settings."""

from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
)

# UI label <-> stored value.
_RES_LABELS = {"accurate": "nauwkeurig", "fast": "snel"}
_RES_VALUES = {v: k for k, v in _RES_LABELS.items()}


class BergingSettingsDialog(QDialog):
    """Edit the flood-fill resolution. ``values()`` returns a dict."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instellingen — verloren berging")
        form = QFormLayout(self)
        self.cmb_resolution = QComboBox()
        self.cmb_resolution.addItems(["nauwkeurig", "snel"])
        current = _RES_LABELS.get(settings.get("resolution", "accurate"), "nauwkeurig")
        self.cmb_resolution.setCurrentText(current)
        form.addRow("Resolutie", self.cmb_resolution)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        """Return ``{resolution: 'accurate'|'fast'}``."""
        return {"resolution": _RES_VALUES.get(self.cmb_resolution.currentText(), "accurate")}
```

- [ ] **Step 3: Import-smoke + commit**

Run: `"$QGIS_PY" -c "import drainworks_plugin.ui.enrich_settings_dialog, drainworks_plugin.ui.berging_settings_dialog; print('ok')"`
Expected: `ok` (trailing segfault harmless).
```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && git add drainworks_plugin/ui/enrich_settings_dialog.py drainworks_plugin/ui/berging_settings_dialog.py && git commit -m "feat: enrich + berging step settings dialogs"
```

---

## Task 5: Dock layout rebuild

**Repo:** plugin.
**Files:**
- Modify: `drainworks_plugin/ui/dock.py`

Rewrite `_build_ui` into the new layout and update the handlers. This is the large
wiring task; apply the exact replacements below and leave all other methods untouched.

- [ ] **Step 1: Replace `_build_ui` entirely.** Replace the whole `_build_ui` method
(from `def _build_ui(self):` down to its final `self._set_data_enabled(False)`) with:

```python
    def _build_ui(self):
        from qgis.gui import QgsCollapsibleGroupBox

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # --- Main toolbar. ---
        actions = QHBoxLayout()
        self.btn_import = self._tool_button("Importeren", "import.svg", self._on_import)
        self.btn_traj = self._tool_button("Traject", "trajectory.svg", self._on_traj_toggled,
                                          checkable=True)
        self.btn_style = self._tool_button("Opmaak", "brush.svg", self._on_style)
        self.btn_settings = self._tool_button("Instellingen", "lost_capacity.svg",
                                              self._on_sideview_settings)
        for b in (self.btn_import, self.btn_traj, self.btn_style, self.btn_settings):
            actions.addWidget(b)
        actions.addStretch()
        left_layout.addLayout(actions)

        # --- File info. ---
        self.file_label = QLabel("Geen data geladen")
        self.file_label.setStyleSheet("color: #666;")
        self.file_label.setWordWrap(True)
        left_layout.addWidget(self.file_label)

        # --- Card 1: enrich. ---
        card1 = QgsCollapsibleGroupBox("1. Basisdata verrijken")
        c1 = QVBoxLayout(card1)
        gear1 = QHBoxLayout()
        gear1.addStretch()
        self.btn_enrich_settings = QToolButton()
        self.btn_enrich_settings.setText("⚙")
        self.btn_enrich_settings.setToolTip("Instellingen verrijken")
        self.btn_enrich_settings.clicked.connect(self._on_enrich_settings)
        gear1.addWidget(self.btn_enrich_settings)
        c1.addLayout(gear1)
        self.btn_enrich = QPushButton(_icon("lost_capacity.svg"), "Verrijk basisdata")
        self.btn_enrich.clicked.connect(self._on_enrich)
        c1.addWidget(self.btn_enrich)
        self.enrich_status = QLabel("")
        c1.addWidget(self.enrich_status)
        self.enrich_summary = QLabel("")
        self.enrich_summary.setStyleSheet("color: #666;")
        self.enrich_summary.setWordWrap(True)
        c1.addWidget(self.enrich_summary)
        left_layout.addWidget(card1)

        # --- Card 2: berging. ---
        card2 = QgsCollapsibleGroupBox("2. Verloren berging")
        c2 = QVBoxLayout(card2)
        gear2 = QHBoxLayout()
        gear2.addStretch()
        self.btn_loss_settings = QToolButton()
        self.btn_loss_settings.setText("⚙")
        self.btn_loss_settings.setToolTip("Instellingen verloren berging")
        self.btn_loss_settings.clicked.connect(self._on_loss_settings)
        gear2.addWidget(self.btn_loss_settings)
        c2.addLayout(gear2)
        c2.addWidget(QLabel("Sinks (uitstroompunten):"))
        sink_row = QHBoxLayout()
        self.sink_combo = ExtendedCombo()
        add_sink = QToolButton()
        add_sink.setText("+")
        add_sink.setToolTip("Voeg de geselecteerde put toe als sink")
        add_sink.clicked.connect(self._on_add_sink)
        self.btn_sink_map = QPushButton("Kaart")
        self.btn_sink_map.setCheckable(True)
        self.btn_sink_map.setToolTip("Kies een sink-put door deze op de kaart aan te klikken")
        self.btn_sink_map.clicked.connect(self._on_sink_map_toggled)
        sink_row.addWidget(self.sink_combo, 1)
        sink_row.addWidget(add_sink)
        sink_row.addWidget(self.btn_sink_map)
        c2.addLayout(sink_row)
        self.sink_table = QTableWidget(0, 2)
        self.sink_table.setHorizontalHeaderLabels(["Sink", ""])
        self.sink_table.verticalHeader().setVisible(False)
        self.sink_table.setColumnWidth(1, 30)
        self.sink_table.setMaximumHeight(120)
        c2.addWidget(self.sink_table)
        self.btn_loss = QPushButton(_icon("lost_capacity.svg"), "Bereken verloren berging")
        self.btn_loss.clicked.connect(self._on_loss)
        c2.addWidget(self.btn_loss)
        self.loss_status = QLabel("")
        c2.addWidget(self.loss_status)
        self.loss_total = QLabel("")
        self.loss_total.setStyleSheet("color: #2c7fb8; font-weight: bold;")
        c2.addWidget(self.loss_total)
        left_layout.addWidget(card2)

        left_layout.addStretch(1)
        left.setMaximumWidth(360)

        # --- Right: trajectory bar (above) + longitudinal profile. ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self.traj_bar = QWidget()
        traj_layout = QHBoxLayout(self.traj_bar)
        traj_layout.setContentsMargins(0, 0, 0, 0)
        traj_layout.addWidget(QLabel("Traject:"))
        self.btn_traj_downstream = QPushButton("Stroomafw.")
        self.btn_traj_downstream.clicked.connect(self._on_downstream)
        self.btn_traj_delmode = QPushButton("Verwijdermodus")
        self.btn_traj_delmode.setCheckable(True)
        self.btn_traj_clear = QPushButton("Wis")
        self.btn_traj_clear.clicked.connect(self._on_reset)
        self.btn_traj_undo = QPushButton("↶")
        self.btn_traj_undo.clicked.connect(self._on_undo)
        self.btn_traj_redo = QPushButton("↷")
        self.btn_traj_redo.clicked.connect(self._on_redo)
        for b in (self.btn_traj_downstream, self.btn_traj_delmode, self.btn_traj_clear,
                  self.btn_traj_undo, self.btn_traj_redo):
            traj_layout.addWidget(b)
        traj_layout.addStretch()
        self.volume_label = QLabel("")
        self.volume_label.setStyleSheet("color: #2c7fb8; font-weight: bold;")
        traj_layout.addWidget(self.volume_label)
        self.traj_bar.setVisible(False)
        right_layout.addWidget(self.traj_bar)

        self.side_view = SideViewWidget()
        self.side_view.hovered.connect(self._on_graph_hover)
        right_layout.addWidget(self.side_view, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 760])
        self.setWidget(splitter)
        self._set_data_enabled(False)
```

- [ ] **Step 2: Replace `_set_data_enabled`** to cover the new widgets (the toolbar
`btn_downstream` and the inline settings widgets no longer exist):

```python
    def _set_data_enabled(self, enabled):
        for widget in (self.btn_traj, self.btn_style, self.btn_loss, self.btn_enrich,
                       self.btn_enrich_settings, self.btn_loss_settings,
                       self.sink_combo, self.btn_sink_map):
            widget.setEnabled(enabled)
```

- [ ] **Step 3: Add the step-settings persistence + handlers.** Add these constants +
methods to the class (e.g. just after the existing `_on_sideview_settings`):

```python
    ENRICH_SETTINGS_KEY = "drainworks/enrich"
    BERGING_SETTINGS_KEY = "drainworks/berging"
    ENRICH_DEFAULTS = {"correct_bob": True, "min_segment": 1.0, "bob_segment": 5.0}
    BERGING_DEFAULTS = {"resolution": "accurate"}

    def _load_json_settings(self, key, defaults):
        import json
        from qgis.core import QgsSettings
        raw = QgsSettings().value(key, "", type=str)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        merged = dict(defaults)
        merged.update({k: v for k, v in data.items() if k in defaults})
        return merged

    def _save_json_settings(self, key, values):
        import json
        from qgis.core import QgsSettings
        QgsSettings().setValue(key, json.dumps(values))

    def _on_enrich_settings(self):
        from qgis.PyQt.QtWidgets import QDialog
        from drainworks_plugin.ui.enrich_settings_dialog import EnrichSettingsDialog
        current = self._load_json_settings(self.ENRICH_SETTINGS_KEY, self.ENRICH_DEFAULTS)
        dialog = EnrichSettingsDialog(current, self.iface.mainWindow())
        if dialog.exec_() == QDialog.Accepted:
            self._save_json_settings(self.ENRICH_SETTINGS_KEY, dialog.values())

    def _on_loss_settings(self):
        from qgis.PyQt.QtWidgets import QDialog
        from drainworks_plugin.ui.berging_settings_dialog import BergingSettingsDialog
        current = self._load_json_settings(self.BERGING_SETTINGS_KEY, self.BERGING_DEFAULTS)
        dialog = BergingSettingsDialog(current, self.iface.mainWindow())
        if dialog.exec_() == QDialog.Accepted:
            self._save_json_settings(self.BERGING_SETTINGS_KEY, dialog.values())
```

- [ ] **Step 4: Make `_on_enrich` / `_on_loss` read the persisted settings.** Replace
the body of `_on_enrich` (the `EnrichTask(...)` construction) so it reads the dialog
settings instead of the removed inline widgets:
```python
    def _on_enrich(self):
        """Step 2: enrich the (possibly edited) base data, off-thread."""
        if not self.gpkg_path:
            self.iface.messageBar().pushWarning("Drainworks", "Importeer eerst data.")
            return
        from drainworks_plugin.pipeline.tasks import EnrichTask

        s = self._load_json_settings(self.ENRICH_SETTINGS_KEY, self.ENRICH_DEFAULTS)
        task = EnrichTask(self.gpkg_path,
                          correct_bob=s["correct_bob"],
                          min_segment=s["min_segment"],
                          bob_segment=s["bob_segment"],
                          on_done=self._enrich_done)
        self._run_task(task)
```
In `_on_loss`, replace the line `resolution = "accurate" if self.cmb_resolution.currentIndex() == 0 else "fast"` with:
```python
        resolution = self._load_json_settings(self.BERGING_SETTINGS_KEY,
                                              self.BERGING_DEFAULTS)["resolution"]
```

- [ ] **Step 5: Update the summaries in `_enrich_done` / `_loss_done`.** Replace the
entire existing `_enrich_done` method with:
```python
    def _enrich_done(self, task):
        if task.error is not None:
            self.iface.messageBar().pushCritical("Drainworks", f"Verrijken mislukt: {task.error}")
            self.active_task = None
            self._refresh_step_buttons()
            return
        self.state.mark_enriched()
        s = task.result or {}
        self.enrich_summary.setText(
            f"{s.get('n_segments', 0)} segmenten · {s.get('n_errors', 0)} fouten · "
            f"{s.get('n_warnings', 0)} waarschuwingen")
        self.plugin.reload_pipeline_layers()
        self._reload_profile()
        self._refresh_step_buttons()
        self.active_task = None
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Verrijkt: {s.get('n_segments', 0)} segmenten, "
            f"{s.get('n_errors', 0)} fouten, {s.get('n_warnings', 0)} waarschuwingen.")
```
And replace the entire existing `_loss_done` method with:
```python
    def _loss_done(self, task):
        if task.error is not None:
            self.iface.messageBar().pushCritical("Drainworks", f"Berekening mislukt: {task.error}")
            self.active_task = None
            self._refresh_step_buttons()
            return
        from drainworks_plugin.io.geopackage_store import total_lost_volume
        self.state.mark_berging_computed()
        self.computed_sinks = set(self.sinks)
        self.loss_total.setText(
            f"Totaal verloren berging: {total_lost_volume(self.gpkg_path):.2f} m³")
        self.plugin.reload_pipeline_layers()
        self._refresh_step_buttons()
        self._rebuild()
        self.active_task = None
        self.iface.messageBar().pushSuccess(
            "Drainworks", f"Verloren berging berekend ({task.result} segmenten).")
```

- [ ] **Step 6: Extend `_refresh_step_buttons`** to also drive the status labels:
```python
    def _refresh_step_buttons(self):
        """Re-enable + relabel the step buttons and status labels from PipelineState."""
        has = self.gpkg_path is not None
        self.btn_enrich.setEnabled(has)
        self.btn_loss.setEnabled(has)
        self.btn_enrich.setText(self.state.enrich_label())
        self.btn_enrich.setStyleSheet(
            "color: #c54141; font-weight: bold;"
            if self.state.enrich_stale and self.state.enrich_ran else "")
        self.btn_loss.setText(self.state.berging_label())
        self.btn_loss.setStyleSheet(
            "color: #c54141; font-weight: bold;"
            if self.state.berging_stale and self.state.berging_ran else "")
        self._set_status(self.enrich_status, self.state.enrich_ran,
                         self.state.enrich_stale, "verrijk opnieuw")
        self._set_status(self.loss_status, self.state.berging_ran,
                         self.state.berging_stale, "herbereken")

    def _set_status(self, label, ran, stale, action):
        """Update an up-to-date indicator label."""
        if not ran:
            label.setText("nog niet uitgevoerd")
            label.setStyleSheet("color: #666;")
        elif stale:
            label.setText(f"⚠ verouderd — {action}")
            label.setStyleSheet("color: #c5841f; font-weight: bold;")
        else:
            label.setText("✓ actueel")
            label.setStyleSheet("color: #2e7d32;")
```

- [ ] **Step 7: Update `set_data`** — fill the file-info line and clear the summaries on
a fresh import. After `self.gpkg_path = str(gpkg_path)` near the top of `set_data`, add:
```python
        from drainworks_plugin.io.geopackage_store import layer_counts
        counts = layer_counts(self.gpkg_path)
        self.file_label.setText(
            f"Bestand: {os.path.basename(self.gpkg_path)}\n"
            f"Putten {counts['manholes']} · Leidingen {counts['pipes']} · "
            f"Metingen {counts['measurements']}")
```
And just before the final `self.state.mark_imported()` line at the end of `set_data`,
clear the previous run's summaries:
```python
        self.enrich_summary.setText("")
        self.loss_total.setText("")
```

- [ ] **Step 8: Verify — full suite + import-smoke**

Run: `"$QGIS_PY" -m pytest`
Then:
```
"$QGIS_PY" -c "import drainworks_plugin.ui.dock as d; print('ok', hasattr(d.DrainworksDock,'_on_enrich_settings'), hasattr(d.DrainworksDock,'_set_status'))"
```
Expected: green (all previously-passing tests still pass) + `ok True True`. If a test
references a removed widget (`chk_correct_bob`/`cmb_resolution`/`spn_*`/`btn_downstream`/
`btn_sv_settings`), there are none in `tests/` — but grep to be sure:
`grep -rn "chk_correct_bob\|cmb_resolution\|spn_min_segment\|spn_bob_segment\|btn_sv_settings\|btn_downstream" tests/`
(should be empty).

- [ ] **Step 9: Commit**

```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && git add drainworks_plugin/ui/dock.py && git commit -m "feat: dock redesign — toolbar, file-info, collapsible step cards, traj bar above graph"
```

---

## Task 6: Manual QGIS check + finish

- [ ] **Step 1: Full suite** — `"$QGIS_PY" -m pytest` → green.

- [ ] **Step 2: Manual QGIS check (record in the finish report).** Load the plugin and
verify: main toolbar shows Importeren/Traject/Opmaak/Instellingen (no Stroomafw.);
file-info shows gpkg name + putten/leidingen/metingen after import; the two step cards
collapse/expand and show a ⚙ that opens the settings dialog; "Verrijk basisdata" runs
and the card shows "✓ actueel" + "N segmenten · X fouten · Y waarschuwingen"; editing a
BOB + committing flips it to "⚠ verouderd — verrijk opnieuw"; the berging card shows the
total m³ and its own indicator; turning on Traject shows the "Traject:" bar with the
buttons above the longitudinal profile; Instellingen opens the side-view settings.

- [ ] **Step 3: Finish.** REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch`
for the plugin branch `feature/dock-redesign`. (Task 1's rgs-ribx branch was already
merged in Task 1.) Do NOT push.

---

## Notes / backlog (separate, after C3)

Two side-view items the user requested for later (see memory `drainworks-backlog`):
vertical put-code labels with a thin line, and a maaiveld-connecting line excluded from
auto-zoom. Not part of C3.
