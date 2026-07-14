# Drainworks — QGIS plugin

Import Dutch sewer inspection data, compute lost storage capacity (*verloren berging*),
and explore the network in a longitudinal side-view — all inside QGIS.

Drainworks turns RIBX / SUFRIB / GeoPackage sewer data into a styled map plus a
re-runnable three-step processing pipeline, and lets you pick a trajectory through the
network to inspect its profile (BOB, water level, maaiveld) in an embedded graph.

> **Status:** 1.0. The plugin depends on the pure-Python library
> [`rgs-ribx`](https://github.com/GetThePointGit/rgs-ribx) for parsing + lost-capacity
> computation.

---

## What it does

**Three-step pipeline** (state persisted in the GeoPackage; each step re-runnable; all run
asynchronously in a `QgsTask` with a **stepped** progress bar — named phases — in the
message bar):

1. **Importeren** — parse RIBX (NEN 13508-2 XML) / SUFRIB (`.rib` + `.hel`/`.rmb`) / an
   existing GeoPackage → base data (`manholes`, `pipes`) + raw inclination
   `measurements_raw`.
2. **Verrijk basisdata** — validate (completeness + ranges → `valid`/`issues`, counted as
   *fouten*/*waarschuwingen*), integrate inclination measurements into a height `profile`,
   and aggregate measured points into `segments`.
3. **Bereken verloren berging** — with the chosen sinks (outflow points), flood-fill the
   network and fill each segment's berging fields (water level, flooded %, lost volume,
   max water depth). *Accurate* (per measurement point) or *fast* (per segment).

**Trajectory + side-view** — choose a path through the network on the map (select / insert
intermediate / extend / move, with reachability checks) and inspect the longitudinal
profile (measured invert, crown, straight BOB line, maaiveld, water fill) in an embedded
[pyqtgraph](https://www.pyqtgraph.org/) view. The trajectory previews live on map and
graph while you build it.

**Styling** — graduated renderers (so the layer legend reflects the choice) for pipes
(BOB/slope), manholes (bottom/ground level), and segments (vullingsgraad / waterhoogte /
max. waterdiepte). Per-line colour/width and legend options for the side-view.

**Up-to-date detection** — a `dw_meta` table in the GeoPackage stores a fingerprint of the
base data plus the settings and summaries used. Re-opening a GeoPackage shows the steps
green (✓ actueel) when still current, and detects in-between/external base-data edits
(⚠ verouderd). `dw_meta` also stamps a **schema version**; opening a foreign/old GeoPackage
is refused up front with a clear message instead of crashing on a missing field.

---

## Installation

Quick version (from a ZIP): *Plugins → Manage and Install Plugins → Install from ZIP →*
select `drainworks-<version>.zip`. See the user manual —
**[docs/manual/06-installatie-en-publicatie.md](docs/manual/06-installatie-en-publicatie.md)** —
for the full install steps and target-machine requirements. For building the ZIP and
publishing to the QGIS plugin repository, see [Building & publishing](#building--publishing).

---

## Repository layout

```
drainworks_plugin/        # the QGIS plugin package
├── plugin.py             # plugin object: toolbar, import dispatch, layer loading
├── io/                   # GeoPackage store (pure OGR) + import controller (QGIS layers)
├── pipeline/             # enrich / berging runners, QgsTask wrappers, staleness state
├── trajectory/           # network graph, placement model, undo/redo, map tool, graphics
├── sideview/             # profile builder, berging overlay, settings, pyqtgraph widget
├── styling/              # renderers (symbology / views) + colours
├── ui/                   # dock + dialogs (Qt)
├── resources/            # icons + logo
└── external/             # vendored pyqtgraph (+ a dev symlink to rgs_ribx)
docs/                     # design specs/plans (docs/superpowers) + the user manual (docs/manual)
tests/                    # pytest suite (headless, run with the QGIS-LTR python)
scripts/                  # headless smoke + example-data generators
```

The parsing + lost-capacity logic lives in the sibling library
[`rgs-ribx`](https://github.com/GetThePointGit/rgs-ribx). For development it is wired in via
`drainworks_plugin/external/rgs_ribx` (a symlink to `../../rgs-ribx/src/rgs_ribx`); for a
published ZIP it must be **vendored** (a real copy) — see
[Building & publishing](#building--publishing).

---

## Development

The plugin imports `qgis.core`/`qgis.gui` + `osgeo`, so tests run with the QGIS Python and
the PROJ/GDAL environment:

```bash
export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3"
export PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj"
export PROJ_DATA="$PROJ_LIB"
export GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal"
export PYTHONPATH="$PWD:$HOME/Documents/GitHub/rgs-ribx/src"
"$QGIS_PY" -m pytest
```

(A teardown segfault printed *after* the pytest summary is a known-harmless QGIS shutdown
quirk; judge success by the summary line.) See **CLAUDE.md** for the full dev recipe and
conventions. The pure logic (pipeline, trajectory, sideview, styling renderers, store) is
unit-tested; the Qt/canvas/pyqtgraph GUI is verified by a headless construction smoke and a
manual QGIS pass.

---

## Building & publishing

### Build the plugin ZIP

A QGIS plugin ZIP has a single top-level `drainworks_plugin/` directory containing
`metadata.txt` and `__init__.py`. Two things matter:

1. **`rgs_ribx` must be vendored.** In development `drainworks_plugin/external/rgs_ribx` is a
   *symlink* to `../../rgs-ribx/src/rgs_ribx`; the ZIP needs a **real copy** (a symlink does
   not work on the user's machine).
2. **Excluded:** `__pycache__/`, `*.pyc`, `.DS_Store`, and the dev `rgs_ribx` symlink.

Use the bundled script (it reads the version from `metadata.txt`):

```bash
./scripts/build_plugin_zip.sh
# -> dist/drainworks-<version>.zip
```

It copies `drainworks_plugin/` to a temp dir, replaces the `rgs_ribx` symlink with a real
copy from `../rgs-ribx/src/rgs_ribx`, strips `__pycache__`, and zips it. The vendored
`pyqtgraph` under `external/` (with its `LICENSE.txt`) is kept; the working tree is left
unchanged. Verify the ZIP has real files under `external/rgs_ribx/` (not a symlink) and
`metadata.txt` at the top of the plugin directory.

### Publish to plugins.qgis.org

The official repository is **https://plugins.qgis.org**.

**One-time:**

1. Create an **OSGEO account** (used to log in to plugins.qgis.org).
2. Check `drainworks_plugin/metadata.txt`: `name`, `version`, `qgisMinimumVersion`,
   `description`, `about`, `author`, `email`, `repository`, `tracker`, `tags`, `icon`,
   `experimental`. Bump `version` for every upload (e.g. `1.0.4` → `1.0.5`) and add a
   `changelog=` entry.

**Upload:**

1. Log in to **https://plugins.qgis.org** → **Share a plugin / Upload**.
2. Upload the ZIP. The site validates `metadata.txt` and the directory structure.
3. The **first** upload needs admin approval; after that you can upload new versions
   yourself. Users get updates via **Plugins → Upgradeable**.
4. `experimental=True` hides the plugin behind QGIS's "Show also experimental plugins"; a
   public release keeps `experimental=False`.

**Approval notes:** no network traffic or heavy imports on load; no `print()` debug output
(use the QGIS message bar); a valid `LICENSE` and clear `about`/`description`; bundled
third-party code (`external/pyqtgraph`, `external/rgs_ribx`) is fine as long as the licences
are compatible (MIT here).

**Internal-only alternative:** serve the ZIP via your own `plugins.xml` on a web server and
add that URL under **Plugins → Settings → Plugin Repositories** — no approval, but you host
it yourself.

### Build the user manual (PDF)

See **[docs/manual/README.md](docs/manual/README.md)** for the `pandoc` + `tectonic` command
that renders the manual to
**[docs/manual/drainworks-handleiding.pdf](docs/manual/drainworks-handleiding.pdf)**.

---

## Documentation

- **Changelog:** [CHANGELOG.md](CHANGELOG.md).
- **User manual:** [docs/manual/](docs/manual/) (markdown, with embedded screenshots) →
  rendered **[drainworks-handleiding.pdf](docs/manual/drainworks-handleiding.pdf)**. Build
  instructions in [docs/manual/README.md](docs/manual/README.md).
- **Design history:** [docs/superpowers/specs](docs/superpowers/specs) and
  [docs/superpowers/plans](docs/superpowers/plans) — one spec + plan per increment.

## License

See [LICENSE](LICENSE).
