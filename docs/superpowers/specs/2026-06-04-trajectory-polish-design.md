# Trajectory & dock polish — design (C4)

**Goal:** A focused polish round on the dock/trajectory: show the put bottom level in
the sinks table, fix the active-point highlight so it follows the last-clicked put, fix
single-point deletion (incl. the macOS Ctrl=right-click pitfall), auto-exit delete-mode,
give the trajectory buttons icons + text, and add tooltips to every button.

**Status:** decisions agreed in brainstorming (2026-06-04); feeds `writing-plans`.

**Builds on:** C1–C3 (current dock + trajectory tooling). Mostly `ui/dock.py`,
`trajectory/map_tool.py`, `trajectory/graphics.py`, one store helper, and a few icons.

---

## 1. Sinks table — bottom level

The sink table gains a **bodemhoogte** column: `Sink · bodem (m) · ✕` (3 columns). The
bottom level is the manhole's `bottom_level` field (lowest connected pipe BOB, already
written by `write_base`). A new store helper `read_manhole_bottom_levels(gpkg)` returns
`{code: bottom_level}`; the dock formats it (`f"{v:.2f}"`, or `—` when NULL).

## 2. Active point follows the last click

Today the active ring sits on `waypoints[-1]`, but a new pick is inserted at the cheapest
gap — so the ring lands on the wrong put and appears not to move. Fix: track the
**last-interacted put** explicitly (`self.active_code`):
- set to the clicked code on add (`_on_pick`/insert) and on a drag's target;
- set to the path end after "Stroomafwaarts";
- set to the new last waypoint (or None) after a delete / undo / redo;
- cleared on reset / no data.

`_update_graphics` highlights `active_code` (when it is still a waypoint), else hides it.

The highlight becomes a **prominent filled halo in the accent colour**: a larger
`QgsVertexMarker` circle with a semi-transparent accent fill plus a solid ring, clearly
distinct from the lettered waypoint markers.

## 3. Single-point deletion + the macOS pitfall

On macOS the OS turns **Ctrl+click into a right-click**, and right-click currently clears
the whole trajectory — hence "the whole line disappears". New behaviour during trajectory
editing:
- **Command/Ctrl-modifier left-click** removes the single nearest waypoint (unchanged
  logic; on macOS Qt maps Command→`ControlModifier`).
- **Right-click** also removes the single nearest waypoint (no longer clears all).
- **Full clear** is only the **Wis** button.

`TrajectoryMapTool` computes the nearest code on right-click and, when editing callbacks
are wired, routes both gestures to the same "remove nearest" handler. The sink-pick tool
(no editing callbacks) keeps its previous right-click = no-op reset.

## 4. Delete-mode is one-shot

After removing a point in **Verwijdermodus**, the mode toggles itself **off** (like the
"Kaart" sink-pick button), so a stray next click doesn't keep deleting.

## 5. Trajectory buttons — icons + text

The five trajectory-bar buttons (Stroomafw. · Verwijdermodus · Wis · Undo · Redo) become
`QToolButton`s with an icon and the text **beside** it (`ToolButtonTextBesideIcon`),
matching the main toolbar's look. Five small SVG icons are added under
`resources/icons/` (`downstream.svg`, `delete_mode.svg`, `clear.svg`, `undo.svg`,
`redo.svg`).

## 6. Tooltips everywhere

Every button gets a concise Dutch `setToolTip`: main toolbar (Importeren / Traject /
Opmaak / Instellingen), both step buttons + their ⚙, the sink add "+" and "Kaart"
(already have some), and the five trajectory buttons.

---

## 7. Out of scope

- No pipeline/logic changes; no new layers.
- The side-view backlog items (vertical put codes, maaiveld line) stay in
  `drainworks-backlog` for a later round.

## 8. Defaults

- Active halo: accent `#0079c1`, size ~26, semi-transparent fill (~70 alpha) + solid ring.
- Bottom-level format: 2 decimals, `—` when missing.
