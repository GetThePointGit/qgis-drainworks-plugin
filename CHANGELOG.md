# Changelog

All notable changes to the Drainworks QGIS plugin. Versions follow the plugin's
`metadata.txt` `version`.

## 1.0.4 — 2026-07-14

### Changed
- **Map styling line widths are now in screen pixels instead of millimetres** (pipes,
  segments and manholes). Millimetre widths render at a fixed physical size, so on-screen
  the difference between thin and thick lines — e.g. pipes sized by diameter — was hard to
  see. Pixel widths keep a constant on-screen thickness at any map scale and make the
  differences legible. Existing GeoPackages are unaffected; this only changes the applied
  symbology.
- **Raised the minimum QGIS version from 3.22 to 3.40 LTR** (`metadata.txt`
  `qgisMinimumVersion`). The old 3.22 was an unverified scaffold default; the plugin is
  tested on 3.44 and 3.40 is the supported LTR baseline.

### Fixed
- Bundled **pyqtgraph** now ships its own `LICENSE.txt` (MIT) under
  `drainworks_plugin/external/pyqtgraph/`, as its licence requires when redistributing.

## 1.0.3 — 2026-06-07

### Fixed
- **Windows: enrich and lost storage (steps 2 and 3) crashed on large datasets**, the
  same way the import did before 1.0.2 — the steps wrote/finalised the GeoPackage
  (`profile`, `segments`) inside the `QgsTask` worker thread. Both steps are now split
  into a compute half (read + computation, off-thread, GUI stays responsive) and a write
  half that runs on the **main thread**; segment-berging updates are committed in batches.
- **Stray water on the live trajectory preview.** While choosing the next point, the
  committed pipe's pool extended across the junction onto the not-yet-committed (live)
  segment, leaving a water point at its invert. Water is now stripped on the preview-only
  pipes' spans (including the junction); the live segment shows only the BOB line. A
  finalised trajectory is unaffected (it keeps extending water to the pipe end).

## 1.0.2 — 2026-06-07

### Fixed
- **Windows: importing a large RIBX crashed** with an access violation while finalising
  the GeoPackage in the background task (the bulk write completed, but closing/reopening
  the large SQLite file in a `QgsTask` worker thread access-violates on Windows). The
  GeoPackage is now **written on the main thread**; only the (pure-Python) parse runs in
  the background. Feature inserts are committed in **batches**, which is also faster on
  every platform.

### Added
- A **loading bar** when opening an existing GeoPackage (the synchronous load previously
  gave no feedback on large files).

## 1.0.0 — 2026-06-06

First public release.

- Three-step pipeline (import → enrich → lost storage / *verloren berging*), persisted in
  the GeoPackage, each step re-runnable and asynchronous with a stepped progress bar.
- Up-to-date detection via a `dw_meta` fingerprint; a schema-version check that refuses
  foreign/old GeoPackages with a clear message.
- Trajectory tool (select / insert / extend / move with reachability checks; right-click to
  remove a point or finish) and a pyqtgraph longitudinal side-view (measured invert, crown,
  BOB line, maaiveld, water / verloren-berging fill with shores and an on/off toggle).
- Styling via graduated renderers (pipes, manholes, segments).
- Backed by the pure-Python `rgs-ribx` library for parsing and the lost-capacity computation.
