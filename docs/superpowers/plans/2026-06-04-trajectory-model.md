# Trajectory Model + Live Side-view + Per-point Water (C6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Definitive trajectory interaction (select/insert/extend/move + reachability), a live BOB-based side-view preview while building, stop loading the profile layer, and per-point water in the accurate berging graph.

**Architecture:** Extract the placement rules into a pure `trajectory/placement.py` (unit-tested against `SewerNetwork`); add water fields to the `profile` layer (TDD store + berging); the rest is `ui/dock.py` wiring + a one-line `load_pipeline_layers` change. Verified by the headless suite + a dock construction smoke + a manual QGIS check.

**Tech Stack:** PyQt5 / `qgis.core` / pyqtgraph, `osgeo.ogr`, `rgs_ribx`, pytest.

**Spec:** `docs/superpowers/specs/2026-06-04-trajectory-model-design.md`.

**Repo:** plugin, branch `feature/trajectory-model`. Test/env prefix:
```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3" PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj" PROJ_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/proj" GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal" PYTHONPATH="/Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin:/Users/bastiaanroos/Documents/GitHub/rgs-ribx/src" && "$QGIS_PY" -m pytest <args>
```
Teardown segfault after the summary is harmless. **Never push.**

---

## Task 1: Pure placement model

**Files:** Create `drainworks_plugin/trajectory/placement.py`; Test `tests/test_placement.py`.

- [ ] **Step 1: Write the failing test** `tests/test_placement.py`:
```python
import rgs_ribx
from drainworks_plugin.trajectory.network import SewerNetwork
from drainworks_plugin.trajectory.placement import place_waypoint


def _net():
    # A - B - C - D in a line, plus a spur E off B, and an isolated X.
    pipes = [
        rgs_ribx.Pipe(code="AB", manhole1="A", manhole2="B", length=10.0),
        rgs_ribx.Pipe(code="BC", manhole1="B", manhole2="C", length=10.0),
        rgs_ribx.Pipe(code="CD", manhole1="C", manhole2="D", length=10.0),
        rgs_ribx.Pipe(code="BE", manhole1="B", manhole2="E", length=10.0),
        rgs_ribx.Pipe(code="XY", manhole1="X", manhole2="Y", length=10.0),
    ]
    return SewerNetwork(pipes)


def test_empty_adds_first():
    assert place_waypoint(_net(), [], None, "A") == (["A"], "A")


def test_existing_waypoint_selects_only():
    assert place_waypoint(_net(), ["A", "D"], "A", "D") == (["A", "D"], "D")


def test_on_route_inserts_tussenpunt():
    # route A->D runs through B and C; clicking C inserts it as a waypoint.
    new, active = place_waypoint(_net(), ["A", "D"], "A", "C")
    assert new == ["A", "C", "D"] and active == "C"


def test_last_selected_appends():
    new, active = place_waypoint(_net(), ["A", "B"], "B", "E")
    assert new == ["A", "B", "E"] and active == "E"


def test_single_point_appends():
    new, active = place_waypoint(_net(), ["A"], "A", "B")
    assert new == ["A", "B"] and active == "B"


def test_first_selected_prepends():
    new, active = place_waypoint(_net(), ["B", "C"], "B", "A")
    assert new == ["A", "B", "C"] and active == "A"


def test_middle_selected_moves():
    # waypoints A,B,D (B middle); selecting B then clicking E moves B->E.
    new, active = place_waypoint(_net(), ["A", "B", "D"], "B", "E")
    assert new == ["A", "E", "D"] and active == "E"


def test_unreachable_returns_none():
    assert place_waypoint(_net(), ["A", "B"], "B", "X") is None
```

- [ ] **Step 2: Run — expect fail** (`ModuleNotFoundError`):
`"$QGIS_PY" -m pytest tests/test_placement.py -v`

- [ ] **Step 3: Write `drainworks_plugin/trajectory/placement.py`:**
```python
"""Pure trajectory placement model (no QGIS).

Given the network, the current waypoints and the selected (active) waypoint, decide
what clicking another manhole does: select / insert a tussenpunt / append / prepend /
move. Returns ``(new_waypoints, new_active)`` or ``None`` when the click would need an
unreachable connection.
"""


def _seg_nodes(network, a, b):
    """The ordered manhole codes of the shortest path a->b, or None if none."""
    try:
        return network.shortest_path(a, b).manholes
    except ValueError:
        return None


def place_waypoint(network, waypoints, active_code, code):
    """Return ``(new_waypoints, new_active)`` for clicking ``code``, or ``None``."""
    wps = list(waypoints)
    if not wps:
        return [code], code
    if code in wps:
        return wps, code  # select only
    # On the current route (between two waypoints) -> insert a tussenpunt.
    if len(wps) >= 2:
        for i in range(len(wps) - 1):
            seg = _seg_nodes(network, wps[i], wps[i + 1])
            if seg and code in seg[1:-1]:
                wps.insert(i + 1, code)
                return wps, code
    # Off the route -> act relative to the selected waypoint (fallback: last).
    sel = active_code if active_code in wps else wps[-1]
    idx = wps.index(sel)
    if idx == len(wps) - 1:                      # last (incl. single) -> append
        return (wps + [code], code) if _seg_nodes(network, sel, code) else None
    if idx == 0:                                 # first -> prepend
        return ([code] + wps, code) if _seg_nodes(network, code, sel) else None
    prev, nxt = wps[idx - 1], wps[idx + 1]       # middle -> move
    if _seg_nodes(network, prev, code) and _seg_nodes(network, code, nxt):
        wps[idx] = code
        return wps, code
    return None
```

- [ ] **Step 4: Run — expect pass:** `"$QGIS_PY" -m pytest tests/test_placement.py -v`

- [ ] **Step 5: Commit**
```bash
git add drainworks_plugin/trajectory/placement.py tests/test_placement.py
git commit -m "feat: pure trajectory placement model (select/insert/extend/move + reachability)"
```

---

## Task 2: Profile layer water fields

**Files:** Modify `drainworks_plugin/io/geopackage_store.py`; Test `tests/test_geopackage_profile_segments.py` (extend).

- [ ] **Step 1: Append the failing test** to `tests/test_geopackage_profile_segments.py`:
```python
def test_profile_roundtrips_water_fields(tmp_gpkg):
    _gpkg(tmp_gpkg)
    rows = [{"pipe_code": "L1", "dist": 0.0, "bob": -2.0, "obb": -1.7,
             "water_level": -1.9, "flooded_pct": 0.5, "geometry_wkt": "POINT (0 0)"}]
    write_profile(tmp_gpkg, rows)
    pt = read_profile(tmp_gpkg)["L1"][0]
    assert pt.water_level == -1.9
    assert pt.flooded_pct == 0.5
```

- [ ] **Step 2: Run — expect fail** (water_level comes back None / field missing):
`"$QGIS_PY" -m pytest tests/test_geopackage_profile_segments.py::test_profile_roundtrips_water_fields -v`

- [ ] **Step 3: Add water fields to `write_profile` + `read_profile`.** In
`geopackage_store.py` `write_profile`, after the dist/bob/obb fields are created:
```python
    layer.CreateField(ogr.FieldDefn("pipe_code", ogr.OFTString))
    for name in ("dist", "bob", "obb"):
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
```
add:
```python
    for name in ("water_level", "flooded_pct"):
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
```
and in the per-row write loop, after `_set(feat, "obb", row.get("obb"))` add:
```python
        _set(feat, "water_level", row.get("water_level"))
        _set(feat, "flooded_pct", row.get("flooded_pct"))
```
In `read_profile`, replace the MeasurementPoint construction:
```python
        grouped.setdefault(feat.GetField("pipe_code"), []).append(
            rgs_ribx.MeasurementPoint(dist=feat.GetField("dist"),
                                      bob=feat.GetField("bob"),
                                      obb=feat.GetField("obb")))
```
with one that also reads the (nullable) water fields:
```python
        mp = rgs_ribx.MeasurementPoint(dist=feat.GetField("dist"),
                                       bob=feat.GetField("bob"),
                                       obb=feat.GetField("obb"))
        if not feat.IsFieldNull("water_level"):
            mp.water_level = feat.GetField("water_level")
        if not feat.IsFieldNull("flooded_pct"):
            mp.flooded_pct = feat.GetField("flooded_pct")
        grouped.setdefault(feat.GetField("pipe_code"), []).append(mp)
```
(Guard the `IsFieldNull` calls so an old profile layer without the fields still reads:
wrap each in `try/except` — if the field is absent, `IsFieldNull` raises; treat as None.)
Concretely use a helper inline:
```python
        def _opt(name):
            try:
                return None if feat.IsFieldNull(name) else feat.GetField(name)
            except (RuntimeError, ValueError):
                return None
        mp = rgs_ribx.MeasurementPoint(dist=feat.GetField("dist"),
                                       bob=feat.GetField("bob"),
                                       obb=feat.GetField("obb"))
        wl = _opt("water_level")
        fp = _opt("flooded_pct")
        if wl is not None:
            mp.water_level = wl
        if fp is not None:
            mp.flooded_pct = fp
        grouped.setdefault(feat.GetField("pipe_code"), []).append(mp)
```

- [ ] **Step 4: Run — expect pass:** `"$QGIS_PY" -m pytest tests/test_geopackage_profile_segments.py -v`

- [ ] **Step 5: Commit**
```bash
git add drainworks_plugin/io/geopackage_store.py tests/test_geopackage_profile_segments.py
git commit -m "feat: profile layer carries water_level + flooded_pct"
```

---

## Task 3: Accurate berging writes per-point water to the profile

**Files:** Modify `drainworks_plugin/pipeline/berging.py`; Test `tests/test_pipeline_berging.py` (extend).

- [ ] **Step 1: Append the failing test** to `tests/test_pipeline_berging.py`:
```python
def test_accurate_writes_per_point_water_to_profile(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import read_profile
    _setup(tmp_gpkg)
    compute_berging(tmp_gpkg, resolution="accurate")
    pts = read_profile(tmp_gpkg)["L1"]
    assert any(p.water_level is not None for p in pts)


def test_fast_leaves_profile_water_empty(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import read_profile
    _setup(tmp_gpkg)
    compute_berging(tmp_gpkg, resolution="fast")
    pts = read_profile(tmp_gpkg)["L1"]
    assert all(p.water_level is None for p in pts)
```

- [ ] **Step 2: Run — expect fail** (accurate doesn't write profile water yet):
`"$QGIS_PY" -m pytest tests/test_pipeline_berging.py::test_accurate_writes_per_point_water_to_profile -v`

- [ ] **Step 3: Write the per-point water back in `compute_berging`.** In `berging.py`,
after `rgs_ribx.compute_lost_capacity(manholes, pipes, profiles)` and before the segment
aggregation loop, add (accurate only — rewrites the measured pipes' profile points with
their flood-filled water):
```python
    if resolution == "accurate" and profile_pts:
        from drainworks_plugin.io.geopackage_store import point_along_wkt, write_profile
        rows = []
        for code in profile_pts:
            pipe = pipes.get(code)
            wkt = pipe.geometry_wkt if pipe else None
            for mp in profiles.get(code, []):
                rows.append({
                    "pipe_code": code, "dist": mp.dist, "bob": mp.bob, "obb": mp.obb,
                    "water_level": mp.water_level, "flooded_pct": mp.flooded_pct,
                    "geometry_wkt": point_along_wkt(wkt, mp.dist) if wkt else None})
        write_profile(gpkg_path, rows)
```
(Note: for accurate, `profiles[code]` for measured pipes IS `profile_pts[code]` — the
same MeasurementPoint objects compute_lost_capacity just annotated.)

- [ ] **Step 4: Run — expect pass:** `"$QGIS_PY" -m pytest tests/test_pipeline_berging.py -v`

- [ ] **Step 5: Commit**
```bash
git add drainworks_plugin/pipeline/berging.py tests/test_pipeline_berging.py
git commit -m "feat: accurate berging writes per-point water back to the profile"
```

---

## Task 4: Don't load the profile layer on the map

**Files:** Modify `drainworks_plugin/io/import_controller.py`.

- [ ] **Step 1: Drop `profile` from the loaded layers.** In `load_pipeline_layers`, the
ordered-load block is:
```python
    ordered = [manhole_layer, pipe_layer]
    if segments_layer.isValid():
        ordered.append(segments_layer)
    if profile_layer.isValid():
        ordered.append(profile_layer)
    for layer in ordered:
        project.addMapLayer(layer, False)
        group.addLayer(layer)
```
Replace with (no profile layer on the map; the side-view reads it from the gpkg):
```python
    ordered = [manhole_layer, pipe_layer]
    if segments_layer.isValid():
        ordered.append(segments_layer)
    for layer in ordered:
        project.addMapLayer(layer, False)
        group.addLayer(layer)
```
The `profile_layer = QgsVectorLayer(...)` / `style_profile(profile_layer)` lines above
can stay (harmless) or be removed; if you remove them, also drop the now-unused
`style_profile` from the import (grep `style_profile` first). Simplest: delete the
`profile_layer` creation + `style_profile` call + the `style_profile` import.

- [ ] **Step 2: Verify + commit.**
`"$QGIS_PY" -m pytest` (green) + `"$QGIS_PY" -c "import drainworks_plugin.io.import_controller; print('ok')"`.
```bash
git add drainworks_plugin/io/import_controller.py
git commit -m "feat: don't add the profile points layer to the map"
```

---

## Task 5: Dock — placement model, reachability, live preview, per-point water

**Files:** Modify `drainworks_plugin/ui/dock.py`.

- [ ] **Step 1: Use the placement model in `_on_pick`.** Replace the current `_on_pick`
+ `_on_ctrl_pick` + `_on_drag` + `_insert_waypoint` with the placement-based handlers.
Replace `_on_pick`:
```python
    def _on_pick(self, code):
        if self.btn_traj_delmode.isChecked():
            if code in self.waypoints:
                self.waypoints.remove(code)
                self.active_code = self.waypoints[-1] if self.waypoints else None
                self.btn_traj_delmode.setChecked(False)
                self._commit_waypoints()
            return
        self._place(code)

    def _place(self, code):
        from drainworks_plugin.trajectory.placement import place_waypoint
        result = place_waypoint(self.network, self.waypoints, self.active_code, code)
        if result is None:
            self.iface.messageBar().pushWarning(
                "Drainworks", "Punt niet bereikbaar vanaf het traject.")
            return
        new_wps, new_active = result
        changed = new_wps != self.waypoints
        self.waypoints = new_wps
        self.active_code = new_active
        self._commit_waypoints(push=changed)
```
Keep `_on_ctrl_pick` (single-point delete) as-is. **Delete** `_on_drag` and
`_insert_waypoint` (the model replaces them). In `_activate_tool`, stop passing the drag
callback — change the `editing` branch so `drag = None` always:
find `drag = self._on_drag if editing else None` and replace with `drag = None`
(leave `ctrl_pick = self._on_ctrl_pick if editing else None`).

- [ ] **Step 2: Refactor the side-view into `_render_side_view(waypoints, light)`.**
Replace the whole `_update_side_view` method with:
```python
    def _update_side_view(self):
        self._render_side_view(self.waypoints, light=self.btn_traj.isChecked())

    def _render_side_view(self, waypoints, light):
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
        measurements = {} if light else self.measurements_by_pipe
        profile = build_profile(route, self.pipes_by_code, measurements,
                                manholes_by_code=self._manholes_by_code)
        self.side_view.show_profile(profile)
        self.route_polyline = self._build_route_polyline(route)
        if light:
            self.volume_label.setText("")
            return
        from drainworks_plugin.sideview.berging import route_berging
        segments_by_pipe = self._read_segments_by_pipe()
        water, volume = route_berging(route, self.pipes_by_code, segments_by_pipe)
        # Accurate berging carries per-point water on the profile (show_profile draws
        # it); only draw the segment overlay when there is no per-point water (fast).
        if not any(v.water_level is not None for v in profile.vertices):
            self.side_view.show_water(water)
        self.volume_label.setText(f"Verloren berging: {volume:.2f} m³" if volume else "")
```

- [ ] **Step 3: Read per-point water for the side-view.** Replace `_read_profile_for_sideview`:
```python
    def _read_profile_for_sideview(self):
        """Read the profile layer into {code: [dict(dist,bob,obb,flooded_pct,water_level)]}."""
        if not self.gpkg_path:
            return {}
        from drainworks_plugin.io.geopackage_store import read_profile
        out = {}
        for code, points in read_profile(self.gpkg_path).items():
            out[code] = [{"dist": p.dist, "bob": p.bob, "obb": p.obb,
                          "flooded_pct": p.flooded_pct, "water_level": p.water_level}
                         for p in points]
        return out
```

- [ ] **Step 4: Live preview on hover + revert on traject toggle.** In `_on_map_hover`,
capture the nearest manhole **code** and, while Traject is active, render the live preview.
Replace the nearest-search + hover block. The current method starts:
```python
    def _on_map_hover(self, point):
        """Highlight the nearest put and drive the graph cursor from the route."""
        if self.graphics is None:
            return
        mupp = self.iface.mapCanvas().mapUnitsPerPixel()
        px, py = point.x(), point.y()
        # Nearest manhole within ~18 px -> highlight (the pick target).
        tol = mupp * 18
        nearest = None
        for xy in self.manhole_points.values():
            d = ((xy[0] - px) ** 2 + (xy[1] - py) ** 2) ** 0.5
            if d <= tol:
                tol, nearest = d, xy
        self.graphics.set_hover(QgsPointXY(*nearest) if nearest else None)
```
Replace that nearest block with one that also tracks the code + does the live preview:
```python
    def _on_map_hover(self, point):
        """Highlight the nearest put and drive the graph cursor from the route."""
        if self.graphics is None:
            return
        mupp = self.iface.mapCanvas().mapUnitsPerPixel()
        px, py = point.x(), point.y()
        tol = mupp * 18
        nearest = None
        nearest_code = None
        for code, xy in self.manhole_points.items():
            d = ((xy[0] - px) ** 2 + (xy[1] - py) ** 2) ** 0.5
            if d <= tol:
                tol, nearest, nearest_code = d, xy, code
        self.graphics.set_hover(QgsPointXY(*nearest) if nearest else None)
        if self.btn_traj.isChecked():
            self._preview_side_view(nearest_code)
```
(Keep the rest of `_on_map_hover` — the `_project_on_route` cursor block — unchanged.)
Add the preview method:
```python
    def _preview_side_view(self, code):
        """Live BOB-based side-view of the trajectory as it would become with `code`."""
        if self.network is None:
            return
        preview = self.waypoints
        if code is not None:
            from drainworks_plugin.trajectory.placement import place_waypoint
            placed = place_waypoint(self.network, self.waypoints, self.active_code, code)
            if placed is not None:
                preview = placed[0]
        self._render_side_view(preview, light=True)
```
In `_on_traj_toggled`, when turning the trajectory **off**, restore the measured view;
when turning it **on**, show the current trajectory light. The method is:
```python
    def _on_traj_toggled(self, checked):
        self.traj_bar.setVisible(checked)
        if checked:
            self.btn_sink_map.setChecked(False)
            self._activate_tool(self._on_pick, self._on_reset, editing=True)
            self._sync_traj_buttons()
        else:
            self.btn_traj_delmode.setChecked(False)
            self._clear_tool()
```
Add `self._update_side_view()` at the end of BOTH branches (after the if/else), so the
graph switches between light (on) and measured (off):
```python
    def _on_traj_toggled(self, checked):
        self.traj_bar.setVisible(checked)
        if checked:
            self.btn_sink_map.setChecked(False)
            self._activate_tool(self._on_pick, self._on_reset, editing=True)
            self._sync_traj_buttons()
        else:
            self.btn_traj_delmode.setChecked(False)
            self._clear_tool()
        self._update_side_view()
```

- [ ] **Step 5: Verify (full suite + import-smoke) + commit.**
```
"$QGIS_PY" -m pytest
"$QGIS_PY" -c "import drainworks_plugin.ui.dock as d; print('ok', hasattr(d.DrainworksDock,'_place'), hasattr(d.DrainworksDock,'_render_side_view'), not hasattr(d.DrainworksDock,'_on_drag'))"
```
Expected: green + `ok True True True`. Also grep that no leftover refs to the removed
methods remain: `grep -n "_on_drag\|_insert_waypoint" drainworks_plugin/ui/dock.py` →
only the `_activate_tool` change should remain (no calls to `_on_drag`/`_insert_waypoint`).
```bash
git add drainworks_plugin/ui/dock.py
git commit -m "feat: trajectory placement model + reachability + live BOB preview + per-point water"
```

---

## Task 6: Construction smoke + manual check + finish

- [ ] **Step 1: Dock construction smoke:**
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
print('DOCK OK', hasattr(dock,'_place'), hasattr(dock,'_render_side_view'))
"
```
Expected: `DOCK OK True True` (trailing segfault harmless).

- [ ] **Step 2: Full suite** — `"$QGIS_PY" -m pytest` → green.

- [ ] **Step 3: Manual QGIS check.** With Traject on: clicking builds A→B→…; clicking a
put on the route inserts a tussenpunt; clicking an existing point selects it (halo moves);
with a middle point selected, clicking elsewhere moves it; with the last/first selected,
clicking elsewhere appends/prepends; an unreachable put shows the message and is not
added; hovering shows a live BOB preview to the put under the cursor; turning Traject off
shows the measured profile with the water overlay. The profile points layer is no longer
in the map tree. Accurate berging shows a per-point water fill in the graph; fast shows
the per-segment overlay.

- [ ] **Step 4: Finish.** REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch`.
Do NOT push.
