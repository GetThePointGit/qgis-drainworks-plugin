# Map Styling Refinements (C10) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Draw segments above pipes, make pipes dark grey by default, and let Opmaak style the segments layer (colour by vullingsgraad / waterhoogte / max. waterdiepte), backed by a new `water_depth_max` segment field.

**Architecture:** A TDD `water_depth_max` field (store + berging aggregation); the rest is small wiring in `import_controller`, `colors`, `views`, `style_dialog`, `dock`. Verified by the suite + dock construction smoke + manual check.

**Tech Stack:** PyQt5 / `qgis.core`, `osgeo.ogr`, pytest.

**Spec:** `docs/superpowers/specs/2026-06-04-map-styling-design.md`.

**Repo:** plugin, branch `feature/map-styling`. Test/env prefix:
```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3" PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj" PROJ_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/proj" GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal" PYTHONPATH="/Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin:/Users/bastiaanroos/Documents/GitHub/rgs-ribx/src" && "$QGIS_PY" -m pytest <args>
```
Teardown segfault after the summary is harmless. **Never push.**

---

## Task 1: `water_depth_max` segment field

**Files:** Modify `drainworks_plugin/io/geopackage_store.py`, `drainworks_plugin/pipeline/berging.py`; Test `tests/test_pipeline_berging.py` (extend).

- [ ] **Step 1: Append the failing test** to `tests/test_pipeline_berging.py`:
```python
def test_accurate_fills_water_depth_max(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import read_segments
    _setup(tmp_gpkg)
    compute_berging(tmp_gpkg, resolution="accurate")
    segs = read_segments(tmp_gpkg)
    # the dip floods -> at least one segment has a positive max water depth
    assert any((s.get("water_depth_max") or 0) > 0 for s in segs)
    # depth is never negative
    assert all((s.get("water_depth_max") or 0) >= 0 for s in segs)
```

- [ ] **Step 2: Run — expect fail** (`KeyError`/None — field absent):
`"$QGIS_PY" -m pytest tests/test_pipeline_berging.py::test_accurate_fills_water_depth_max -v`

- [ ] **Step 3: Add the field to the store.** In `geopackage_store.py` change:
```python
SEGMENT_BERGING_FIELDS = ["water_level", "flooded_pct", "lost_volume",
                          "flooded_length", "flooded_pct_max"]
```
to:
```python
SEGMENT_BERGING_FIELDS = ["water_level", "flooded_pct", "lost_volume",
                          "flooded_length", "flooded_pct_max", "water_depth_max"]
```
(`write_segments`/`update_segments_berging`/`read_segments` all iterate this list, so the
new field is created, written and read automatically.)

- [ ] **Step 4: Compute it in `_aggregate`.** In `berging.py`, inside `_aggregate`, add a
running max of the per-point water depth. After the line `pts = sorted(points, key=lambda p: p.dist)`
add `depth_max = 0.0`, and inside the loop (after the `waters = [...]` block) add a depth
update using both endpoints, then include it in the returned dict. Replace the whole
`_aggregate` body's return + accumulation: change
```python
    pts = sorted(points, key=lambda p: p.dist)
    total = flooded_len = vol = pct_w = water_w = water_len = pct_max = 0.0
    for a, b in zip(pts, pts[1:]):
```
to
```python
    pts = sorted(points, key=lambda p: p.dist)
    total = flooded_len = vol = pct_w = water_w = water_len = pct_max = depth_max = 0.0
    for p in pts:
        if p.water_level is not None:
            depth_max = max(depth_max, p.water_level - p.bob)
    for a, b in zip(pts, pts[1:]):
```
and change the return dict
```python
    return {
        "flooded_pct": (pct_w / total) if total else 0.0,
        "flooded_pct_max": pct_max,
        "lost_volume": vol,
        "flooded_length": flooded_len,
        "water_level": (water_w / water_len) if water_len else None,
    }
```
to
```python
    return {
        "flooded_pct": (pct_w / total) if total else 0.0,
        "flooded_pct_max": pct_max,
        "lost_volume": vol,
        "flooded_length": flooded_len,
        "water_level": (water_w / water_len) if water_len else None,
        "water_depth_max": depth_max,
    }
```
(`water_level` is clamped to `[bob, obb]` by the flood-fill, so `water_level - bob >= 0`.)

- [ ] **Step 5: Run — expect pass:** `"$QGIS_PY" -m pytest tests/test_pipeline_berging.py -v`

- [ ] **Step 6: Commit**
```bash
git add drainworks_plugin/io/geopackage_store.py drainworks_plugin/pipeline/berging.py tests/test_pipeline_berging.py
git commit -m "feat: segment water_depth_max field (max water_level - bob) from berging"
```

---

## Task 2: Segments above pipes + dark-grey pipes

**Files:** Modify `drainworks_plugin/io/import_controller.py`, `drainworks_plugin/styling/colors.py`.

- [ ] **Step 1: Order segments above pipes.** In `load_pipeline_layers`, change:
```python
        ordered = [manhole_layer, pipe_layer]
        if segments_layer.isValid():
            ordered.append(segments_layer)
```
to:
```python
        ordered = [manhole_layer]
        if segments_layer.isValid():
            ordered.append(segments_layer)
        ordered.append(pipe_layer)
```
(Tree top→bottom becomes manholes, segments, pipes → segments draw above pipes.)

- [ ] **Step 2: Dark-grey pipe default.** In `styling/colors.py` change:
```python
PIPE_DEFAULT = "#0079c1"     # blue line — white was invisible on the canvas
```
to:
```python
PIPE_DEFAULT = "#4d4d4d"     # dark grey line (coloured segments draw on top)
```

- [ ] **Step 3: Verify + commit.**
`"$QGIS_PY" -m pytest` (green) + `"$QGIS_PY" -c "import drainworks_plugin.io.import_controller, drainworks_plugin.styling.colors as c; print('ok', c.PIPE_DEFAULT)"`.
```bash
git add drainworks_plugin/io/import_controller.py drainworks_plugin/styling/colors.py
git commit -m "feat: draw segments above pipes; dark-grey pipe default"
```

---

## Task 3: Segment styling in Opmaak

**Files:** Modify `drainworks_plugin/styling/views.py`, `drainworks_plugin/ui/style_dialog.py`, `drainworks_plugin/ui/dock.py`; Test `tests/test_views_graduated.py` (extend).

- [ ] **Step 1: Write the failing test** — append to `tests/test_views_graduated.py`:
```python
def test_segment_style_by_water_depth_uses_graduated_renderer():
    _qgis()
    from qgis.core import (QgsFeature, QgsGeometry, QgsGraduatedSymbolRenderer,
                           QgsPointXY, QgsVectorLayer)
    from drainworks_plugin.styling.views import apply_segment_style, SEGMENT_COLOR_DEPTH

    layer = QgsVectorLayer(
        "LineString?crs=EPSG:28992&field=flooded_pct:double&field=water_level:double"
        "&field=water_depth_max:double", "segments", "memory")
    for v in (0.1, 0.4, 0.9):
        f = QgsFeature(layer.fields())
        f.setAttribute("water_depth_max", v)
        f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)]))
        layer.dataProvider().addFeature(f)
    layer.updateExtents()

    apply_segment_style(layer, SEGMENT_COLOR_DEPTH)
    r = layer.renderer()
    assert isinstance(r, QgsGraduatedSymbolRenderer)
    assert r.classAttribute() == "water_depth_max"
```

- [ ] **Step 2: Run — expect fail** (`ImportError: ... apply_segment_style`):
`"$QGIS_PY" -m pytest tests/test_views_graduated.py::test_segment_style_by_water_depth_uses_graduated_renderer -v`

- [ ] **Step 3: Add `apply_segment_style` to `styling/views.py`** (after the manhole
style function). Uses the existing `_minmax`/`_graduated` helpers, and reuses the default
`style_segments` for the flooded look:
```python
SEGMENT_COLOR_FLOODED = "flooded"   # vullingsgraad
SEGMENT_COLOR_WATER = "water"       # waterhoogte
SEGMENT_COLOR_DEPTH = "depth"       # max. waterdiepte


def apply_segment_style(layer, color_mode):
    """Colour the segments layer by flooded_pct, water_level, or water_depth_max."""
    field = {SEGMENT_COLOR_WATER: "water_level",
             SEGMENT_COLOR_DEPTH: "water_depth_max"}.get(color_mode)
    if field is None:
        from drainworks_plugin.styling.symbology import style_segments
        style_segments(layer)   # default graduated flooded_pct look
        return
    mn, mx = _minmax(layer, field)

    def _seg_line(color):
        return QgsLineSymbol.createSimple({"color": color, "width": "1.6"})

    layer.setRenderer(_graduated(field, mn, mx, _seg_line))
    layer.triggerRepaint()
```

- [ ] **Step 4: Run — expect pass:** `"$QGIS_PY" -m pytest tests/test_views_graduated.py -v`

- [ ] **Step 5: Add the Segmenten section to the Opmaak dialog.** In `ui/style_dialog.py`,
add a segment colour option list + section + value. Add the class attribute (after
`MANHOLE_LABEL = [...]`):
```python
    SEGMENT_COLOR = [("Vullingsgraad", v.SEGMENT_COLOR_FLOODED),
                     ("Waterhoogte", v.SEGMENT_COLOR_WATER),
                     ("Max. waterdiepte", v.SEGMENT_COLOR_DEPTH)]
```
After the manhole section block (`layout.addLayout(mh_form)`), add:
```python
        layout.addWidget(QLabel("<b>Segmenten</b>"))
        seg_form = QFormLayout()
        self.segment_color = _combo(self.SEGMENT_COLOR, current.get("segment_color"))
        seg_form.addRow("Kleur op:", self.segment_color)
        layout.addLayout(seg_form)
```
And add to `values()`:
```python
            "segment_color": self.segment_color.currentData(),
```

- [ ] **Step 6: Wire it in the dock.** In `dock.py` `__init__`, add `segment_color` to the
`style_modes` dict:
```python
        self.style_modes = {
            "pipe_color": _v.PIPE_COLOR_DEFAULT, "pipe_width": _v.PIPE_WIDTH_DEFAULT,
            "pipe_label": _v.PIPE_LABEL_NONE, "manhole_color": _v.MANHOLE_COLOR_DEFAULT,
            "manhole_label": _v.MANHOLE_LABEL_NONE,
            "segment_color": _v.SEGMENT_COLOR_FLOODED,
        }
```
In `_on_style`, after applying the manhole style + before/with the symbology refreshes,
apply the segment style to the loaded "Segmenten" layer:
```python
        from drainworks_plugin.styling.views import (
            apply_manhole_style, apply_pipe_style, apply_segment_style)
```
(extend the existing import), and after the `apply_manhole_style(...)` call add:
```python
        from qgis.core import QgsProject
        for seg_layer in QgsProject.instance().mapLayersByName("Segmenten"):
            apply_segment_style(seg_layer, self.style_modes["segment_color"])
            self.iface.layerTreeView().refreshLayerSymbology(seg_layer.id())
```

- [ ] **Step 7: Verify + commit.**
```
"$QGIS_PY" -m pytest
"$QGIS_PY" -c "import drainworks_plugin.ui.style_dialog, drainworks_plugin.ui.dock; from drainworks_plugin.styling.views import apply_segment_style; print('ok')"
git add drainworks_plugin/styling/views.py drainworks_plugin/ui/style_dialog.py drainworks_plugin/ui/dock.py tests/test_views_graduated.py
git commit -m "feat: style segments via Opmaak (vullingsgraad / waterhoogte / max waterdiepte)"
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
p = type('P', (), {'iface': type('I', (), {'mainWindow': lambda self: mw})()})()
from drainworks_plugin.ui.dock import DrainworksDock
dock = DrainworksDock(p)
print('DOCK OK', dock.style_modes.get('segment_color'))
from drainworks_plugin.ui.style_dialog import StyleDialog
d = StyleDialog(dock.style_modes, mw); print('STYLE OK', d.values().get('segment_color'))
"
```
Expected: `DOCK OK flooded` and `STYLE OK flooded` (trailing segfault harmless).

- [ ] **Step 2: Full suite** — `"$QGIS_PY" -m pytest` → green.

- [ ] **Step 3: Manual QGIS check.** Segments draw on top of the (now dark-grey) pipes;
Opmaak → Segmenten → "Kleur op" offers Vullingsgraad / Waterhoogte / Max. waterdiepte and
applying it recolours the segments + updates the layer legend; after a berging run the
max-waterdiepte colouring shows sensible values.

- [ ] **Step 4: Finish.** REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch`.
Do NOT push.
