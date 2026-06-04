# Polish round 2 — design (C5)

**Goal:** A second polish round: restore vertical put-code labels + a maaiveld line in
the side-view, fix pipe labels in Opmaak, fix the "metingen 0" count for old gpkgs,
proper gear icons, rename the toolbar side-view button, drop the obsolete import-dialog
BOB option, and make all UI text Dutch.

**Status:** feedback agreed (2026-06-04); feeds `writing-plans`.

**Builds on:** C1–C4. Touches `sideview/sideview_widget.py`, `styling/views.py`,
`io/geopackage_store.py`, `ui/dock.py`, `ui/import_dialog.py`, `plugin.py`, + one icon.

---

## 1. Side-view — vertical put codes + maaiveld line

Keep the current solid green **invert→maaiveld** put line. In addition, per put:
- draw a **thin light full-height line** through the put (a `pg.InfiniteLine`, light
  green, width 1) with the **put code as a vertical label** beside it (rotated, like
  before C2 — `labelOpts` with `rotateAxis=(1, 0)`), shown when "putcodes" is on;
- replace the current horizontal `TextItem` put code with this vertical label.

Add a **maaiveld line** connecting the ground levels across the puts: a polyline over
`[(dist, ground_level)]` from `Profile.manhole_levels` (skip puts without a ground
level), drawn dashed/brown and **excluded from auto-zoom** (`ignoreBounds=True`), like
the put lines.

## 2. Opmaak — pipe labels work

`_apply_label` currently leaves the label placement at `AroundPoint`, which is correct
for points (manholes) but never places labels on **lines** (pipes). Fix: when the layer
is a line layer (`layer.geometryType() == QgsWkbTypes.LineGeometry`) set
`settings.placement = QgsPalLayerSettings.Line` (parallel) before applying.

## 3. "Metingen 0" for old GeoPackages

`layer_counts` counts only `measurements_raw`; an old gpkg (e.g.
`example/ribx_input_old_tool.gpkg`) has a `measurements` layer instead, so it shows 0.
Fix: the measurements count is `measurements_raw` when present, **else** `measurements`.

## 4. Gear icons

The step ⚙ buttons use the `⚙` glyph, which renders as a faint circle. Add a proper
**gear SVG** (`resources/icons/gear.svg`, clear cog teeth) and use it on both step
settings buttons (icon instead of the glyph, larger icon size ~20 px).

## 5. Toolbar side-view button → "Zijaanzicht"

The main-toolbar button that opens the side-view settings is currently labelled
"Instellingen" with the lost-capacity icon. Rename it to **"Zijaanzicht"** and give it
the **gear icon**.

## 6. Import dialog — drop the BOB option

"Corrigeer BOB-metingen" no longer belongs in the import dialog (BOB correction is an
enrich-step setting, in the enrich ⚙). Remove the checkbox; `values()` returns
`(input_path, measurement_path, output_gpkg_path)` (3-tuple); `plugin.on_import` unpacks
three values.

## 7. All text Dutch

Translate remaining English UI strings:
- `import_dialog.py`: window title "Drainworks — import sewer data" →
  "Drainworks — rioolgegevens importeren"; "Import" → "Importeren"; "Cancel" →
  "Annuleren"; "Browse…" → "Bladeren…"; the save caption "Target GeoPackage" →
  "Doel-GeoPackage".
- `plugin.py`: "Import failed: …" → "Importeren mislukt: …"; "Imported N pipes, M
  manholes." → "Geïmporteerd: N leidingen, M putten."

---

## 8. Out of scope

- No pipeline/data-model changes; old-gpkg *migration* (creating `measurements_raw`
  from a legacy `measurements` layer) is not in scope — only the count display is fixed.

## 9. Defaults

- Put light line: light green `#b5d6b5`, width 1; code label green `#398a39`, vertical.
- Maaiveld line: brown `#a0522d`, dashed, width 1, excluded from auto-zoom.
- Gear icon size ~20 px on the step ⚙ buttons.
