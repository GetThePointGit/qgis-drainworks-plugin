# Map styling refinements — design (C10)

**Goal:** Draw segments above pipes, make pipes dark grey by default, and let the Opmaak
dialog also style the segments layer (colour by vullingsgraad or waterhoogte).

**Status:** decisions agreed (2026-06-04); feeds `writing-plans`.

**Builds on:** C1–C9. Touches `io/import_controller.py`, `styling/colors.py`,
`styling/views.py`, `ui/style_dialog.py`, `ui/dock.py`.

---

## 1. Segments above pipes

In `load_pipeline_layers`, the layer order in the group becomes **manholes → segments →
pipes** (top to bottom), so the coloured `segments` draw on top of the pipe lines (and
the manhole points stay on top of everything). Only the order of `addLayer` changes.

## 2. Pipes dark grey by default

`PIPE_DEFAULT` becomes a dark grey (`#4d4d4d`) instead of blue. This is the default pipe
line colour (used by `style_pipes` on load and as the base in `apply_pipe_style`), so
pipes render dark grey under the coloured segments.

## 3. Segments styling via the Opmaak dialog

The Opmaak (StyleDialog) gains a **Segmenten** section with a "Kleur op" choice:
- **Vullingsgraad** (`flooded_pct`) — the current graduated 0–25/25–50/50–75/75–100%
  look (default), via the existing `style_segments`;
- **Waterhoogte** (`water_level`) — a graduated renderer over the segment water level;
- **Max. waterdiepte** (`water_depth_max`) — a graduated renderer over the maximum
  water depth in the segment.

New `styling/views.py`: `SEGMENT_COLOR_FLOODED` / `SEGMENT_COLOR_WATER` /
`SEGMENT_COLOR_DEPTH` + `apply_segment_style(layer, color_mode)`. The dock's
`style_modes` gains `"segment_color"` (default flooded); `_on_style` applies it to the
loaded "Segmenten" layer (found via `QgsProject.mapLayersByName("Segmenten")`, so it
works after each enrich/berging reload) and refreshes its legend. The segments layer
keeps its default graduated `flooded_pct` styling on load (unchanged).

### New segment field: `water_depth_max`

Max water depth isn't stored yet. Add **`water_depth_max`** to the segment berging fields
(`geopackage_store.SEGMENT_BERGING_FIELDS`, so `write_segments`/`update_segments_berging`/
`read_segments` carry it automatically). The berging aggregation (`pipeline/berging.py`
`_aggregate`) computes it as the **maximum over the segment's flood-filled points of
`water_level − bob`** (≥ 0; 0 where dry). Both resolutions fill it (accurate from the
detailed points, fast from the segment endpoints).

---

## 4. Out of scope

- No change to the segment data/fields or the berging maths.
- No new persisted styling state (Opmaak choices live in the session `style_modes`, as
  today for pipes/manholes).

## 5. Defaults

- Pipe default colour dark grey `#4d4d4d`. Segment colour-by default = vullingsgraad.
- Layer order: manholes, segments, pipes.
