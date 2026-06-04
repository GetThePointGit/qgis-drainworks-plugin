# Trajectory live preview refinements — design (C9)

**Goal:** Finish the trajectory UX: a "Klaar" button, a live map preview that follows the
cursor, clearing the preview when the mouse leaves the map, a grey trajectory colour, and
a side-view that keeps the committed trajectory measured (with water) while the
live-edited part shows only the BOB line.

**Status:** decisions agreed (2026-06-04); feeds `writing-plans`.

**Builds on:** C1–C8. Touches `ui/dock.py`, `trajectory/graphics.py`, one icon.

---

## 1. "Klaar" button

In the contextual trajectory bar (above the side-view), add a **"Klaar"** button with a
check icon that turns the trajectory tool off (untoggles the main "Traject" button and
deactivates the map tool — same effect as toggling Traject off). New icon
`resources/icons/check.svg`.

## 2. Clear the live preview when the mouse leaves the map

While the trajectory tool is active, moving the mouse **off the map canvas** clears the
live preview: the side-view and the map graphics revert to the **committed** trajectory,
and the hover marker is hidden. Implemented with an event filter on the canvas viewport
(`QEvent.Leave`) installed while the tool is active and removed on deactivate.

## 3. Live map preview

While hovering during trajectory editing, the **map** updates live too: the route band
and lettered markers show the *preview* trajectory (`place_waypoint` applied to the put
under the cursor), and the active halo sits on that put. On a click (commit) or on leave,
the map shows the committed trajectory again. `_update_graphics` is refactored to
`_render_graphics(waypoints, active_code)` so it can draw either the committed or a
preview list.

## 4. Grey trajectory

The route band and the lettered waypoint markers become **grey** (`#5a5a5a`) instead of
red, so they don't clash with the red used in the side-view legend/observations. The
letters stay white inside the filled grey circle; the **active halo stays blue**
(`#0079c1`) for contrast. (Constants `MARKER_COLOR`/`ROUTE_COLOR` in `graphics.py`.)

## 5. Side-view: committed measured, live part BOB-only

The side-view stops being "fully BOB while Traject is on" (C6). Instead, for any rendered
route (committed or preview):
- pipes that belong to the **committed** trajectory (`network.route(self.waypoints)`)
  draw the **measured** invert + the water overlay + volume;
- pipes that exist only in the **preview extension** draw the straight **BOB line**, with
  no water.

Implementation: `_render_side_view(waypoints)` computes `committed_codes` =
the committed route's pipe codes, passes `build_profile` a `measurements` map limited to
those codes (so committed pipes show measured, preview-only pipes fall back to the BOB
line), and draws the water overlay + volume from the **committed** route only. When the
trajectory tool is off, `waypoints == self.waypoints` so everything is committed →
measured (the previous behaviour). The old `light` flag is removed.

---

## 6. Out of scope

- No change to the placement model itself or to the berging maths.
- The reverse hover (graph cursor ↔ map point) stays as-is.

## 7. Defaults

- Trajectory grey `#5a5a5a`; active halo blue `#0079c1` (filled, alpha 70).
- "Klaar" button: check icon + text "Klaar".
