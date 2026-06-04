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
- `write_base` stamps `dw_meta.schema_version` (= `geopackage_store.SCHEMA_VERSION`). On
  open, `check_base_schema` validates the layers/fields/version and returns a Dutch error
  for foreign/old GeoPackages (so reads don't crash with OGR's "Illegal field requested in
  GetField()"). Bump `SCHEMA_VERSION` when the base layers change incompatibly.
- The network graph is immutable after `set_data`; `SewerNetwork.shortest_path` is memoised.
- Settings (enrich/berging/side-view) persist via `QgsSettings` (JSON) and, per-gpkg, in
  `dw_meta`.

## Workflow used to build this

Each increment went brainstorm → spec (`docs/superpowers/specs/`) → plan
(`docs/superpowers/plans/`) → TDD/execute → review. Follow the same for substantial changes.

## Memory

Project memory lives in
`~/.claude/projects/-Users-bastiaanroos-Documents-GitHub-qgis-drainworks-plugin/memory/`
(dev/test environment, the refactor history). Check it when resuming.
