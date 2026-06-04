# Dock redesign — design (C3)

**Goal:** Re-group the Drainworks dock around the three pipeline steps: a compact
main toolbar, a file-info line, two collapsible step cards (each with a wide action
button, a gear for its settings, an up-to-date indicator and a summary), and the
trajectory edit buttons relocated above the longitudinal profile.

**Status:** design agreed in brainstorming (2026-06-04); feeds `writing-plans`.

**Builds on:** the implemented 1.0 pipeline (A/B/C1/C2). This is a UI reorganisation
of `ui/dock.py` plus two small settings dialogs, one store helper, and a validation
severity split.

---

## 1. Main toolbar

Tool buttons (text under icon), left of the panel:
`Importeren · Traject · Opmaak · Instellingen`

- **Importeren** — unchanged (import dialog → `import_to_base` task → load layers).
- **Traject** — toggles the map tool AND shows the trajectory edit bar above the
  side-view (section 4). No longer a left-column concern.
- **Opmaak** — unchanged (brush icon, style dialog).
- **Instellingen** — the side-view (langsprofiel) settings gear, moved here from next
  to the volume label. Opens the existing `SideViewSettingsDialog`.
- **Stroomafwaarts is removed from the toolbar** — it lives only in the trajectory bar.

Enable/disable stays as-is (greyed until data is loaded / a step is ready).

## 2. File-info line

Directly under the toolbar, a compact, dimmed two-line block (always visible, not
collapsible):
```
Bestand: <gpkg stem>
Putten <n> · Leidingen <n> · Metingen <n>
```
Counts: `pipes` featureCount, `manholes` featureCount, `measurements_raw` feature
count. Refreshed on import and after each step. Empty ("Geen data geladen") before import.

## 3. Step cards (collapsible)

Two `QgsCollapsibleGroupBox` cards (native QGIS — gives border + title + remembered
collapse state), numbered to convey order.

### Card 1 — "1. Basisdata verrijken"
- A **⚙** tool button in the card's top-right opens the **enrich settings dialog**:
  - Corrigeer BOB (checkbox, default on)
  - Segment (min, m) — default 1.0
  - BOB-seg (m) — default 5.0
  - Persisted via QgsSettings (`drainworks/enrich`).
- A **wide "Verrijk basisdata" button** (same style as the berging button). Runs the
  `EnrichTask` using the persisted settings (no inline widgets anymore).
- An **up-to-date indicator** (coloured label): `✓ actueel` (green) when not stale,
  `⚠ verouderd — verrijk opnieuw` (amber) when `enrich_stale` and previously run.
- A **summary** line after a run: `<n> segmenten · <e> fouten · <w> waarschuwingen`.

### Card 2 — "2. Verloren berging"
- A **⚙** opens the **berging settings dialog**: Resolutie (nauwkeurig | snel),
  persisted (`drainworks/berging`).
- The **sinks block** unchanged in content: label, combo, "+" add, "Kaart", and the
  per-row-delete sink table.
- A **wide "Bereken verloren berging" button**. Runs `BergingTask` with the persisted
  resolution. Disabled (with a hint) while enrich is stale.
- An **up-to-date indicator**: `✓ actueel` / `⚠ verouderd — herbereken`.
- A **network total**: `Totaal verloren berging: <v> m³` (sum of every segment's
  `lost_volume`). The per-route total stays on the side-view graph.

Both cards re-label/re-style their action button + indicator from `PipelineState`
(extending the existing `_refresh_step_buttons`).

## 4. Trajectory bar above the side-view

When **Traject** is active, a row appears above the longitudinal profile:
```
Traject:  [Stroomafw.] [Verwijdermodus] [Wis] [↶] [↷]
```
Hidden when Traject is off. This replaces the bottom-of-left-column bar from C2 — the
buttons and their handlers are unchanged, only the parent/placement moves.

## 5. Supporting changes

- **Validation severity split** (`rgs_ribx.validate_network`): each issue is tagged
  `error` or `warning`. **Errors** = missing/unknown required data (code, bob1/bob2,
  diameter, manhole link to a non-existent node). **Warnings** = out-of-range values
  (diameter outside [50,3000] mm, measured length beyond ±20%, mean inclination > 10°).
  `set_validation` keeps writing a single joined `issues` text but the enrich summary
  returns `n_errors` + `n_warnings` (counted over pipes + manholes) for card 1.
- **`total_lost_volume(gpkg)`** store helper: sum of `lost_volume` over the `segments`
  layer (NULL-safe). The dock reads it after a berging run for card 2.
- The C1 inline settings widgets (`chk_correct_bob`, `cmb_resolution`,
  `spn_min_segment`, `spn_bob_segment`) move into the two gear dialogs; `_on_enrich`/
  `_on_loss` read the persisted settings instead of widgets.

## 6. Out of scope

- No change to the pipeline logic, layers, or the side-view rendering itself.
- No new map interactions.

## 7. Defaults

- Enrich: Corrigeer BOB on, Segment 1.0 m, BOB-seg 5.0 m. Berging: Resolutie nauwkeurig.
- Indicator colours: green `#2e7d32` (actueel), amber `#c5841f` (verouderd).
- Step settings persist across sessions (QgsSettings), like the side-view settings.
