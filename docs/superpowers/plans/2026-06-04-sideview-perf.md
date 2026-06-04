# Side-view Performance + Hover (C12) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stop re-reading the segments layer on every hover (cache + render-on-change), drive the graph cursor from the canvas `xyCoordinates` signal so it works with editing off, and clear the red hover ring when leaving the trajectory.

**Architecture:** All in `ui/dock.py`. Verified by the suite + dock construction smoke + manual check (perf is manual).

**Spec:** `docs/superpowers/specs/2026-06-04-sideview-perf-design.md`.

**Repo:** plugin, branch `feature/sideview-perf`. Env prefix as in earlier plans. Never push (except the explicit PR step the user requested afterwards).

---

## Task 1: Cache segments + render-on-change

- [ ] In `__init__`, next to `self.measurements_by_pipe = {}` add:
```python
        self._segments_by_pipe = {}
        self._last_hover_code = None
        self._canvas_move_connected = False
```
- [ ] In `set_data`, after `self.measurements_by_pipe = self._read_profile_for_sideview()` add:
```python
        self._segments_by_pipe = self._read_segments_by_pipe()
```
- [ ] In `_render_side_view`, replace `segments_by_pipe = self._read_segments_by_pipe()` with
`segments_by_pipe = self._segments_by_pipe`.
- [ ] Refresh the cache after the steps: in `_enrich_done` after `self._reload_profile()` and
in `_loss_done` after `self.plugin.reload_pipeline_layers()` add
`self._segments_by_pipe = self._read_segments_by_pipe()`.
- [ ] In `_on_map_hover`, replace the preview call + reverse-hover block:
```python
        self.graphics.set_hover(QgsPointXY(*nearest) if nearest else None)
        # While building a trajectory, live-preview it from the BOB lines.
        if self.btn_traj.isChecked():
            self._preview(nearest_code)
        # Reverse hover: project onto the route -> show the graph cursor.
        if self.route_polyline:
            dist, offset = self._project_on_route(px, py)
            self.side_view.set_cursor(dist if offset <= mupp * 14 else None)
        else:
            self.side_view.set_cursor(None)
```
with (render only when the nearest put changes; the graph cursor moves to `_on_canvas_move`):
```python
        self.graphics.set_hover(QgsPointXY(*nearest) if nearest else None)
        # While building a trajectory, live-preview it — but only when the nearest put
        # changes, so moving within/around the same put doesn't re-render.
        if self.btn_traj.isChecked() and nearest_code != self._last_hover_code:
            self._last_hover_code = nearest_code
            self._preview(nearest_code)
```
- [ ] Commit: `feat: cache segments_by_pipe + render preview only on nearest-put change`

## Task 2: Graph cursor via xyCoordinates + clear hover ring

- [ ] In `set_data`, connect the canvas move signal once (e.g. after the graphics are created):
```python
        if not self._canvas_move_connected:
            self.iface.mapCanvas().xyCoordinates.connect(self._on_canvas_move)
            self._canvas_move_connected = True
```
- [ ] Add the handler:
```python
    def _on_canvas_move(self, point):
        """Any map mouse move: drive the graph cursor from the route (editing or not)."""
        if not self.route_polyline:
            self.side_view.set_cursor(None)
            return
        mupp = self.iface.mapCanvas().mapUnitsPerPixel()
        dist, offset = self._project_on_route(point.x(), point.y())
        self.side_view.set_cursor(dist if offset <= mupp * 14 else None)
```
- [ ] Clear the red hover ring when leaving the trajectory. In `_on_traj_toggled`'s
`else` branch add (after `removeEventFilter`):
```python
            if self.graphics is not None:
                self.graphics.set_hover(None)
            self._last_hover_code = None
```
And in `deactivate_tool`, after `self.map_tool = None` block, add:
```python
        if self.graphics is not None:
            self.graphics.set_hover(None)
```
- [ ] Disconnect on teardown. In `teardown`, after `self.deactivate_tool()` add:
```python
        try:
            self.iface.mapCanvas().xyCoordinates.disconnect(self._on_canvas_move)
        except (TypeError, RuntimeError):
            pass
```
- [ ] Commit: `feat: graph cursor via xyCoordinates (works with editing off); clear hover ring on leave`

## Task 3: Suite + construction smoke + finish

- [ ] Full suite green; dock construction smoke (`_on_canvas_move` present); manual check
(fast side-view; graph cursor on hover with Traject off; red ring gone after leaving Traject).
- [ ] (Per the user's request this round) merge to main + push + open a PR.
