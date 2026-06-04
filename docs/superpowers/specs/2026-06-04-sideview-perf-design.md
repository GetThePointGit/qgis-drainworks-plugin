# Side-view performance + hover refinements — design (C12)

**Goal:** Make the side-view fast (stop re-reading all segments from disk on every hover),
keep the "where am I on the graph" cursor working when the trajectory tool is off, and
clear the red map hover ring when leaving the trajectory.

**Status:** decisions agreed (2026-06-04); feeds `writing-plans`.

**Builds on:** C1–C11. Touches `ui/dock.py` only.

---

## 1. Performance: cache segments + render only on change

Two causes of the slowness:
1. `_render_side_view` calls `_read_segments_by_pipe()` — a full OGR read of the whole
   `segments` layer — **on every render**, and a render happens on **every mouse move**
   during trajectory editing (the live preview).
2. The preview re-renders the whole side-view on every pixel, even when still hovering the
   same put.

Fixes:
- **Cache** `self._segments_by_pipe`: read once in `set_data` and refresh after enrich /
  berging (when the segments change). `_render_side_view` uses the cache instead of
  re-reading from disk.
- **Render-on-change**: in `_on_map_hover`, track the last hovered put code; only call
  `_preview` when the nearest put **changes** (so moving the mouse within/around the same
  put — or over empty space — doesn't re-render).

## 2. Graph cursor works with editing off

The reverse-hover (map position → vertical cursor on the graph) currently lives in
`_on_map_hover`, which only fires while a map tool is active. Move it to a handler driven by
the canvas **`xyCoordinates`** signal (emitted on every mouse move regardless of the active
tool): when a committed route exists (`route_polyline`), project the cursor onto the route
and set/clear the graph cursor. This makes the graph cursor work whether or not the
trajectory tool is on. `_on_map_hover` keeps only the editing-time work (nearest-put
highlight + preview). The signal is connected once (in `set_data`) and disconnected on
teardown.

## 3. Clear the red hover ring when leaving the trajectory

The red map hover ring (`graphics.set_hover`) is the editing-time nearest-put highlight; it
is not driven by the graph cursor. When the trajectory tool is turned off (Traject toggled
off, "Klaar", or the dock/tool deactivates), clear it: `graphics.set_hover(None)` in
`_on_traj_toggled`'s off-branch and in `deactivate_tool`.

---

## 4. Out of scope

- No change to what the side-view draws or the placement model.
- The graph→map hover (hovering the graph shows a ring on the map) stays as-is.

## 5. Defaults

- Graph cursor shown when the projected offset ≤ 14 px from the route (unchanged).
