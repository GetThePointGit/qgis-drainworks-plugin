# Trajectory model + live side-view + per-point water — design (C6)

**Goal:** Make the trajectory interaction definitive and predictable (select/insert/
extend/move with reachability checks), give a live BOB-based side-view preview while
building a trajectory, stop loading the profile layer on the map, and show per-point
water levels in the graph for the accurate berging.

**Status:** decisions agreed in brainstorming (2026-06-04); feeds `writing-plans`.

**Builds on:** C1–C5. Touches a new pure `trajectory/placement.py`, `ui/dock.py`,
`io/geopackage_store.py` (profile water fields), `pipeline/berging.py`,
`io/import_controller.py`, `sideview/sideview_widget.py`.

---

## 1. Trajectory placement model (definitive)

State: one **selected** waypoint (the active/highlighted one). Clicking a manhole `M`
(pure function `place_waypoint(network, waypoints, active, M) -> (new_waypoints,
new_active) | None`):

1. **Empty trajectory** → `M` becomes the first point; selected = `M`.
2. **`M` is already a waypoint** → **select** it only (route unchanged).
3. **`M` lies on the current route** (a node the path runs through, not a waypoint) →
   insert a **labeled tussenpunt** at that position; selected = `M`.
4. **`M` is off the route** — relative to the selected waypoint (fallback: last):
   - selected is the **last** waypoint (incl. a single point) → **append** `M`;
   - selected is the **first** waypoint → **prepend** `M`;
   - selected is a **middle** waypoint → **move** it to `M`;
   - selected becomes `M`.

**Reachability:** any append/prepend/move/insert that needs a path between two nodes
that does not exist returns `None`; the dock then shows a message ("Punt niet
bereikbaar vanaf het traject.") and makes no change. `place_waypoint` is pure (uses
`SewerNetwork.shortest_path`), so it is unit-tested without QGIS.

The old cheapest-gap insert and the drag-to-move gesture are **removed** — the model
above replaces them. Deletion is unchanged (Cmd/right-click removes the nearest point;
Wis clears all; delete-mode one-shot).

## 2. Live side-view while building a trajectory

While the **Traject** button is on, the side-view is **BOB-based and live**:
- on **hover** over a manhole, the graph previews the trajectory as it *would* become
  if that put were clicked now (`place_waypoint` applied to the hovered put), drawn from
  the straight pipe **bob1→bob2** lines (no measurements) — fast;
- the committed trajectory (between hovers / after a click) is likewise drawn from the
  BOB lines.

When **Traject is off** (finalised), the side-view uses the **measured** profiles (with
the water overlay) as today. Implementation: a shared `_render_side_view(waypoints,
light)` — `light=True` builds the profile with `measurements={}` (BOB line) and shows no
water/volume; `light=False` builds with the measured profiles + water overlay + volume.

## 3. Profile layer not on the map

`load_pipeline_layers` no longer adds the `profile` point layer to the map group (the
profile feeds the side-view via `read_profile`, it isn't a map layer). `manholes`,
`pipes` and `segments` are still loaded/styled.

## 4. Per-point water for the accurate berging

Today the side-view water overlay is per **segment** in both modes. For **accurate**,
the flood-fill already runs on the detailed profile points, so persist the per-point
result and show it per point:
- `profile` layer gains `water_level` + `flooded_pct` fields (nullable); `write_profile`
  writes them, `read_profile` reads them onto each `MeasurementPoint`.
- `compute_berging(resolution="accurate")` writes the flood-filled `water_level`/
  `flooded_pct` back to the `profile` layer (for the measured pipes). `fast` does not.
- `_read_profile_for_sideview` reads those values, so `show_profile`'s existing per-point
  water fill renders them. The dock draws the **segment** water overlay (`show_water`)
  only when the profile carries **no** per-point water (i.e. fast mode). The route volume
  total stays sourced from `segments` (`route_berging`) in both modes.

---

## 5. Out of scope

- No change to the flood-fill maths or the segment aggregation.
- No new persisted state for "selected waypoint" (it is session UI state only).

## 6. Defaults

- Unreachable message: "Punt niet bereikbaar vanaf het traject."
- Live preview uses `measurements={}` → the straight bob1→bob2 line per pipe.
