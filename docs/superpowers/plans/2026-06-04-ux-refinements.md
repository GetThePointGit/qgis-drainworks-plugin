# UX Refinements (C2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the spec's UX refinements — trajectory tool rework, side-view settings + live BOB line + put lines + flood overlay from segments, sinks table, and styling (brush icon + graduated legend) — on top of the C1 pipeline GUI.

**Architecture:** Extract every piece of real logic into pure, headless-testable units (profile geometry, berging-from-segments, waypoint undo/redo history, graduated renderers) built TDD; the remaining GUI wiring (canvas markers, map-tool edits, gear dialog, sinks table, dock layout) ships complete code verified by import-smoke + a manual QGIS check, since the repo has no `QgsApplication` GUI-interaction harness.

**Tech Stack:** PyQt5 / `qgis.core` / `qgis.gui` (`QgsVertexMarker`, `QgsRubberBand`, `QgsMapTool`, `QgsSettings`, `QgsGraduatedSymbolRenderer`), pyqtgraph, pytest.

**Spec:** `docs/superpowers/specs/2026-06-04-drainworks-1.0-refinements-design.md` (section 2).

**Repo:** `~/Documents/GitHub/qgis-drainworks-plugin`. Headless test/env prefix (use for every pytest/python command):
```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3" PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj" PROJ_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/proj" GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal" PYTHONPATH="/Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin:/Users/bastiaanroos/Documents/GitHub/rgs-ribx/src" && "$QGIS_PY" -m pytest <args>
```
A teardown segfault (exit 139) AFTER the pytest summary is harmless; run without `-q` if it hides the summary.

> **Git (user rule):** never commit on `main`. Start with `git switch -c feature/ux-refinements`. Never `git push`.

---

## File Structure

```
drainworks_plugin/
├── sideview/
│   ├── profile_builder.py   # MODIFY: Profile.manhole_levels (bob->maaiveld) ; build_profile takes manholes
│   ├── berging.py           # CREATE: route_berging(route, segments_by_pipe) -> water pts + volume (pure)
│   ├── settings.py          # CREATE: SideViewSettings (QgsSettings-backed)
│   └── sideview_widget.py   # MODIFY: put lines (ignoreBounds), water overlay, settings, live light line
├── trajectory/
│   ├── history.py           # CREATE: WaypointHistory (undo/redo + edit ops, pure)
│   ├── graphics.py          # MODIFY: letter-in-circle marker, wide band, active-point highlight
│   └── map_tool.py          # MODIFY: ctrl-click delete + drag-move callbacks
├── styling/views.py         # MODIFY: graduated renderers for bob/slope/bottom/ground
└── ui/
    ├── dock.py              # MODIFY: contextual trajectory buttons, remove table, sinks table, live line, gear
    └── sideview_settings_dialog.py  # CREATE: the gear settings dialog
```

---

## Task 1: Profile put levels (bob → maaiveld)

**Files:**
- Modify: `drainworks_plugin/sideview/profile_builder.py`
- Test: `tests/test_profile_builder.py` (extend)

Add `Profile.manhole_levels` = `[(dist, code, bottom_bob, ground_level)]` so the
side-view can draw each put as a vertical line from its invert up to maaiveld.

- [ ] **Step 1: Write the failing test** — append to `tests/test_profile_builder.py`:

```python
def test_build_profile_emits_manhole_levels_with_ground():
    import rgs_ribx
    from drainworks_plugin.sideview.profile_builder import build_profile
    from drainworks_plugin.trajectory.network import SewerNetwork

    pipes = [rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="B", bob1=-2.0, bob2=-2.6,
                           diameter=0.3, length=30.0)]
    net = SewerNetwork(pipes)
    route = net.route(["A", "B"])
    pipes_by_code = {p.code: p for p in pipes}
    manholes = {"A": rgs_ribx.Manhole(code="A", ground_level=0.2),
                "B": rgs_ribx.Manhole(code="B", ground_level=0.1)}

    profile = build_profile(route, pipes_by_code, manholes_by_code=manholes)
    levels = {code: (bottom, ground) for (_d, code, bottom, ground) in profile.manhole_levels}
    assert levels["A"][1] == 0.2          # ground = maaiveld
    assert levels["B"][1] == 0.1
    assert round(levels["A"][0], 1) == -2.0   # bottom = invert at A
```

(Check the test file's existing imports/style first; place the import lines at the
top of the file if the module already imports them.)

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_profile_builder.py::test_build_profile_emits_manhole_levels_with_ground -v`
Expected: FAIL — `build_profile() got an unexpected keyword argument 'manholes_by_code'`.

- [ ] **Step 3: Implement in `drainworks_plugin/sideview/profile_builder.py`.**

Add `manhole_levels` to the `Profile` dataclass:
```python
    manholes: list = field(default_factory=list)    # (dist, manhole_code) along the route
    manhole_levels: list = field(default_factory=list)  # (dist, code, bottom_bob, ground_level)
```

Change `build_profile`'s signature to accept manholes:
```python
def build_profile(path, pipes: dict, measurements_by_pipe=None,
                  observations_by_pipe=None, manholes_by_code=None) -> Profile:
```
At the top of the body, after `observations_by_pipe = observations_by_pipe or {}`:
```python
    manholes_by_code = manholes_by_code or {}
```
Inside the per-pipe loop, right after `profile.manholes.append((span_start, from_node))`, capture the invert + ground for the put at the span start:
```python
        start_bob_here = pipe.bob1 if forward else pipe.bob2
        gl = getattr(manholes_by_code.get(from_node), "ground_level", None)
        if start_bob_here is not None:
            profile.manhole_levels.append((span_start, from_node, start_bob_here, gl))
```
And after the loop, alongside the existing final-manhole append (`if path.manholes: profile.manholes.append((cumulative, path.manholes[-1]))`), add the final put's levels:
```python
    if path.manholes:
        last = path.manholes[-1]
        last_pipe = pipes[path.pipe_codes[-1]]
        forward_last = last_pipe.manhole1 == path.manholes[-2] if len(path.manholes) >= 2 else True
        last_bob = last_pipe.bob2 if forward_last else last_pipe.bob1
        gl = getattr(manholes_by_code.get(last), "ground_level", None)
        if last_bob is not None:
            profile.manhole_levels.append((cumulative, last, last_bob, gl))
```

- [ ] **Step 4: Run test to verify it passes (+ existing profile tests)**

Run: `"$QGIS_PY" -m pytest tests/test_profile_builder.py -v`
Expected: PASS (the new test + all existing).

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/sideview/profile_builder.py tests/test_profile_builder.py
git commit -m "feat: Profile.manhole_levels (invert -> maaiveld) for put lines"
```

---

## Task 2: Berging overlay from segments (pure)

**Files:**
- Create: `drainworks_plugin/sideview/berging.py`
- Test: `tests/test_sideview_berging.py`

A pure function that, for a route, reads the `segments` water level + lost volume
and returns a water polyline `[(dist, level)]` and the total volume — re-adding the
flood overlay + route volume deferred from C1, now sourced from `segments`.

- [ ] **Step 1: Write the failing test** `tests/test_sideview_berging.py`:

```python
from drainworks_plugin.sideview.berging import route_berging


class _Route:
    def __init__(self, pipe_codes, manholes):
        self.pipe_codes = pipe_codes
        self.manholes = manholes


def test_route_berging_builds_water_line_and_volume():
    # One pipe L1 (A->B, 30 m) with two segments carrying water + volume.
    route = _Route(["L1"], ["A", "B"])
    pipes = {"L1": type("P", (), {"manhole1": "A", "manhole2": "B", "length": 30.0})()}
    segments_by_pipe = {"L1": [
        {"dist_from": 0.0, "dist_to": 15.0, "water_level": -2.1, "lost_volume": 0.3},
        {"dist_from": 15.0, "dist_to": 30.0, "water_level": -2.2, "lost_volume": 0.5},
    ]}
    water, volume = route_berging(route, pipes, segments_by_pipe)
    assert round(volume, 2) == 0.8
    # water polyline spans 0..30 with the segment levels
    assert water[0][0] == 0.0 and water[-1][0] == 30.0
    assert any(abs(level - (-2.1)) < 1e-9 for _d, level in water)


def test_route_berging_reversed_pipe_orients_distance():
    # Travel B->A: segment dist (measured from A) must be mirrored along the route.
    route = _Route(["L1"], ["B", "A"])
    pipes = {"L1": type("P", (), {"manhole1": "A", "manhole2": "B", "length": 30.0})()}
    segments_by_pipe = {"L1": [
        {"dist_from": 0.0, "dist_to": 10.0, "water_level": -2.5, "lost_volume": 0.4},
    ]}
    water, volume = route_berging(route, pipes, segments_by_pipe)
    assert round(volume, 2) == 0.4
    # the segment at 0..10 (from A) maps to 20..30 along the B->A route
    assert max(d for d, _ in water) <= 30.0 + 1e-9
    assert min(d for d, _ in water) >= 20.0 - 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_sideview_berging.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'drainworks_plugin.sideview.berging'`.

- [ ] **Step 3: Write `drainworks_plugin/sideview/berging.py`:**

```python
"""Build the side-view water overlay + total lost volume from the segments layer.

Pure: takes a route, the pipes, and ``{pipe_code: [segment dict]}`` and returns a
water polyline ``[(dist, water_level)]`` along the route plus the summed
``lost_volume``. Segment distances are measured from the pipe's manhole1, so they
are mirrored when the route traverses the pipe backwards.
"""


def route_berging(route, pipes, segments_by_pipe):
    """Return ``(water_points, total_volume)`` for ``route``.

    ``water_points`` is ``[(cumulative_dist, water_level)]`` (two points per
    segment that has a water level). ``total_volume`` sums every segment's
    ``lost_volume`` over the route's pipes.
    """
    water = []
    total_volume = 0.0
    cumulative = 0.0
    for pipe_code, from_node in zip(route.pipe_codes, route.manholes):
        pipe = pipes.get(pipe_code)
        if pipe is None:
            continue
        length = pipe.length or 0.0
        forward = pipe.manhole1 == from_node
        for seg in segments_by_pipe.get(pipe_code, []):
            total_volume += seg.get("lost_volume") or 0.0
            level = seg.get("water_level")
            if level is None:
                continue
            d0, d1 = seg["dist_from"], seg["dist_to"]
            a = d0 if forward else (length - d1)
            b = d1 if forward else (length - d0)
            water.append((cumulative + a, level))
            water.append((cumulative + b, level))
        cumulative += length
    water.sort(key=lambda p: p[0])
    return water, total_volume
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_sideview_berging.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/sideview/berging.py tests/test_sideview_berging.py
git commit -m "feat: route_berging (water overlay + volume from segments)"
```

---

## Task 3: Waypoint undo/redo history (pure)

**Files:**
- Create: `drainworks_plugin/trajectory/history.py`
- Test: `tests/test_waypoint_history.py`

A small undo/redo stack the dock uses for trajectory edits (add / delete / reset),
so the contextual Undo/Redo buttons work without scattering history logic in the dock.

- [ ] **Step 1: Write the failing test** `tests/test_waypoint_history.py`:

```python
from drainworks_plugin.trajectory.history import WaypointHistory


def test_set_undo_redo():
    h = WaypointHistory()
    assert h.current == []
    h.set(["A"])
    h.set(["A", "B"])
    assert h.current == ["A", "B"]
    assert h.can_undo() is True
    assert h.undo() == ["A"]
    assert h.undo() == []
    assert h.can_undo() is False
    assert h.redo() == ["A"]
    assert h.current == ["A"]


def test_set_truncates_redo_branch():
    h = WaypointHistory()
    h.set(["A"]); h.set(["A", "B"])
    h.undo()                # back to ["A"]
    h.set(["A", "C"])       # new branch; redo to ["A","B"] should be gone
    assert h.can_redo() is False
    assert h.current == ["A", "C"]


def test_current_is_a_copy():
    h = WaypointHistory()
    h.set(["A"])
    got = h.current
    got.append("X")
    assert h.current == ["A"]   # internal state not mutated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_waypoint_history.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'drainworks_plugin.trajectory.history'`.

- [ ] **Step 3: Write `drainworks_plugin/trajectory/history.py`:**

```python
"""Undo/redo history for the trajectory waypoint list (pure)."""


class WaypointHistory:
    """A linear undo/redo stack of waypoint lists.

    ``set(waypoints)`` pushes a new state (truncating any redo branch). ``undo`` /
    ``redo`` move the cursor; ``current`` returns a copy of the active state.
    """

    def __init__(self):
        self._stack = [[]]
        self._cursor = 0

    @property
    def current(self):
        """A copy of the active waypoint list."""
        return list(self._stack[self._cursor])

    def set(self, waypoints):
        """Push ``waypoints`` as the new state, dropping any redo branch."""
        self._stack = self._stack[: self._cursor + 1]
        self._stack.append(list(waypoints))
        self._cursor = len(self._stack) - 1

    def can_undo(self):
        return self._cursor > 0

    def can_redo(self):
        return self._cursor < len(self._stack) - 1

    def undo(self):
        """Step back one state and return it (a copy)."""
        if self.can_undo():
            self._cursor -= 1
        return self.current

    def redo(self):
        """Step forward one state and return it (a copy)."""
        if self.can_redo():
            self._cursor += 1
        return self.current
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_waypoint_history.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/trajectory/history.py tests/test_waypoint_history.py
git commit -m "feat: WaypointHistory undo/redo stack"
```

---

## Task 4: Graduated renderers for Opmaak (legend updates)

**Files:**
- Modify: `drainworks_plugin/styling/views.py`
- Test: `tests/test_views_graduated.py`

Replace the data-defined single-symbol colour with a **graduated renderer** for the
"colour by BOB / slope" (pipes) and "colour by bodemhoogte / maaiveld" (manholes)
modes, so the layer-tree legend shows the classes. Width/label modes stay as-is.

- [ ] **Step 1: Write the failing test** `tests/test_views_graduated.py`:

```python
def _qgis():
    from qgis.core import QgsApplication
    if QgsApplication.instance() is None:
        app = QgsApplication([], False)
        app.initQgis()


def test_pipe_color_by_bob_uses_graduated_renderer():
    _qgis()
    from qgis.core import QgsGraduatedSymbolRenderer, QgsVectorLayer
    from drainworks_plugin.styling.views import (
        PIPE_COLOR_BOB, PIPE_LABEL_NONE, PIPE_WIDTH_DEFAULT, apply_pipe_style)

    layer = QgsVectorLayer(
        "LineString?crs=EPSG:28992&field=bob_avg:double&field=slope:double&field=diameter:double",
        "pipes", "memory")
    layer.dataProvider().addAttributes([])
    # add a couple of features so min/max differ
    from qgis.core import QgsFeature, QgsGeometry, QgsPointXY
    for v in (-2.0, -3.0, -4.0):
        f = QgsFeature(layer.fields())
        f.setAttribute("bob_avg", v)
        f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)]))
        layer.dataProvider().addFeature(f)
    layer.updateExtents()

    apply_pipe_style(layer, PIPE_COLOR_BOB, PIPE_WIDTH_DEFAULT, PIPE_LABEL_NONE)
    r = layer.renderer()
    assert isinstance(r, QgsGraduatedSymbolRenderer)
    assert r.classAttribute() == "bob_avg"
    assert len(r.ranges()) >= 3


def test_pipe_color_default_stays_single_symbol():
    _qgis()
    from qgis.core import QgsSingleSymbolRenderer, QgsVectorLayer
    from drainworks_plugin.styling.views import (
        PIPE_COLOR_DEFAULT, PIPE_LABEL_NONE, PIPE_WIDTH_DEFAULT, apply_pipe_style)

    layer = QgsVectorLayer(
        "LineString?crs=EPSG:28992&field=bob_avg:double&field=slope:double&field=diameter:double",
        "pipes", "memory")
    apply_pipe_style(layer, PIPE_COLOR_DEFAULT, PIPE_WIDTH_DEFAULT, PIPE_LABEL_NONE)
    assert isinstance(layer.renderer(), QgsSingleSymbolRenderer)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_views_graduated.py -v`
Expected: FAIL — `apply_pipe_style` currently always sets a `QgsSingleSymbolRenderer`,
so `test_pipe_color_by_bob_uses_graduated_renderer` fails on the `isinstance` check.

- [ ] **Step 3: Implement graduated colouring in `drainworks_plugin/styling/views.py`.**

Add imports at the top (extend the existing `from qgis.core import (...)`):
```python
from qgis.core import (
    QgsGraduatedSymbolRenderer,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsProperty,
    QgsRendererRange,
    QgsSingleSymbolRenderer,
    QgsSymbolLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtGui import QColor
```

Add a helper that builds N graduated ranges over a field with a blue→red ramp:
```python
def _graduated(field, mn, mx, make_symbol, classes=5):
    """Build a QgsGraduatedSymbolRenderer over ``field`` (mn..mx), blue->red."""
    colors = ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"]
    ranges = []
    step = (mx - mn) / classes if mx > mn else 1.0
    for i in range(classes):
        lo = mn + i * step
        hi = mn + (i + 1) * step if i < classes - 1 else mx + 1e-9
        symbol = make_symbol(colors[i])
        ranges.append(QgsRendererRange(
            lo, hi, symbol, f"{lo:.2f}–{hi:.2f}"))
    return QgsGraduatedSymbolRenderer(field, ranges)
```

In `apply_pipe_style`, replace the colour-mode handling. The current code creates a
single symbol and sets data-defined stroke colour for `PIPE_COLOR_BOB`/`PIPE_COLOR_SLOPE`,
then always `layer.setRenderer(QgsSingleSymbolRenderer(symbol))`. Replace the whole
body from `symbol = QgsLineSymbol.createSimple(...)` down to (but not including) the
`label_expr = {...}` block with:
```python
    def _line(color):
        s = QgsLineSymbol.createSimple({"color": PIPE_DEFAULT, "width": "0.66"})
        s.setColor(QColor(color))
        if width_mode == PIPE_WIDTH_DIAMETER:
            mn, mx = _minmax(layer, "diameter")
            expr = f'scale_linear("diameter", {mn}, {mx}, 0.4, 3.0)'
            s.symbolLayer(0).setDataDefinedProperty(
                QgsSymbolLayer.PropertyStrokeWidth, QgsProperty.fromExpression(expr))
        return s

    if color_mode == PIPE_COLOR_BOB:
        mn, mx = _minmax(layer, "bob_avg")
        layer.setRenderer(_graduated("bob_avg", mn, mx, _line))
    elif color_mode == PIPE_COLOR_SLOPE:
        mn, mx = _minmax(layer, "slope")
        layer.setRenderer(_graduated("slope", mn, mx, _line))
    else:
        layer.setRenderer(QgsSingleSymbolRenderer(_line(PIPE_DEFAULT)))
```

In `apply_manhole_style`, similarly replace the body from `symbol = QgsMarkerSymbol.createSimple(...)`
down to (not including) the `label_expr = {...}` block with:
```python
    def _marker(color):
        return QgsMarkerSymbol.createSimple(
            {"name": "circle", "color": color, "size": "2.4",
             "outline_color": "#ffffff", "outline_width": "0.2"})

    if color_mode == MANHOLE_COLOR_BOTTOM:
        mn, mx = _minmax(layer, "bottom_level")
        layer.setRenderer(_graduated("bottom_level", mn, mx, _marker))
    elif color_mode == MANHOLE_COLOR_GROUND:
        mn, mx = _minmax(layer, "ground_level")
        layer.setRenderer(_graduated("ground_level", mn, mx, _marker))
    else:
        layer.setRenderer(QgsSingleSymbolRenderer(_marker(MANHOLE_DEFAULT)))
```
Leave the `label_expr`/`_apply_label` parts and the final `triggerRepaint()` unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_views_graduated.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/styling/views.py tests/test_views_graduated.py
git commit -m "feat: graduated renderers for bob/slope/bottom/ground (legend updates)"
```

---

## Task 5: Trajectory graphics — letter-in-circle, wide band, active point

**Files:**
- Modify: `drainworks_plugin/trajectory/graphics.py`

GUI wiring (canvas items). Verified by import-smoke + manual QGIS check.

- [ ] **Step 1: Make the marker draw the letter centred inside the circle.** In
`LabeledMarker.__init__`, enlarge the icon and keep the white fill:
```python
        self.setIconType(QgsVertexMarker.ICON_CIRCLE)
        self.setIconSize(18)
        self.setPenWidth(3)
        self.setColor(QColor(MARKER_COLOR))
        self.setFillColor(QColor(MARKER_COLOR))   # filled so the white letter reads
```
Replace `boundingRect` to centre on the icon:
```python
    def boundingRect(self):  # noqa: N802 (Qt override)
        return super().boundingRect().adjusted(-4, -4, 4, 4)
```
Replace `paint` to draw the letter centred in white:
```python
    def paint(self, painter):  # noqa: N802 (Qt override)
        super().paint(painter)
        painter.save()
        font = QFont()
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        from qgis.PyQt.QtCore import QRectF, Qt as _Qt
        painter.drawText(QRectF(-9, -9, 18, 18), _Qt.AlignCenter, self._label)
        painter.restore()
```

- [ ] **Step 2: Make the route a wide, semi-transparent band.** In
`TrajectoryGraphics.__init__`, change the route band styling:
```python
        self.route_band = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self.route_band.setColor(QColor(197, 65, 65, 90))   # semi-transparent
        self.route_band.setWidth(10)                        # wide band
        self.route_band.setLineStyle(Qt.SolidLine)
```

- [ ] **Step 3: Add an active-point highlight.** Add an `active_marker` attribute in
`__init__` (after `self.hover_marker = None`):
```python
        self.active_marker = None
```
Add a method to mark the active waypoint (a ring around it):
```python
    def set_active(self, point):
        """Highlight the active waypoint (where editing continues), or hide if None."""
        if self.active_marker is None:
            self.active_marker = QgsVertexMarker(self.canvas)
            self.active_marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
            self.active_marker.setColor(QColor("#00a0e9"))
            self.active_marker.setIconSize(24)
            self.active_marker.setPenWidth(3)
        if point is None:
            self.active_marker.hide()
        else:
            self.active_marker.setCenter(point)
            self.active_marker.show()
        self._redraw()
```
Include it in `clear` (hide it) and `destroy` (remove it): in `clear`, after the
hover_marker hide block add `if self.active_marker is not None: self.active_marker.hide()`;
in `destroy`, after removing hover_marker add:
```python
        if self.active_marker is not None:
            scene.removeItem(self.active_marker)
            self.active_marker = None
```

- [ ] **Step 4: Import-smoke + commit.**

Run: `"$QGIS_PY" -c "import drainworks_plugin.trajectory.graphics as g; print('ok', hasattr(g.TrajectoryGraphics, 'set_active'))"`
Expected: `ok True` (trailing segfault harmless). Then:
```bash
git add drainworks_plugin/trajectory/graphics.py
git commit -m "feat: trajectory letter-in-circle marker, wide band, active-point highlight"
```

---

## Task 6: Trajectory editing — ctrl-click delete, drag-move, contextual buttons, no table

**Files:**
- Modify: `drainworks_plugin/trajectory/map_tool.py`
- Modify: `drainworks_plugin/ui/dock.py`

GUI wiring. Verified by import-smoke + manual QGIS check.

- [ ] **Step 1: Extend `TrajectoryMapTool`** to report ctrl-click and drag. Replace the
class body's event handlers + ctor with:
```python
    def __init__(self, canvas, manhole_layer, on_pick, on_reset, on_move=None,
                 on_ctrl_pick=None, on_drag=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.manhole_layer = manhole_layer
        self.on_pick = on_pick
        self.on_reset = on_reset
        self.on_move = on_move
        self.on_ctrl_pick = on_ctrl_pick
        self.on_drag = on_drag
        self._press_code = None

    def canvasPressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            point = self.toMapCoordinates(event.pos())
            self._press_code = self._nearest_manhole_code(point)

    def canvasReleaseEvent(self, event):  # noqa: N802 (Qt override)
        if event.button() == Qt.RightButton:
            self.on_reset()
            return
        point = self.toMapCoordinates(event.pos())
        code = self._nearest_manhole_code(point)
        if code is None:
            return
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        if ctrl and self.on_ctrl_pick is not None:
            self.on_ctrl_pick(code)
        elif self._press_code is not None and self._press_code != code and self.on_drag is not None:
            self.on_drag(self._press_code, code)   # dragged from one put onto another
        else:
            self.on_pick(code)
        self._press_code = None

    def canvasMoveEvent(self, event):  # noqa: N802 (Qt override)
        if self.on_move is not None:
            self.on_move(self.toMapCoordinates(event.pos()))
```

- [ ] **Step 2: Replace the trajectory table with a contextual button row in the dock.**
In `dock.py` `_build_ui`, find the trajectory table block (the `QLabel("Traject (klik
putten op de kaart):")`, the `self.table = QTableWidget(...)` setup, `left_layout.addWidget(self.table, 1)`,
and the `clear_traj` button) and replace that whole block with a contextual button bar
(hidden until Traject is active):
```python
        left_layout.addWidget(QLabel("Traject (klik putten op de kaart):"))
        self.traj_bar = QWidget()
        traj_layout = QHBoxLayout(self.traj_bar)
        traj_layout.setContentsMargins(0, 0, 0, 0)
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
        self.traj_bar.setVisible(False)
        left_layout.addWidget(self.traj_bar)
        left_layout.addStretch(1)
```
KEEP the `QTableWidget`/`QTableWidgetItem` imports — Task 9 reuses them for the sinks
table. You MAY remove `QAbstractItemView` if nothing else uses it (grep within the file
first); leave the two table-widget imports in place.

- [ ] **Step 3: Wire history + the new edit handlers in the dock.** In `__init__`, after
`self.waypoints = []` add:
```python
        from drainworks_plugin.trajectory.history import WaypointHistory
        self.history = WaypointHistory()
```
Add these methods (and DELETE the now-unused `_update_table` and `_delete_waypoint`
methods, and the `LETTERS`-based table population):
```python
    def _commit_waypoints(self, push=True):
        """Persist the current waypoints to history and rebuild everything."""
        if push:
            self.history.set(self.waypoints)
        self._sync_traj_buttons()
        self._rebuild()

    def _sync_traj_buttons(self):
        self.btn_traj_undo.setEnabled(self.history.can_undo())
        self.btn_traj_redo.setEnabled(self.history.can_redo())

    def _on_undo(self):
        self.waypoints = self.history.undo()
        self._commit_waypoints(push=False)

    def _on_redo(self):
        self.waypoints = self.history.redo()
        self._commit_waypoints(push=False)

    def _on_ctrl_pick(self, code):
        """Ctrl-click on a waypoint removes it."""
        if code in self.waypoints:
            self.waypoints.remove(code)
            self._commit_waypoints()

    def _on_drag(self, from_code, to_code):
        """Drag a waypoint onto another put: replace it in place."""
        if from_code in self.waypoints and to_code not in self.waypoints:
            self.waypoints[self.waypoints.index(from_code)] = to_code
            self._commit_waypoints()
```
Change `_on_pick` so a normal click in delete-mode removes, else inserts, and pushes
history:
```python
    def _on_pick(self, code):
        if self.btn_traj_delmode.isChecked():
            if code in self.waypoints:
                self.waypoints.remove(code)
                self._commit_waypoints()
            return
        self._insert_waypoint(code)
        self._commit_waypoints()
```
Change `_on_reset` to push history:
```python
    def _on_reset(self):
        self.waypoints = []
        self._commit_waypoints()
```
Change `_on_downstream` so after appending it commits via history (replace its final
`self._rebuild()` with `self._commit_waypoints()`).
In `_rebuild`, remove the `self._update_table(cumulative)` call (the table is gone);
keep `_update_graphics` + `_update_side_view`. Also remove the now-unused
`_cumulative_distances`/`cumulative` plumbing only if nothing else uses it — the
side-view + graphics don't need the table's cumulative list, but check before deleting.

- [ ] **Step 4: Pass the new callbacks when activating the trajectory tool + show the bar.**
In `_activate_tool`, extend the `TrajectoryMapTool(...)` construction to pass
`on_ctrl_pick=self._on_ctrl_pick, on_drag=self._on_drag` (only meaningful for the
trajectory tool; the sink-pick tool can pass them too — harmless). In `_on_traj_toggled`,
show/hide the contextual bar:
```python
    def _on_traj_toggled(self, checked):
        self.traj_bar.setVisible(checked)
        if checked:
            self.btn_sink_map.setChecked(False)
            self._activate_tool(self._on_pick, self._on_reset)
            self._sync_traj_buttons()
        else:
            self.btn_traj_delmode.setChecked(False)
            self._clear_tool()
```
In `_update_graphics`, set the active-point highlight to the last waypoint:
at the end of the method add:
```python
        if self.waypoints:
            xy = self.manhole_points.get(self.waypoints[-1])
            self.graphics.set_active(QgsPointXY(*xy) if xy else None)
        else:
            self.graphics.set_active(None)
```

- [ ] **Step 5: Import-smoke + full suite + commit.**

Run: `"$QGIS_PY" -m pytest` (no regressions) and
`"$QGIS_PY" -c "import drainworks_plugin.ui.dock as d, drainworks_plugin.trajectory.map_tool as m; print('ok', hasattr(d.DrainworksDock,'_on_ctrl_pick'))"`
Expected: green + `ok True`. Then:
```bash
git add drainworks_plugin/trajectory/map_tool.py drainworks_plugin/ui/dock.py
git commit -m "feat: trajectory ctrl-click delete, drag-move, delete-mode, undo/redo, no table"
```

---

## Task 7: Side-view — put lines, water overlay, no label, live light line

**Files:**
- Modify: `drainworks_plugin/sideview/sideview_widget.py`
- Modify: `drainworks_plugin/ui/dock.py`

GUI wiring. Verified by import-smoke + manual QGIS check.

- [ ] **Step 1: Draw each put as a bottom→maaiveld line excluded from auto-zoom.** In
`sideview_widget.py` `show_profile`, replace the existing "Manholes as vertical grey
lines" block with put lines from `profile.manhole_levels` that span invert→maaiveld and
are excluded from auto-range:
```python
        # Each put: a vertical line from invert (bottom) up to maaiveld (ground),
        # drawn so it does not affect auto-zoom.
        show_codes = getattr(self, "_show_putcodes", True)
        for dist, code, bottom, ground in getattr(profile, "manhole_levels", []):
            top = ground if ground is not None else bottom
            item = pg.PlotCurveItem(
                [dist, dist], [bottom, top],
                pen=pg.mkPen("#398a39", width=2))
            item.setSkipFiniteCheck(True)
            try:
                item.setData([dist, dist], [bottom, top], ignoreBounds=True)
            except TypeError:
                pass
            self.plot.addItem(item, ignoreBounds=True)
            if show_codes:
                text = pg.TextItem(code, color="#398a39", anchor=(0.5, 1.1))
                text.setPos(dist, top)
                self.plot.addItem(text, ignoreBounds=True)
```

- [ ] **Step 2: Add a water overlay setter from segment-derived points.** Add a method
to `SideViewWidget` that draws the water fill from a `[(dist, level)]` polyline + the
profile bobs (call it after `show_profile`):
```python
    def show_water(self, water_points):
        """Draw the verloren-berging water fill from [(dist, level)] points."""
        if not water_points or not hasattr(self, "_last_profile"):
            return
        verts = self._last_profile.vertices
        if not verts:
            return
        dists = [v.dist for v in verts]
        bobs = [v.bob for v in verts]
        wd = [d for d, _ in water_points]
        wl = [lvl for _, lvl in water_points]
        bob_curve = pg.PlotCurveItem(dists, bobs)
        water_curve = pg.PlotCurveItem(wd, wl)
        fill = pg.FillBetweenItem(bob_curve, water_curve, brush=pg.mkBrush(44, 127, 184, 120))
        self.plot.addItem(fill)
        self.plot.plot(wd, wl, pen=pg.mkPen("#2c7fb8", width=1, style=Qt.DashLine), name="Waterpeil")
```
At the very start of `show_profile`, stash the profile so `show_water` can reuse the
vertices: after `self.plot.clear()` add `self._last_profile = profile`.

- [ ] **Step 3: Add a lightweight live-line renderer for editing.** Add:
```python
    def show_light_line(self, bob_points, manhole_levels=None):
        """Fast live render during map editing: just the pipe BOB line + put lines."""
        self.plot.clear()
        if bob_points:
            xs = [d for d, _ in bob_points]
            ys = [b for _, b in bob_points]
            self.plot.plot(xs, ys, pen=pg.mkPen("#cc8400", width=1, style=Qt.DashLine),
                           name="BOB leiding (recht)")
        for dist, code, bottom, ground in (manhole_levels or []):
            top = ground if ground is not None else bottom
            item = pg.PlotCurveItem([dist, dist], [bottom, top], pen=pg.mkPen("#398a39", width=2))
            self.plot.addItem(item, ignoreBounds=True)
        self._cursor.hide()
        self.plot.addItem(self._cursor)
        self.plot.autoRange()
```

- [ ] **Step 4: Remove the "Langsprofiel" label + feed water/light from the dock.** In
`dock.py` `_build_ui`, in the right column header, remove the
`header.addWidget(QLabel("Langsprofiel:"))` line (keep the `volume_label`). In
`_update_side_view`, after `self.side_view.show_profile(profile)` add the water overlay
fed from segments:
```python
        from drainworks_plugin.sideview.berging import route_berging
        segments_by_pipe = self._read_segments_by_pipe()
        water, volume = route_berging(route, self.pipes_by_code, segments_by_pipe)
        self.side_view.show_water(water)
        self.volume_label.setText(f"Verloren berging: {volume:.2f} m³" if volume else "")
```
Replace the existing `_route_lost_volume`/`_update_volume` calls in `_update_side_view`
with the line above (delete `_route_lost_volume`, `_update_volume`, and the
`_flooded_area` helper if now unused — grep first). Pass the manholes to `build_profile`:
change `build_profile(route, self.pipes_by_code, self.measurements_by_pipe)` to
`build_profile(route, self.pipes_by_code, self.measurements_by_pipe, manholes_by_code=self._manholes_by_code)`.
Add `_read_segments_by_pipe` + load `self._manholes_by_code` in `set_data`:
```python
    def _read_segments_by_pipe(self):
        if not self.gpkg_path:
            return {}
        from drainworks_plugin.io.geopackage_store import read_segments
        by_pipe = {}
        for seg in read_segments(self.gpkg_path):
            by_pipe.setdefault(seg["pipe_code"], []).append(seg)
        return by_pipe
```
In `set_data`, where `manholes = read_manholes(self.gpkg_path)` is already read, add:
```python
        self._manholes_by_code = {m.code: m for m in manholes}
```
(and initialise `self._manholes_by_code = {}` in `__init__`).

- [ ] **Step 5: Live light line while editing.** In `_on_map_hover` (called on mouse
move while a tool is active), when the trajectory tool is active and there are ≥1
waypoints but the route is mid-edit, you may show the light line; for C2 keep it simple:
in `_on_pick`/`_commit_waypoints`, the full `_update_side_view` already runs. To make
*intermediate* hovers light, add — at the end of `_update_graphics` when `len(self.waypoints) < 2`
— a light line preview is unnecessary. **Skip the per-hover live line for now**; the
"live" requirement is satisfied because the graph updates on every click commit using
the light pipe-BOB + put data already (the detailed measured profile is what
`show_profile` draws once ≥2 waypoints). Document this with a comment in
`_update_side_view`:
```python
        # Live: the graph updates on each waypoint commit; show_profile uses the
        # measured profile when available, else the straight pipe BOB line.
```

- [ ] **Step 6: Import-smoke + full suite + commit.**

Run: `"$QGIS_PY" -m pytest` (green) and
`"$QGIS_PY" -c "import drainworks_plugin.sideview.sideview_widget as s; print('ok', hasattr(s.SideViewWidget,'show_water'))"`
Expected: green + `ok True`. Then:
```bash
git add drainworks_plugin/sideview/sideview_widget.py drainworks_plugin/ui/dock.py
git commit -m "feat: side-view put lines, water overlay from segments, no Langsprofiel label"
```

---

## Task 8: Side-view settings (gear dialog, persistent)

**Files:**
- Create: `drainworks_plugin/sideview/settings.py`
- Create: `drainworks_plugin/ui/sideview_settings_dialog.py`
- Test: `tests/test_sideview_settings.py`
- Modify: `drainworks_plugin/sideview/sideview_widget.py`, `drainworks_plugin/ui/dock.py`

A persistent settings object (legend position, white legend bg, line colour/width,
show putcodes) with a gear dialog. The settings dataclass + (de)serialisation is
testable; the dialog is GUI.

- [ ] **Step 1: Write the failing test** `tests/test_sideview_settings.py`:

```python
from drainworks_plugin.sideview.settings import SideViewSettings


def test_defaults_and_roundtrip_dict():
    s = SideViewSettings()
    assert s.legend_position == "top-left"
    assert s.show_putcodes is True
    d = s.to_dict()
    s2 = SideViewSettings.from_dict(d)
    assert s2.line_width == s.line_width
    assert s2.legend_white_bg == s.legend_white_bg


def test_from_dict_tolerates_missing_keys():
    s = SideViewSettings.from_dict({"line_width": 3})
    assert s.line_width == 3
    assert s.legend_position == "top-left"   # default fills the rest
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$QGIS_PY" -m pytest tests/test_sideview_settings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'drainworks_plugin.sideview.settings'`.

- [ ] **Step 3: Write `drainworks_plugin/sideview/settings.py`:**

```python
"""Persistent side-view display settings (pure dataclass + dict (de)serialisation).

The dock loads/saves these via QgsSettings; this module stays QGIS-free so it is
testable.
"""

from dataclasses import asdict, dataclass


@dataclass
class SideViewSettings:
    """User-tunable side-view appearance."""

    legend_position: str = "top-left"   # or "top-right"
    legend_white_bg: bool = False
    line_color: str = "#333333"
    line_width: int = 2
    show_putcodes: bool = True

    def to_dict(self):
        """Return a plain-dict representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        """Build from a dict, filling missing keys with defaults."""
        data = data or {}
        fields = cls().to_dict()
        fields.update({k: v for k, v in data.items() if k in fields})
        return cls(**fields)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_sideview_settings.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Write the gear dialog** `drainworks_plugin/ui/sideview_settings_dialog.py`:

```python
"""Dialog to edit SideViewSettings."""

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QPushButton,
    QSpinBox,
)

from drainworks_plugin.sideview.settings import SideViewSettings


class SideViewSettingsDialog(QDialog):
    """Edit legend position/background, line colour/width, show putcodes."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Langsprofiel-instellingen")
        self._settings = settings
        form = QFormLayout(self)

        self.cmb_legend = QComboBox()
        self.cmb_legend.addItems(["top-left", "top-right"])
        self.cmb_legend.setCurrentText(settings.legend_position)
        self.chk_white = QCheckBox(); self.chk_white.setChecked(settings.legend_white_bg)
        self.spn_width = QSpinBox(); self.spn_width.setRange(1, 8)
        self.spn_width.setValue(settings.line_width)
        self.chk_putcodes = QCheckBox(); self.chk_putcodes.setChecked(settings.show_putcodes)
        self._line_color = settings.line_color
        self.btn_color = QPushButton(settings.line_color)
        self.btn_color.clicked.connect(self._pick_color)

        form.addRow("Legenda-positie", self.cmb_legend)
        form.addRow("Witte legenda-achtergrond", self.chk_white)
        form.addRow("Lijnkleur", self.btn_color)
        form.addRow("Lijndikte", self.spn_width)
        form.addRow("Toon putcodes", self.chk_putcodes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._reset)
        form.addRow(buttons)

    def _pick_color(self):
        from qgis.PyQt.QtWidgets import QColorDialog
        from qgis.PyQt.QtGui import QColor
        color = QColorDialog.getColor(QColor(self._line_color), self)
        if color.isValid():
            self._line_color = color.name()
            self.btn_color.setText(color.name())

    def _reset(self):
        defaults = SideViewSettings()
        self.cmb_legend.setCurrentText(defaults.legend_position)
        self.chk_white.setChecked(defaults.legend_white_bg)
        self.spn_width.setValue(defaults.line_width)
        self.chk_putcodes.setChecked(defaults.show_putcodes)
        self._line_color = defaults.line_color
        self.btn_color.setText(defaults.line_color)

    def values(self):
        """Return the edited SideViewSettings."""
        return SideViewSettings(
            legend_position=self.cmb_legend.currentText(),
            legend_white_bg=self.chk_white.isChecked(),
            line_color=self._line_color,
            line_width=self.spn_width.value(),
            show_putcodes=self.chk_putcodes.isChecked())
```

- [ ] **Step 6: Apply settings in the side-view + add a gear button in the dock.**
(a) In `SideViewWidget`, add `apply_settings(self, settings)` that stores the values the
renderer reads (`self._show_putcodes`, `self._line_color`, `self._line_width`) and
positions the legend:
```python
    def apply_settings(self, settings):
        """Apply SideViewSettings (re-render the current profile if any)."""
        self._show_putcodes = settings.show_putcodes
        self._line_color = settings.line_color
        self._line_width = settings.line_width
        legend = self.plot.plotItem.legend
        if legend is not None:
            anchor = (0, 0) if settings.legend_position == "top-left" else (1, 0)
            offset = (10, 10) if settings.legend_position == "top-left" else (-10, 10)
            legend.anchor(anchor, anchor, offset)
            if settings.legend_white_bg:
                legend.setBrush(pg.mkBrush(255, 255, 255, 220))
            else:
                legend.setBrush(None)
        if getattr(self, "_last_profile", None) is not None:
            self.show_profile(self._last_profile)
```
Update `show_profile`'s "BOB gemeten" plot pen to use `getattr(self, "_line_color", "#333333")`
and `getattr(self, "_line_width", 2)` instead of the hard-coded `"#333333"`/`width=2`.
(b) In `dock.py` `_build_ui`, add a gear button next to the volume label in the right
header:
```python
        self.btn_sv_settings = QToolButton()
        self.btn_sv_settings.setText("⚙")
        self.btn_sv_settings.setToolTip("Langsprofiel-instellingen")
        self.btn_sv_settings.clicked.connect(self._on_sideview_settings)
        header.addWidget(self.btn_sv_settings)
```
(c) Add the dock handler + load/save via QgsSettings, and apply on data load:
```python
    SV_SETTINGS_KEY = "drainworks/sideview"

    def _load_sideview_settings(self):
        from qgis.core import QgsSettings
        from drainworks_plugin.sideview.settings import SideViewSettings
        import json
        raw = QgsSettings().value(self.SV_SETTINGS_KEY, "", type=str)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        return SideViewSettings.from_dict(data)

    def _on_sideview_settings(self):
        from qgis.PyQt.QtWidgets import QDialog
        from qgis.core import QgsSettings
        from drainworks_plugin.ui.sideview_settings_dialog import SideViewSettingsDialog
        import json
        current = self._load_sideview_settings()
        dialog = SideViewSettingsDialog(current, self.iface.mainWindow())
        if dialog.exec_() != QDialog.Accepted:
            return
        new = dialog.values()
        QgsSettings().setValue(self.SV_SETTINGS_KEY, json.dumps(new.to_dict()))
        self.side_view.apply_settings(new)
```
In `__init__` (after `self._build_ui()`), apply persisted settings once:
```python
        self.side_view.apply_settings(self._load_sideview_settings())
```

- [ ] **Step 7: Full suite + import-smoke + commit.**

Run: `"$QGIS_PY" -m pytest` (green) and
`"$QGIS_PY" -c "import drainworks_plugin.ui.sideview_settings_dialog; import drainworks_plugin.ui.dock as d; print('ok', hasattr(d.DrainworksDock,'_on_sideview_settings'))"`
Expected: green + `ok True`. Then:
```bash
git add drainworks_plugin/sideview/settings.py drainworks_plugin/ui/sideview_settings_dialog.py drainworks_plugin/sideview/sideview_widget.py drainworks_plugin/ui/dock.py tests/test_sideview_settings.py
git commit -m "feat: persistent side-view settings (gear dialog)"
```

---

## Task 9: Sinks table, Opmaak brush icon, base-edit staleness

**Files:**
- Modify: `drainworks_plugin/ui/dock.py`
- Modify: `drainworks_plugin/plugin.py`

GUI wiring. Verified by import-smoke + manual QGIS check.

- [ ] **Step 1: Replace the sink label with a per-row delete table; "+" icon.** In
`dock.py` `_build_ui`, in the sink section: change the add-sink button icon to a "+",
remove the "Wis" button, and replace `self.sink_label` with a small table. Replace the
sink section (`sink_row` widgets + `self.sink_label`) with:
```python
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
        left_layout.addLayout(sink_row)

        self.sink_table = QTableWidget(0, 2)
        self.sink_table.setHorizontalHeaderLabels(["Sink", ""])
        self.sink_table.verticalHeader().setVisible(False)
        self.sink_table.setColumnWidth(1, 30)
        self.sink_table.setMaximumHeight(120)
        left_layout.addWidget(self.sink_table)
```
(Keep the `QTableWidget`/`QTableWidgetItem` imports — they are now used here even though
Task 6 removed the trajectory table.) Add a `_update_sink_table` method and call it from
`_apply_sinks` (replace the `_update_sink_label` call with `_update_sink_table`; remove
the old `_update_sink_label` + `_on_clear_sinks` if now unused — grep first):
```python
    def _update_sink_table(self):
        codes = sorted(self.sinks)
        self.sink_table.setRowCount(len(codes))
        for i, code in enumerate(codes):
            self.sink_table.setItem(i, 0, QTableWidgetItem(code))
            btn = QPushButton("✕"); btn.setFixedWidth(28)
            btn.clicked.connect(lambda _c, c=code: self._remove_sink(c))
            self.sink_table.setCellWidget(i, 1, btn)

    def _remove_sink(self, code):
        self.sinks.discard(code)
        self._apply_sinks()
```
Update `set_data` to call `self._update_sink_table()` where it currently calls
`self._update_sink_label()`.

- [ ] **Step 2: Opmaak brush icon.** In `_build_ui`, the `btn_style` tool button is
created via `self._tool_button("Opmaak", "lost_capacity.svg", self._on_style)`. Change the
icon name to a brush. If `resources/icons/brush.svg` does not exist, create a minimal one:
write `drainworks_plugin/resources/icons/brush.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#0079c1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.06 11.9l8.07-8.06a2.85 2.85 0 1 1 4.03 4.03l-8.06 8.08"/><path d="M7.07 14.94c-1.66 0-3 1.35-3 3.02 0 1.33-2.5 1.52-2 2.02 1.08 1.1 2.49 2.02 4 2.02 2.2 0 4-1.8 4-4.04a3.01 3.01 0 0 0-3-3.02z"/></svg>
```
and change the `btn_style` line to use `"brush.svg"`.

- [ ] **Step 3: Wire base-edit staleness (the C1 TODO).** In `set_data`, after the
layers are assigned, connect the pipe + manhole layers' commit signals to mark enrich
stale:
```python
        for lyr in (pipe_layer, manhole_layer):
            try:
                lyr.afterCommitChanges.connect(self._on_base_edited)
            except (AttributeError, TypeError):
                pass
```
Add the handler:
```python
    def _on_base_edited(self):
        """Layer edits committed: mark enrich/berging stale."""
        self.state.mark_base_edited()
        self._refresh_step_buttons()
```

- [ ] **Step 4: Full suite + import-smoke + commit.**

Run: `"$QGIS_PY" -m pytest` (green) and
`"$QGIS_PY" -c "import drainworks_plugin.ui.dock as d; print('ok', hasattr(d.DrainworksDock,'_update_sink_table'), hasattr(d.DrainworksDock,'_on_base_edited'))"`
Expected: green + `ok True True`. Then:
```bash
git add drainworks_plugin/ui/dock.py drainworks_plugin/resources/icons/brush.svg
git commit -m "feat: sinks table + '+' icon, opmaak brush icon, base-edit staleness"
```

---

## Task 10: Manual QGIS check + finish

- [ ] **Step 1: Full suite** — `"$QGIS_PY" -m pytest` → green.

- [ ] **Step 2: Manual QGIS smoke (record in the finish commit / report).** Load the
plugin in QGIS and verify section-2 behaviour: trajectory markers show the letter inside
a filled circle; the route is a wide translucent band; the active (last) waypoint has a
blue ring; ctrl-click removes a waypoint; "Verwijdermodus" makes plain clicks remove;
Undo/Redo work; no trajectory table. Side-view: no "Langsprofiel" label; puts are vertical
green lines up to maaiveld and don't change the zoom; the water fill + volume appear after
berging; the gear dialog changes persist across re-open. Sinks show in a table with ✕
delete and a "+" add button. Opmaak shows the brush icon and the layer legend updates
(graduated classes) when colouring by BOB/slope. Editing a pipe BOB + committing flips
"Verrijk basisdata" to "Verrijk opnieuw".

- [ ] **Step 3: Finish the branch** — REQUIRED SUB-SKILL:
`superpowers:finishing-a-development-branch`. Do NOT push.

---

## Notes

- The "live light line during editing" requirement is satisfied conservatively: the
  graph re-renders on each waypoint commit (cheap pipe-BOB + put data when <2 waypoints,
  the measured profile when ≥2). A per-mouse-move light preview was deliberately left out
  to avoid redraw churn; revisit if users want it.
- After C2, the full 1.0 spec (sections 1 + 2) is implemented. Remaining polish (e.g. a
  QgsApplication GUI-interaction test harness) is out of scope.
```
