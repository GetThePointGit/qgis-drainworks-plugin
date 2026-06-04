# Drainworks plugin — 1.0 refinements design

**Goal:** Restructure the plugin around an explicit three-step processing pipeline
(import → enrich → lost storage) whose middle step is independently re-runnable
after editing base data, and apply a batch of UX refinements (trajectory tool,
side-view settings, sinks table, styling), towards a 1.0 release.

**Status:** design agreed in brainstorming; this spec feeds `writing-plans`.

---

## 1. Processing pipeline (three steps)

The work splits into three steps with intermediate state persisted in the
GeoPackage, so any step can be re-run without redoing the previous ones.

### GeoPackage layers

**After step 1 — Import (RIBX / SUFRIB → base data):**
- `manholes` (Point) — `code, node_type, ground_level (maaiveld), bottom_level, is_sink`. **Editable.**
- `pipes` (LineString) — `code, manhole1, manhole2, shape, diameter, width, bob1, bob2, length, material, inspection_date`. **Editable.**
- `measurements_raw` (attribute table, no geometry) — `pipe_code, dist, value, mtype (J/K/AA), reference`. The **raw** inclination/height measurements, NOT integrated.

> Change vs current: the inclination→height integration moves out of import into
> step 2, so edited BOBs are honoured on re-run. Import only parses + stores raw.

**After step 2 — Enrich (base data → enriched base data):**
- `pipes` / `manholes` gain validation fields `valid` (int 0/1) and `issues` (text).
- `profile` (Point) — detailed computed heights per measurement point:
  `pipe_code, dist, bob, obb`. Feeds the side-view. (Berging fields added in step 3.)
- `segments` (LineString) — aggregated pieces per pipe:
  `pipe_code, dist_from, dist_to, length, bob_start, bob_end, bob_highest,
  slope_avg, diameter, n_measurements, source (measured|bob)`,
  plus empty berging fields `water_level, flooded_pct, lost_volume, flooded_length, flooded_pct_max`.

Step 2 wipes any existing berging results (clears the berging fields / re-creates
`segments`). Setting: **Corrigeer op BOB** (default true).

**After step 3 — Lost storage (+ sinks):**
- Fills the berging fields on `segments` (`water_level, flooded_pct, lost_volume,
  flooded_length, flooded_pct_max`).

### Step responsibilities

- **Step 1 (Importeren):** parse RIBX/SUFRIB → write `manholes`, `pipes`,
  `measurements_raw`. No heights, no segments, no validation.
- **Step 2 (Verrijk basisdata):** reads the (possibly edited) `manholes`/`pipes`
  + `measurements_raw`. Then:
  1. **Validation** (writes `valid`/`issues`, message-bar summary "X leidingen, Y putten met problemen"):
     - completeness: code present, bob1/bob2 present, diameter present, manhole1/2 link to existing manholes;
     - ranges: diameter within [50, 3000] mm; mean inclination magnitude ≤ 10° (≈18%) flagged otherwise; measured length within ±20% of pipe geometry length.
  2. **Heights**: per pipe with raw measurements → integrate (reverse-aware) with
     optional BOB correction → write `profile` points.
  3. **Segments**: aggregate consecutive measurement points into segments of at
     least `MIN_SEGMENT` length (default 1.0 m) — merge to avoid many tiny pieces —
     carrying the attributes above. Pipes without measurements → BOB-line segments
     of a fixed length (default 5 m) for visualisation, `source = "bob"`.
  4. Wipe old berging results.
- **Step 3 (Bereken verloren berging):** with chosen sinks, run the flood-fill and
  fill the segment berging fields. **Setting: resolution** —
  *accurate* (default): flood-fill on the detailed `profile` points, then
  aggregate flooded %/water level/volume onto each segment; or
  *fast*: flood-fill directly on segment endpoints.

### Triggers & staleness (dock buttons)

Three buttons: **Importeren**, **Verrijk basisdata**, **Bereken verloren berging**.
Staleness indication:
- editing `pipes`/`manholes` (layer edits committed) → "Verrijk basisdata" marked stale ("Verrijk opnieuw").
- re-running step 2, or changing sinks → "Bereken verloren berging" marked stale ("Herbereken").

Re-run flow: edit BOB/pipe in QGIS → commit edits → click **Verrijk basisdata** →
segments + profile rebuilt → (optionally) **Bereken verloren berging**.

### Asynchronous execution

All three steps run as a **`QgsTask`** with a progress bar, so QGIS does not
freeze on large datasets. The heavy work (parsing, integration, flood-fill,
GeoPackage writes via OGR) runs off the main thread; **layer loading and dock
updates happen in the task's `finished` callback** (main thread). While a step
runs, its button is disabled and shows progress; errors are surfaced via the
message bar on completion.

---

## 2. UX refinements

### Trajectory
- Waypoint markers: filled circle with the **letter (A/B/C) centred inside**.
- Route drawn as a **wide, semi-transparent band** so underlying data shows through
  (rubber bands always overlay layers; transparency gives the "underneath" feel).
- The **active point** (where work continues) is marked distinctly.
- **Live map editing**: click = add / smart-insert a waypoint; **ctrl-click on a
  waypoint = remove it**; drag a waypoint = move it. Also a **delete-mode toggle**
  button for users who don't use ctrl.
- **No trajectory table.** When "Traject" is active, a contextual button row appears:
  **Stroomafwaarts · Wis traject · Verwijdermodus · Undo · Redo**.

### Side-view
- Remove the "Langsprofiel" label above the graph.
- **Settings button** (gear) with: legend position (top-left default / top-right),
  white legend background, line colour/width, show put codes (default on),
  reset to defaults. Settings **persistent** (QgsSettings).
- Show each put as a **vertical line from bottom (bob) to top (maaiveld)**, drawn
  with `ignoreBounds` so it does not affect auto-zoom.
- **Live update on light data**: while the trajectory is being edited on the map,
  the graph updates live from just the **pipe BOB line** (`bob1`/`bob2` per pipe —
  the straight line, lighter even than segments) plus the put lines — trivially
  fast for live redraw. The **detailed measured profile** (`profile` points) is
  loaded and shown only once the trajectory is **finalised** (editing stops / tool
  deactivated). The graph itself stays **read-only**.

### Sinks
- Chosen sinks shown in a **table with a per-row delete button** (like the current
  trajectory table). The separate "Wis" button is removed.
- The button next to the sink combo uses a **"+" icon** (instead of the filter look).

### Styling ("Opmaak")
- New **brush icon**.
- **Layer-panel legend updates** with the choice: for "colour by BOB / slope" use a
  **graduated renderer** (classes) instead of a single symbol with data-defined
  colour, so the layer tree shows the class legend.

---

## 3. Out of scope (1.0)

- **Editing** the trajectory *in the graph* (add/move/remove via the graph). The
  graph updates live but stays read-only; editing is on the map.
- A separate validation issues table/layer (per-feature fields + summary suffice).

---

## 4. Notes / defaults to confirm during planning

- `MIN_SEGMENT` (measured) default 1.0 m; BOB-only segment length default 5 m — both configurable.
- Validation ranges: diameter [50, 3000] mm; measured-length tolerance ±20% of geometry length; mean inclination magnitude flagged above 10°. All thresholds as named constants.
- SUFRIB parsing already tolerates missing/short fields (the old tool's "fix missing column").
