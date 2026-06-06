# Trajectory Live Preview Refinements (C9) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "Klaar" button, a live map preview that follows the cursor and clears when the mouse leaves the map, a grey trajectory, and a side-view that keeps the committed trajectory measured (with water) while the live-edited part shows only the BOB line.

**Architecture:** `graphics.py` colour change + new `check.svg`; the rest is `ui/dock.py` — refactor the side-view + map graphics to render an arbitrary (preview) waypoint list, limit measured data to the committed route, drive both from hover, and clear on a canvas-leave event filter. GUI — verified by the suite + dock construction smoke + manual check.

**Tech Stack:** PyQt5 / `qgis.core`/`qgis.gui` / pyqtgraph, pytest.

**Spec:** `docs/superpowers/specs/2026-06-04-trajectory-live-design.md`.

**Repo:** plugin, branch `feature/trajectory-live`. Test/env prefix:
```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3" PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj" PROJ_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/proj" GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal" PYTHONPATH="/Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin:/Users/bastiaanroos/Documents/GitHub/rgs-ribx/src" && "$QGIS_PY" -m pytest <args>
```
Teardown segfault after the summary is harmless. **Never push.**

---

## Task 1: Grey trajectory

**Files:** Modify `drainworks_plugin/trajectory/graphics.py`.

- [ ] **Step 1: Grey the marker + route colours.** Change the constants:
```python
MARKER_COLOR = "#c54141"
ROUTE_COLOR = "#c54141"
```
to:
```python
MARKER_COLOR = "#5a5a5a"
ROUTE_COLOR = "#5a5a5a"
```
And change the route band colour in `__init__`:
```python
        self.route_band.setColor(QColor(197, 65, 65, 90))   # semi-transparent
```
to:
```python
        self.route_band.setColor(QColor(90, 90, 90, 90))   # semi-transparent grey
```
(The active halo `#0079c1` in `set_active` stays blue — leave it.)

- [ ] **Step 2: Import-smoke + commit.**
```
"$QGIS_PY" -c "import drainworks_plugin.trajectory.graphics; print('ok')"
git add drainworks_plugin/trajectory/graphics.py
git commit -m "feat: grey trajectory band + markers (red is used in the side-view legend)"
```

---

## Task 2: "Klaar" button

**Files:** Create `drainworks_plugin/resources/icons/check.svg`; modify `ui/dock.py`.

- [ ] **Step 1: Write `drainworks_plugin/resources/icons/check.svg`:**
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#2e7d32" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
```

- [ ] **Step 2: Add the button to the trajectory bar.** In `_build_ui`, after the redo
button is created and before the `for b in (...)` loop that adds them, add a "Klaar"
button, and include it in the loop. Replace:
```python
        self.btn_traj_redo = self._text_tool_button(
            "Opnieuw", "redo.svg", self._on_redo, "Voer de ongedane wijziging opnieuw uit")
        for b in (self.btn_traj_downstream, self.btn_traj_delmode, self.btn_traj_clear,
                  self.btn_traj_undo, self.btn_traj_redo):
            traj_layout.addWidget(b)
```
with:
```python
        self.btn_traj_redo = self._text_tool_button(
            "Opnieuw", "redo.svg", self._on_redo, "Voer de ongedane wijziging opnieuw uit")
        self.btn_traj_done = self._text_tool_button(
            "Klaar", "check.svg", self._on_traj_done, "Sluit de trajectkeuze af")
        for b in (self.btn_traj_downstream, self.btn_traj_delmode, self.btn_traj_clear,
                  self.btn_traj_undo, self.btn_traj_redo, self.btn_traj_done):
            traj_layout.addWidget(b)
```

- [ ] **Step 3: Add `_on_traj_done`** (turns the trajectory tool off). Add near
`_on_traj_toggled`:
```python
    def _on_traj_done(self):
        """Finish trajectory editing: turn the Traject tool off."""
        self.btn_traj.setChecked(False)
        self._on_traj_toggled(False)
```
(`setChecked(False)` alone doesn't emit `clicked`, so call the handler explicitly.)

- [ ] **Step 4: Import-smoke + commit.**
```
"$QGIS_PY" -c "import drainworks_plugin.ui.dock as d; print('ok', hasattr(d.DrainworksDock,'_on_traj_done'))"
git add drainworks_plugin/resources/icons/check.svg drainworks_plugin/ui/dock.py
git commit -m "feat: trajectory 'Klaar' button to finish the trajectory tool"
```

---

## Task 3: Live map preview + committed-measured side-view + leave-clears

**Files:** Modify `drainworks_plugin/ui/dock.py`.

- [ ] **Step 1: Render-from-arbitrary-waypoints for the map graphics.** Replace
`_update_graphics` with a `_render_graphics(waypoints, active_code)` + a thin
`_update_graphics`:
```python
    def _update_graphics(self):
        self._render_graphics(self.waypoints, self.active_code)

    def _render_graphics(self, waypoints, active_code):
        if self.graphics is None:
            return
        labelled = []
        for i, code in enumerate(waypoints):
            xy = self.manhole_points.get(code)
            if xy is not None:
                letter = LETTERS[i] if i < len(LETTERS) else str(i + 1)
                labelled.append((letter, QgsPointXY(xy[0], xy[1])))
        self.graphics.set_markers(labelled)
        geoms = []
        if self.network is not None and len(waypoints) >= 2:
            try:
                route = self.network.route(waypoints)
                geoms = [self.pipe_geoms.get(c) for c in route.pipe_codes]
            except ValueError:
                geoms = []
        self.graphics.set_route(geoms)
        active = active_code if active_code in waypoints else None
        xy = self.manhole_points.get(active) if active else None
        self.graphics.set_active(QgsPointXY(*xy) if xy else None)
```

- [ ] **Step 2: Committed-measured side-view.** Replace `_render_side_view(self, waypoints, light)`
and `_update_side_view` with:
```python
    def _update_side_view(self):
        self._render_side_view(self.waypoints)

    def _render_side_view(self, waypoints):
        if self.network is None or len(waypoints) < 2:
            self.side_view.clear()
            self.volume_label.setText("")
            self.route_polyline = []
            return
        try:
            route = self.network.route(waypoints)
        except ValueError as exc:
            self.iface.messageBar().pushWarning("Drainworks", str(exc))
            self.side_view.clear()
            self.volume_label.setText("")
            self.route_polyline = []
            return
        # Pipes of the committed trajectory show the measured invert + water; pipes that
        # exist only in the live preview fall back to the straight BOB line (no water).
        committed_route = None
        committed_codes = set()
        if len(self.waypoints) >= 2:
            try:
                committed_route = self.network.route(self.waypoints)
                committed_codes = set(committed_route.pipe_codes)
            except ValueError:
                committed_route = None
        measurements = {c: m for c, m in self.measurements_by_pipe.items() if c in committed_codes}
        profile = build_profile(route, self.pipes_by_code, measurements,
                                manholes_by_code=self._manholes_by_code)
        self.side_view.show_profile(profile)
        self.route_polyline = self._build_route_polyline(route)
        if committed_route is None:
            self.volume_label.setText("")
            return
        from drainworks_plugin.sideview.berging import route_berging
        segments_by_pipe = self._read_segments_by_pipe()
        water, volume = route_berging(committed_route, self.pipes_by_code, segments_by_pipe)
        # Accurate berging carries per-point water on the profile (show_profile draws it);
        # only draw the segment overlay when there is no per-point water (fast).
        if not any(v.water_level is not None for v in profile.vertices):
            self.side_view.show_water(water)
        self.volume_label.setText(f"Verloren berging: {volume:.2f} m³" if volume else "")
```

- [ ] **Step 3: Drive both views from hover (preview).** Replace `_preview_side_view`
with `_preview` that updates the side-view AND the map graphics:
```python
    def _preview(self, code):
        """Live preview (graph + map) of the trajectory as it would become with `code`."""
        if self.network is None:
            return
        preview, active = self.waypoints, self.active_code
        if code is not None:
            from drainworks_plugin.trajectory.placement import place_waypoint
            placed = place_waypoint(self.network, self.waypoints, self.active_code, code)
            if placed is not None:
                preview, active = placed
        self._render_side_view(preview)
        self._render_graphics(preview, active)
```
In `_on_map_hover`, change the call `self._preview_side_view(nearest_code)` to
`self._preview(nearest_code)`.

- [ ] **Step 4: Clear the preview when the mouse leaves the canvas.** Add an event filter
on the dock + install/remove it in `_on_traj_toggled`. Add the method:
```python
    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        from qgis.PyQt.QtCore import QEvent
        if event.type() == QEvent.Leave and self.btn_traj.isChecked():
            if self.graphics is not None:
                self.graphics.set_hover(None)
            self._update_side_view()   # revert graph to the committed trajectory
            self._update_graphics()    # revert map to the committed trajectory
        return super().eventFilter(obj, event)
```
Replace `_on_traj_toggled` with one that installs/removes the filter and reverts both
views:
```python
    def _on_traj_toggled(self, checked):
        self.traj_bar.setVisible(checked)
        canvas = self.iface.mapCanvas()
        if checked:
            self.btn_sink_map.setChecked(False)
            self._activate_tool(self._on_pick, self._on_reset, editing=True)
            self._sync_traj_buttons()
            canvas.viewport().installEventFilter(self)
        else:
            self.btn_traj_delmode.setChecked(False)
            self._clear_tool()
            canvas.viewport().removeEventFilter(self)
        self._update_side_view()
        self._update_graphics()
```

- [ ] **Step 5: Verify (full suite + import-smoke) + commit.**
```
"$QGIS_PY" -m pytest
"$QGIS_PY" -c "import drainworks_plugin.ui.dock as d; print('ok', hasattr(d.DrainworksDock,'_render_graphics'), hasattr(d.DrainworksDock,'_preview'), hasattr(d.DrainworksDock,'eventFilter'), not hasattr(d.DrainworksDock,'_preview_side_view'))"
```
Expected: green + `ok True True True True`. Grep no leftover `light=`/`_preview_side_view`:
`grep -n "light=\|_preview_side_view" drainworks_plugin/ui/dock.py` → empty.
```bash
git add drainworks_plugin/ui/dock.py
git commit -m "feat: live map preview + committed-measured side-view + clear preview on canvas leave"
```

---

## Task 4: Construction smoke + manual check + finish

- [ ] **Step 1: Dock construction smoke:**
```bash
export QT_QPA_PLATFORM=offscreen
"$QGIS_PY" -u -c "
from qgis.core import QgsApplication
app = QgsApplication([], True); app.initQgis()
from qgis.PyQt.QtWidgets import QMainWindow
mw = QMainWindow()
p = type('P', (), {'iface': type('I', (), {'mainWindow': lambda self: mw, 'mapCanvas': lambda self: None})()})()
from drainworks_plugin.ui.dock import DrainworksDock
dock = DrainworksDock(p)
print('DOCK OK', hasattr(dock,'btn_traj_done'), hasattr(dock,'_render_graphics'))
"
```
Expected: `DOCK OK True True` (trailing segfault harmless).

- [ ] **Step 2: Full suite** — `"$QGIS_PY" -m pytest` → green.

- [ ] **Step 3: Manual QGIS check.** With Traject on: the route band + markers are grey;
hovering previews the route live on the map AND in the graph; the committed part of the
graph shows the measured invert + water while the previewed extension shows only the BOB
line; moving the mouse off the map clears the preview (graph + map revert to the committed
trajectory); "Klaar" closes the trajectory tool.

- [ ] **Step 4: Finish.** REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch`.
Do NOT push.
