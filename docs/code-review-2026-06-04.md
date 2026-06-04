# Code review — 2026-06-04

A review of the plugin after the incremental 1.0 work (specs/plans under
`docs/superpowers/`). Three read-only review passes (architecture/consistency,
performance, test coverage) followed by the fixes below. Suite: **78 passing** after the
changes.

## Verdict

The structure is sound: layering is clean (pure `osgeo.ogr` in `io/`, pure logic in
`pipeline/` + `trajectory/` + `sideview/` cores, Qt only in `ui/` and the canvas/pyqtgraph
modules). No OGR leaked into the dock, no Qt into the pure cores. Findings were mostly
small cleanups + a few high-value performance wins, not structural problems.

## Fixed in this pass

**Dead code removed** (verified zero references first):
- `computed_sinks` (write-only; staleness is fingerprint-driven), `clear_graphics()`
  (uncalled), `styling.style_profile()` (profile layer isn't added to the map),
  `Profile.pipe_spans` (built, never read), the abandoned drag-to-move plumbing in
  `TrajectoryMapTool` (`on_drag`/`_press_code`/`canvasPressEvent`), and the empty
  `lostcapacity/` package.

**Performance**:
- **`SewerNetwork.shortest_path` memoised** — the graph is immutable after `set_data`, so
  hover/route queries no longer re-run Dijkstra (placement + side-view called it many times
  per mouse move). Biggest interaction-latency win.
- **Load**: `_restore_pipeline_state` no longer re-reads all segments (reuses the cached
  `_segments_by_pipe`) and only computes the (measurement-heavy) `base_fingerprint` when
  there is a stored fingerprint to compare against — so a fresh import doesn't hash 100k+
  points.
- `_render_side_view` reuses the route for the common (non-preview) case instead of
  computing it twice.
- Side-view: `skipFiniteCheck=True` on the line plots and per-point markers dropped for
  long routes (>500 vertices) — the pyqtgraph marker path was the bottleneck.

**Tests added** for previously-untested pure logic flagged by the review:
- `point_along_wkt` / `linestring_substring_wkt` (WKT geometry helpers).
- `_aggregate` (berging length-weighted math: volume, flooded %, water level, max depth).

## Deferred (noted, not done — low risk / larger or low payoff)

- **`dock.py` size (~1000 lines).** It's a legitimate GUI controller; the cleanest future
  extraction is the settings-persistence block (`_load/_save_json_settings`,
  `_load_sideview_settings`, the `_on_*_settings` handlers) → a small `ui/settings_store.py`,
  and the route↔map geometry math (`_project_on_route`, `_build_route_polyline`,
  `_point_at_distance`) → free functions in `trajectory/`. No behaviour change; do it when
  next touching those areas.
- **Profile-row construction duplicated** between `enrich.py` and `berging.py` (accurate
  path rewrites the profile to add water columns). A shared `_profile_rows(...)` helper
  would remove the seam.
- **Observation rendering** (`profile_builder` observation branch + side-view dotted lines)
  is only exercised by tests — production never passes `observations_by_pipe`. Either wire
  observations from the gpkg or document as a stub.
- **Duplicate settings loaders** `_load_sideview_settings` vs `_load_json_settings` — minor
  dedup.
- **Further perf** (only if profiled on very large data): spatial index for the
  nearest-manhole hover scan; persistent pyqtgraph curve items with `setData()` instead of
  `clear()`+re-add; pass in-memory pipes/manholes to `base_fingerprint` to avoid the load-
  time re-read (must keep the hash byte-identical to what enrich writes).

## Coverage boundary

Pure logic is well covered. GUI (`ui/`, `plugin.py`, `trajectory/{graphics,map_tool}`,
`sideview_widget`, `import_controller.load_pipeline_layers`) is intentionally left to the
construction smoke + manual checks. The SUFRIB branch of `import_to_base` is a trivial
dispatch to `build_from_sufrib`, which is thoroughly tested in `rgs-ribx`.
