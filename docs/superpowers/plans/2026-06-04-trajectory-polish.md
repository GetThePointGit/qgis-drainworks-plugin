# Trajectory & Dock Polish (C4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the dock/trajectory: bottom level in the sinks table, an active-point highlight that follows the last click, reliable single-point deletion (incl. the macOS Ctrl=right-click pitfall), one-shot delete-mode, icon+text trajectory buttons, and tooltips on every button.

**Architecture:** Mostly `ui/dock.py`, `trajectory/map_tool.py`, `trajectory/graphics.py`, plus one TDD store helper and five small SVG icons. GUI wiring is verified by the headless suite + a dock construction smoke + a manual QGIS check.

**Tech Stack:** PyQt5 / `qgis.core` / `qgis.gui`, `osgeo.ogr`, pytest.

**Spec:** `docs/superpowers/specs/2026-06-04-trajectory-polish-design.md`.

**Repo:** plugin, branch `feature/trajectory-polish`. Test/env prefix:
```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3" PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj" PROJ_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/proj" GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal" PYTHONPATH="/Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin:/Users/bastiaanroos/Documents/GitHub/rgs-ribx/src" && "$QGIS_PY" -m pytest <args>
```
Teardown segfault after the summary is harmless. **Never push.**

---

## Task 1: Store helper — read_manhole_bottom_levels

**Files:** Modify `drainworks_plugin/io/geopackage_store.py`; Test `tests/test_geopackage_counts.py` (extend).

- [ ] **Step 1: Append the failing test** to `tests/test_geopackage_counts.py`:
```python
def test_read_manhole_bottom_levels(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import read_manhole_bottom_levels
    _gpkg(tmp_gpkg)
    levels = read_manhole_bottom_levels(tmp_gpkg)
    # bottom_level = lowest connected pipe BOB; pipe L1 has bob1=-2.0, bob2=-2.6
    assert round(levels["A"], 1) == -2.0
    assert round(levels["B"], 1) == -2.6
```

- [ ] **Step 2: Run — expect fail** (`ImportError: cannot import name 'read_manhole_bottom_levels'`):
`"$QGIS_PY" -m pytest tests/test_geopackage_counts.py::test_read_manhole_bottom_levels -v`

- [ ] **Step 3: Add the helper** at the END of `geopackage_store.py`:
```python
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
```

- [ ] **Step 4: Run — expect pass:** `"$QGIS_PY" -m pytest tests/test_geopackage_counts.py -v`

- [ ] **Step 5: Commit**
```bash
git add drainworks_plugin/io/geopackage_store.py tests/test_geopackage_counts.py
git commit -m "feat: read_manhole_bottom_levels store helper"
```

---

## Task 2: Sinks table — bodem column

**Files:** Modify `drainworks_plugin/ui/dock.py`.

- [ ] **Step 1: Make the table 3 columns.** In `_build_ui`, replace the sink-table setup:
```python
        self.sink_table = QTableWidget(0, 2)
        self.sink_table.setHorizontalHeaderLabels(["Sink", ""])
        self.sink_table.verticalHeader().setVisible(False)
        self.sink_table.setColumnWidth(1, 30)
        self.sink_table.setMaximumHeight(120)
```
with:
```python
        self.sink_table = QTableWidget(0, 3)
        self.sink_table.setHorizontalHeaderLabels(["Sink", "bodem (m)", ""])
        self.sink_table.verticalHeader().setVisible(False)
        self.sink_table.setColumnWidth(1, 70)
        self.sink_table.setColumnWidth(2, 30)
        self.sink_table.setMaximumHeight(120)
```

- [ ] **Step 2: Populate the bodem column.** Replace `_update_sink_table` with:
```python
    def _update_sink_table(self):
        from drainworks_plugin.io.geopackage_store import read_manhole_bottom_levels
        levels = read_manhole_bottom_levels(self.gpkg_path) if self.gpkg_path else {}
        codes = sorted(self.sinks)
        self.sink_table.setRowCount(len(codes))
        for i, code in enumerate(codes):
            self.sink_table.setItem(i, 0, QTableWidgetItem(code))
            bottom = levels.get(code)
            self.sink_table.setItem(i, 1, QTableWidgetItem(
                f"{bottom:.2f}" if bottom is not None else "—"))
            btn = QPushButton("✕")
            btn.setFixedWidth(28)
            btn.setToolTip("Verwijder deze sink")
            btn.clicked.connect(lambda _c, c=code: self._remove_sink(c))
            self.sink_table.setCellWidget(i, 2, btn)
```

- [ ] **Step 3: Verify + commit.**
`"$QGIS_PY" -m pytest` (green) and
`"$QGIS_PY" -c "import drainworks_plugin.ui.dock; print('ok')"`.
```bash
git add drainworks_plugin/ui/dock.py
git commit -m "feat: show put bottom level in the sinks table"
```

---

## Task 3: Active point follows the last click + prominent halo

**Files:** Modify `drainworks_plugin/trajectory/graphics.py`, `drainworks_plugin/ui/dock.py`.

- [ ] **Step 1: Prominent filled halo.** In `graphics.py` `set_active`, replace the
marker creation block:
```python
        if self.active_marker is None:
            self.active_marker = QgsVertexMarker(self.canvas)
            self.active_marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
            self.active_marker.setColor(QColor("#00a0e9"))
            self.active_marker.setIconSize(24)
            self.active_marker.setPenWidth(3)
```
with:
```python
        if self.active_marker is None:
            self.active_marker = QgsVertexMarker(self.canvas)
            self.active_marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
            self.active_marker.setColor(QColor("#0079c1"))
            self.active_marker.setFillColor(QColor(0, 121, 193, 70))
            self.active_marker.setIconSize(26)
            self.active_marker.setPenWidth(3)
```

- [ ] **Step 2: Track the last-interacted put in the dock.** In `DrainworksDock.__init__`,
after `self.waypoints = []` add:
```python
        self.active_code = None
```

- [ ] **Step 3: Set `active_code` at each edit.** Apply these edits in `dock.py`:
- In `_on_pick`, set the active to the clicked code on add (replace the method):
```python
    def _on_pick(self, code):
        if self.btn_traj_delmode.isChecked():
            if code in self.waypoints:
                self.waypoints.remove(code)
                self.active_code = self.waypoints[-1] if self.waypoints else None
                self.btn_traj_delmode.setChecked(False)
                self._commit_waypoints()
            return
        self._insert_waypoint(code)
        self.active_code = code
        self._commit_waypoints()
```
- In `_on_ctrl_pick`, update active after removing:
```python
    def _on_ctrl_pick(self, code):
        if code in self.waypoints:
            self.waypoints.remove(code)
            self.active_code = self.waypoints[-1] if self.waypoints else None
            self._commit_waypoints()
```
- In `_on_drag`, set active to the drop target:
```python
    def _on_drag(self, from_code, to_code):
        if from_code in self.waypoints and to_code not in self.waypoints:
            self.waypoints[self.waypoints.index(from_code)] = to_code
            self.active_code = to_code
            self._commit_waypoints()
```
- In `_on_downstream`, after the `for code in path[1:]: self.waypoints.append(code)` loop
and before `self._commit_waypoints()`, set `self.active_code = self.waypoints[-1]`.
- In `_on_reset`, set `self.active_code = None` (add the line before `self._commit_waypoints()`).
- In `_on_undo` and `_on_redo`, after assigning `self.waypoints = ...`, set
`self.active_code = self.waypoints[-1] if self.waypoints else None`.

- [ ] **Step 4: Highlight `active_code` in `_update_graphics`.** Replace the existing
active block at the end of `_update_graphics`:
```python
        if self.waypoints:
            xy = self.manhole_points.get(self.waypoints[-1])
            self.graphics.set_active(QgsPointXY(*xy) if xy else None)
        else:
            self.graphics.set_active(None)
```
with:
```python
        active = self.active_code if self.active_code in self.waypoints else None
        xy = self.manhole_points.get(active) if active else None
        self.graphics.set_active(QgsPointXY(*xy) if xy else None)
```

- [ ] **Step 5: Verify + commit.**
`"$QGIS_PY" -m pytest` (green) + `"$QGIS_PY" -c "import drainworks_plugin.ui.dock, drainworks_plugin.trajectory.graphics; print('ok')"`.
```bash
git add drainworks_plugin/trajectory/graphics.py drainworks_plugin/ui/dock.py
git commit -m "feat: active waypoint follows the last click with a prominent halo"
```

---

## Task 4: Single-point delete (macOS-safe) + one-shot delete-mode

**Files:** Modify `drainworks_plugin/trajectory/map_tool.py`. (Delete-mode one-shot was
already added to `_on_pick` in Task 3 Step 3.)

- [ ] **Step 1: Route right-click to single-delete during editing.** In
`map_tool.py`, replace `canvasReleaseEvent` with:
```python
    def canvasReleaseEvent(self, event):  # noqa: N802 (Qt override)
        point = self.toMapCoordinates(event.pos())
        code = self._nearest_manhole_code(point)
        if event.button() == Qt.RightButton:
            # During trajectory editing (on_ctrl_pick wired) a right-click — which is
            # also what macOS makes of Ctrl+click — removes the nearest waypoint instead
            # of clearing everything. Other tools keep the plain reset.
            if self.on_ctrl_pick is not None and code is not None:
                self.on_ctrl_pick(code)
            else:
                self.on_reset()
            return
        if code is None:
            return
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        if ctrl and self.on_ctrl_pick is not None:
            self.on_ctrl_pick(code)
        elif self._press_code is not None and self._press_code != code and self.on_drag is not None:
            self.on_drag(self._press_code, code)
        else:
            self.on_pick(code)
        self._press_code = None
```

- [ ] **Step 2: Verify + commit.**
`"$QGIS_PY" -m pytest` (green) + `"$QGIS_PY" -c "import drainworks_plugin.trajectory.map_tool; print('ok')"`.
```bash
git add drainworks_plugin/trajectory/map_tool.py
git commit -m "feat: right-click/Cmd-click removes one waypoint (macOS-safe); full clear via Wis only"
```

---

## Task 5: Trajectory button icons + text, and tooltips everywhere

**Files:** Create five SVGs under `drainworks_plugin/resources/icons/`; modify `ui/dock.py`.

- [ ] **Step 1: Create the five icons.** Write each file:

`drainworks_plugin/resources/icons/downstream.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#0079c1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="4" x2="12" y2="20"/><polyline points="6 14 12 20 18 14"/></svg>
```
`drainworks_plugin/resources/icons/delete_mode.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#c54141" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></svg>
```
`drainworks_plugin/resources/icons/clear.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#666666" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="5" x2="19" y2="19"/><line x1="19" y1="5" x2="5" y2="19"/></svg>
```
`drainworks_plugin/resources/icons/undo.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#0079c1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 7 4 12 9 17"/><path d="M4 12h11a5 5 0 0 1 0 10h-1"/></svg>
```
`drainworks_plugin/resources/icons/redo.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#0079c1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 7 20 12 15 17"/><path d="M20 12H9a5 5 0 0 0 0 10h1"/></svg>
```

- [ ] **Step 2: Convert the trajectory buttons to icon+text QToolButtons.** In
`_build_ui`, replace the trajectory-bar button creation block:
```python
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
```
with:
```python
        self.btn_traj_downstream = self._text_tool_button(
            "Stroomafw.", "downstream.svg", self._on_downstream,
            "Verleng het traject stroomafwaarts vanaf het laatste punt")
        self.btn_traj_delmode = self._text_tool_button(
            "Verwijdermodus", "delete_mode.svg", None,
            "Klik daarna één put aan om die uit het traject te verwijderen", checkable=True)
        self.btn_traj_clear = self._text_tool_button(
            "Wis", "clear.svg", self._on_reset, "Wis het hele traject")
        self.btn_traj_undo = self._text_tool_button(
            "Ongedaan", "undo.svg", self._on_undo, "Maak de laatste wijziging ongedaan")
        self.btn_traj_redo = self._text_tool_button(
            "Opnieuw", "redo.svg", self._on_redo, "Voer de ongedane wijziging opnieuw uit")
        for b in (self.btn_traj_downstream, self.btn_traj_delmode, self.btn_traj_clear,
                  self.btn_traj_undo, self.btn_traj_redo):
            traj_layout.addWidget(b)
```

- [ ] **Step 3: Add the `_text_tool_button` helper** next to `_tool_button`:
```python
    def _text_tool_button(self, text, icon_name, slot, tooltip, checkable=False):
        """A QToolButton with the icon left of the text (trajectory bar style)."""
        button = QToolButton()
        button.setText(text)
        button.setIcon(_icon(icon_name))
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        button.setCheckable(checkable)
        button.setToolTip(tooltip)
        if slot is not None:
            button.clicked.connect(slot)
        return button
```

- [ ] **Step 4: Tooltips on the main toolbar + step buttons + gears + sink "+".** Apply:
- After `self.btn_import = self._tool_button("Importeren", ...)` add `self.btn_import.setToolTip("Importeer RIBX/SUFRIB of een bestaande GeoPackage")`.
- After `self.btn_traj = self._tool_button("Traject", ...)` add `self.btn_traj.setToolTip("Stel een traject samen door putten op de kaart te klikken")`.
- After `self.btn_style = self._tool_button("Opmaak", ...)` add `self.btn_style.setToolTip("Pas de kaartopmaak van leidingen en putten aan")`.
- After `self.btn_settings = self._tool_button("Instellingen", ...)` add `self.btn_settings.setToolTip("Instellingen voor het langsprofiel")`.
- After `self.btn_enrich = QPushButton(_icon("lost_capacity.svg"), "Verrijk basisdata")` add `self.btn_enrich.setToolTip("Valideer, bereken hoogtes en bouw segmenten uit de basisdata")`.
- The `self.btn_enrich_settings` already has a tooltip ("Instellingen verrijken") — leave it.
- After `self.btn_loss = QPushButton(_icon("lost_capacity.svg"), "Bereken verloren berging")` add `self.btn_loss.setToolTip("Bereken de verloren berging op de segmenten met de gekozen sinks")`.
- The `self.btn_loss_settings` already has a tooltip — leave it.
- The sink `add_sink` "+" and `self.btn_sink_map` "Kaart" already have tooltips — leave them.

- [ ] **Step 5: Verify + commit.**
`"$QGIS_PY" -m pytest` (green) + `"$QGIS_PY" -c "import drainworks_plugin.ui.dock as d; print('ok', hasattr(d.DrainworksDock,'_text_tool_button'))"`.
```bash
git add drainworks_plugin/resources/icons/downstream.svg drainworks_plugin/resources/icons/delete_mode.svg drainworks_plugin/resources/icons/clear.svg drainworks_plugin/resources/icons/undo.svg drainworks_plugin/resources/icons/redo.svg drainworks_plugin/ui/dock.py
git commit -m "feat: trajectory buttons icon+text; tooltips on all buttons"
```

---

## Task 6: Construction smoke + manual check + finish

- [ ] **Step 1: Dock construction smoke** (catches `_build_ui`/handler wiring errors):
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
print('DOCK OK', dock.sink_table.columnCount(), hasattr(dock, 'active_code'),
      dock.btn_traj_undo.toolButtonStyle())
"
```
Expected: prints `DOCK OK 3 True ...` (a trailing exit-139 segfault is harmless).

- [ ] **Step 2: Full suite** — `"$QGIS_PY" -m pytest` → green.

- [ ] **Step 3: Manual QGIS check.** Verify: sink table shows the bodem column; the
active halo sits on the put you last clicked and moves as you add/drag; Command-click
and right-click each remove a single point while "Wis" clears all; delete-mode turns
itself off after one removal; the trajectory buttons show icon+text; hovering any button
shows a tooltip.

- [ ] **Step 4: Finish.** REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch`.
Do NOT push.
