# CLAUDE.md — Drainworks QGIS plugin

Guidance for working in this repository. (User-global rules in `~/.claude/CLAUDE.md` —
Dutch communication, NumPy-style docstrings, feature-branch git workflow, never push
without explicit instruction — still apply and take precedence.)

## What this is

A QGIS plugin that imports Dutch sewer inspection data and runs a three-step pipeline
(import → enrich → lost storage / *verloren berging*), with a trajectory tool and a
pyqtgraph side-view. Parsing + lost-capacity logic lives in the sibling pure-Python library
**`rgs-ribx`** (`~/Documents/GitHub/rgs-ribx`); this repo is the QGIS/UI layer.

## Running tests (headless)

The plugin imports `qgis.core`/`qgis.gui` + `osgeo`, so use the QGIS-LTR2 Python with the
PROJ/GDAL env and `rgs-ribx/src` on the path:

```bash
cd ~/Documents/GitHub/qgis-drainworks-plugin
export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3"
export PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj" PROJ_DATA="$PROJ_LIB"
export GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal"
export PYTHONPATH="$PWD:$HOME/Documents/GitHub/rgs-ribx/src"
"$QGIS_PY" -m pytest
```

- Do **not** `pip install` into the QGIS bundle (it upgrades numpy/pandas and breaks QGIS).
- A teardown segfault (exit 139) printed **after** the pytest summary is harmless; judge by
  the summary counts. If `-q` hides the summary behind the segfault, run without `-q`.
- `rgs-ribx` tests run from that repo with its own `.venv` (Python 3.12) or the QGIS Python.

## GUI is not unit-tested

There is no `QgsApplication` interaction harness. The pure logic (`pipeline/`,
`trajectory/{network,placement,history}`, `sideview/{berging,profile_builder,settings}`,
`styling/` renderers, `io/geopackage_store`) is unit-tested. The Qt/canvas/pyqtgraph GUI
(`ui/`, `plugin.py`, `trajectory/{graphics,map_tool}`, `sideview/sideview_widget`,
`io/import_controller.load_pipeline_layers`) is verified by a **headless construction smoke**
(build `DrainworksDock` with a stub iface under `QT_QPA_PLATFORM=offscreen`) plus a **manual
QGIS pass**. When changing the dock, run the construction smoke + the suite, then ask the
user to verify behaviour.

## Architecture / layering (keep it)

- `io/geopackage_store.py` — **pure `osgeo.ogr`** read/write of the GeoPackage layers
  (`manholes`, `pipes`, `measurements_raw`, `profile`, `segments`, `dw_meta`). No Qt.
- `pipeline/{enrich,berging,state}.py` — **pure logic** (no Qt). `tasks.py` wraps the steps
  in `QgsTask`; its `run()` is directly callable in tests.
- `trajectory/{network,placement,history}.py`, `sideview/{berging,profile_builder,settings}`
  — **pure logic**, unit-tested. `trajectory/{graphics,map_tool}` and `sideview_widget` are Qt.
- `ui/` + `plugin.py` — Qt. The dock (`ui/dock.py`) is the main controller.
- Don't leak OGR into the dock or Qt into the pure cores.

## Conventions

- Dutch UI strings; English code/identifiers; `_on_*` for Qt slots; `read_*`/`write_*` in
  the store; NumPy-style docstrings.
- Steps persist state in the GeoPackage's `dw_meta` table: a **base-data fingerprint**
  (`base_fingerprint`) + used settings + summaries. On load the dock compares the
  fingerprint to decide "actueel" vs "verouderd" (`PipelineState.restore`). If you change
  what enrich consumes, keep `base_fingerprint` consistent or staleness detection breaks.
- **GeoPackage schema version.** `write_base` stamps `dw_meta.schema_version`
  (= `geopackage_store.SCHEMA_VERSION`, currently `1`). On open, the dock's import flow
  calls `geopackage_store.check_base_schema(path)` *before* loading: it checks the required
  layers (`pipes`, `manholes`) and their required fields (`geopackage_store._REQUIRED_FIELDS`)
  plus the stored version, and returns a Dutch message (or `None` if OK). The dock shows that
  message instead of reading the gpkg — without it, foreign/old GeoPackages crash deep in the
  reads with OGR's cryptic "Illegal field requested in GetField()".
  Policy (decided with the user): **refuse incompatible GeoPackages with a clear explanation;
  do not auto-migrate** — the user re-imports from the RIBX/SUFRIB source.
  When you change the base layers incompatibly (rename/remove a required field, change a
  layer): bump `SCHEMA_VERSION`, update `_REQUIRED_FIELDS` if the field set changed, and add a
  `check_base_schema` test (`tests/test_geopackage_schema.py`).
- The network graph is immutable after `set_data`; `SewerNetwork.shortest_path` is memoised.
- Settings (enrich/berging/side-view) persist via `QgsSettings` (JSON) and, per-gpkg, in
  `dw_meta`.
- **Don't do GUI work inside `QgsTask.finished()`.** Touching the message bar or loading
  layers in the task's `finished`/`on_done` callback can corrupt QGIS' widget state and
  crash (SIGBUS in `QgsMessageBar::showItem`). Extract `task.error`/`task.result`, then
  defer the work one event-loop tick: `QTimer.singleShot(0, lambda: self._finalize(...))`
  (see `dock._enrich_done`/`_loss_done`, `plugin._import_done`).
- **GeoPackage read/write goes by field index, not name.** OGR resolves a field name to an
  index on every `GetField(name)`/`SetField(name, ...)` call; over millions of features that
  dominates. Resolve once via `geopackage_store._field_index(layer)` and read/write by index
  (`_seti`). Long pipeline steps take an `on_progress(fraction, label)` callback; the
  `QgsTask` fans it out via a `progress(pct, label)` signal (`busy.bind_progress`).

## Workflow used to build this

Each increment went brainstorm → spec (`docs/superpowers/specs/`) → plan
(`docs/superpowers/plans/`) → TDD/execute → review. Follow the same for substantial changes.

## Memory

Project memory lives in
`~/.claude/projects/-Users-bastiaanroos-Documents-GitHub-qgis-drainworks-plugin/memory/`
(dev/test environment, the refactor history). Check it when resuming.
