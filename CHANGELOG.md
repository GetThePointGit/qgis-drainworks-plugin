# Changelog

All notable changes to the Drainworks QGIS plugin. Versions follow the plugin's
`metadata.txt` `version`.

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
