# QGIS Drainworks Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **DEPENDS ON:** the `rgs-ribx` library plan (`2026-06-02-rgs-ribx-library.md`) must be implemented first — this plugin imports `rgs_ribx`.

**Goal:** A QGIS plugin that imports sewer data (RIBX via `rgs-ribx`, or an existing GeoPackage), shows it on the map with drainworks-style symbology, computes and visualizes "verloren berging" (lost storage), and lets the user pick a trajectory (shortest path through the network) to display a pyqtgraph longitudinal side-view.

**Architecture:** A GeoPackage is the canonical store: import writes `manholes`, `pipes`, and `measurements` layers (EPSG:28992) which are loaded into the QGIS project and styled. Pure logic (GeoPackage read/write via OGR, network graph + Dijkstra shortest path, profile assembly) lives in plain modules that are pytest-testable headlessly. QGIS-coupled glue (map tool, dock widgets, symbology renderers) is thin and manually verified in QGIS.

**Tech Stack:** QGIS 3.x (PyQGIS, `qgis.core`, `qgis.gui`), PyQt5 (`Qt5`), `rgs-ribx`, `pyqtgraph`, `osgeo.ogr`/`osgeo.gdal` (bundled in QGIS). Tests run under the QGIS Python (or a venv with `qgis`/`gdal` available) using `pytest`.

**Target repo:** `~/Documents/GitHub/qgis-drainworks-plugin` (this repo).

> **IMPORTANT — git workflow (user's global rule):** Never commit on `main`. Work happens on a feature branch (e.g. `feature/qgis-plugin`). Never `git push` unless explicitly told.

> **Dependency note (verified in this environment):** The target interpreter is **`/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3`** (Python 3.9.5, x86_64). It already has `lxml 4.5.2`, `pandas 1.3.3`, `numpy 1.20.1`, `osgeo`, `qgis.core`, `PyQt5`, and `pyqtgraph` — do **NOT** `pip install` anything into this bundle (a prior `pip install` upgraded numpy/pandas and had to be reverted; the library's dependency floors were lowered to match). `rgs_ribx` is made importable **without installing** via a tiny `sys.path` bootstrap in `drainworks_plugin/__init__.py` (Task 0) for runtime, and via `PYTHONPATH` for headless tests (Task 1). When running the QGIS Python from a shell, also export `PROJ_LIB`, `PROJ_DATA`, and `GDAL_DATA` (see Task 1) or OGR cannot resolve EPSG codes.

---

## File Structure

```
qgis-drainworks-plugin/
├── drainworks_plugin/
│   ├── __init__.py                 # classFactory(iface)
│   ├── metadata.txt                # QGIS plugin manifest
│   ├── plugin.py                   # DrainworksPlugin: initGui / unload, wiring
│   ├── resources/
│   │   └── icon.svg
│   ├── io/
│   │   ├── __init__.py
│   │   ├── geopackage_store.py     # write entities -> .gpkg, read .gpkg -> entities (OGR)
│   │   └── import_controller.py    # RIBX/GPKG -> store -> load layers (uses QGIS)
│   ├── styling/
│   │   ├── __init__.py
│   │   ├── colors.py               # drainworks status color constants
│   │   └── symbology.py            # apply renderers to pipe/manhole/measurement layers
│   ├── lostcapacity/
│   │   ├── __init__.py
│   │   └── runner.py               # read layers -> rgs_ribx.compute_lost_capacity -> write back
│   ├── trajectory/
│   │   ├── __init__.py
│   │   ├── network.py              # build adjacency from pipes, Dijkstra shortest path
│   │   └── map_tool.py             # QgsMapTool: click manholes to choose a route
│   ├── sideview/
│   │   ├── __init__.py
│   │   ├── profile_builder.py      # route -> ordered profile (dist, bob, obb, water, observations)
│   │   └── sideview_panel.py       # pyqtgraph dock widget
│   └── ui/
│       ├── __init__.py
│       └── import_dialog.py        # choose RIBX/GPKG file + import button
└── tests/
    ├── conftest.py
    ├── fixtures/minimal.ribx       # copied from rgs-ribx tests
    ├── test_geopackage_store.py
    ├── test_network.py
    ├── test_profile_builder.py
    └── test_lostcapacity_runner.py
```

**Responsibilities:**
- `io/` — turns entities into a GeoPackage and back; the only place that knows the layer schema.
- `styling/` — QGIS renderers, ported colors from drainworks.
- `trajectory/` — graph + shortest path (pure) and the click-to-pick map tool (QGIS).
- `sideview/` — assemble a profile (pure) and draw it (pyqtgraph).
- `lostcapacity/` — bridge between map layers and the `rgs-ribx` algorithm.

**GeoPackage schema (layers, all EPSG:28992):**
- `manholes` (Point): `code` (str), `node_type` (str), `ground_level` (real), `is_sink` (int 0/1)
- `pipes` (LineString): `code` (str), `manhole1` (str), `manhole2` (str), `shape` (str), `diameter` (real), `width` (real), `bob1` (real), `bob2` (real), `length` (real), `material` (str), `sewerage_type` (str), `inspection_date` (str ISO)
- `measurements` (no geometry / point): `pipe_code` (str), `dist` (real), `bob` (real), `obb` (real), `water_level` (real), `flooded_pct` (real)

---

## Task 0: Plugin scaffold that loads in QGIS

**Files:**
- Create: `drainworks_plugin/__init__.py`
- Create: `drainworks_plugin/metadata.txt`
- Create: `drainworks_plugin/plugin.py`
- Create: `drainworks_plugin/resources/icon.svg`

- [ ] **Step 1: Switch to a feature branch**

```bash
cd ~/Documents/GitHub/qgis-drainworks-plugin
git switch -c feature/qgis-plugin
```

- [ ] **Step 2: Create `drainworks_plugin/metadata.txt`**

```ini
[general]
name=Drainworks
qgisMinimumVersion=3.22
description=Import RIBX/GeoPackage sewer data, compute lost storage, show side-views.
version=0.1.0
author=Bastiaan Roos
email=bastiaan@roosgeo.nl
about=Import Dutch sewer inspection data (RIBX or GeoPackage), display it on the map, compute "verloren berging" (lost storage capacity), and view longitudinal profiles along a chosen trajectory.
tracker=https://github.com/GetThePoint/qgis-drainworks-plugin/issues
repository=https://github.com/GetThePoint/qgis-drainworks-plugin
experimental=True
deprecated=False
icon=resources/icon.svg
```

- [ ] **Step 3: Create `drainworks_plugin/resources/icon.svg`**

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <circle cx="5" cy="12" r="3" fill="#398a39"/>
  <circle cx="19" cy="12" r="3" fill="#398a39"/>
  <line x1="5" y1="12" x2="19" y2="12" stroke="#01aeed" stroke-width="3"/>
</svg>
```

- [ ] **Step 4: Create `drainworks_plugin/__init__.py`**

Includes a `sys.path` bootstrap so the plugin finds `rgs_ribx` from a sibling checkout without installing it into the QGIS Python (which must not be modified).

```python
"""Drainworks QGIS plugin entry point."""

import os
import sys


def _ensure_rgs_ribx_on_path():
    """Make ``rgs_ribx`` importable without installing it into QGIS's Python.

    Tries a normal import first; if that fails, falls back to a sibling
    ``rgs-ribx`` checkout's ``src`` directory. Adjust the fallback path if your
    checkout lives elsewhere.
    """
    try:
        import rgs_ribx  # noqa: F401
        return
    except ImportError:
        pass
    candidates = [
        os.path.expanduser("~/Documents/GitHub/rgs-ribx/src"),
        os.path.join(os.path.dirname(__file__), "..", "..", "rgs-ribx", "src"),
    ]
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)
            return


_ensure_rgs_ribx_on_path()


def classFactory(iface):  # noqa: N802 (QGIS-required name)
    """Return the plugin instance. Called by QGIS when loading the plugin.

    Parameters
    ----------
    iface : qgis.gui.QgisInterface
        The running QGIS interface handed in by QGIS.
    """
    from drainworks_plugin.plugin import DrainworksPlugin

    return DrainworksPlugin(iface)
```

- [ ] **Step 5: Create `drainworks_plugin/plugin.py` (minimal toolbar action)**

```python
"""Main plugin object: registers a toolbar button and menu entry."""

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

PLUGIN_DIR = os.path.dirname(__file__)


class DrainworksPlugin:
    """Wires the plugin into the QGIS GUI."""

    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.menu = "&Drainworks"

    def initGui(self):  # noqa: N802 (QGIS-required name)
        """Create toolbar/menu actions. Called by QGIS on plugin load."""
        icon = QIcon(os.path.join(PLUGIN_DIR, "resources", "icon.svg"))
        action = QAction(icon, "Import sewer data…", self.iface.mainWindow())
        action.triggered.connect(self.on_import)
        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)

    def unload(self):
        """Remove actions. Called by QGIS on plugin unload."""
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        self.actions = []

    def on_import(self):
        """Placeholder hook, replaced in Task 3."""
        self.iface.messageBar().pushInfo("Drainworks", "Import action (not wired yet).")
```

- [ ] **Step 6: Manual verification in QGIS**

1. Symlink the plugin into the QGIS plugins folder:
   ```bash
   QGIS_PLUGINS="$HOME/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins"
   mkdir -p "$QGIS_PLUGINS"
   ln -snf ~/Documents/GitHub/qgis-drainworks-plugin/drainworks_plugin "$QGIS_PLUGINS/drainworks_plugin"
   ```
2. Start QGIS → Plugins → Manage and Install Plugins → enable "Drainworks".
3. Confirm a toolbar icon appears; click it and see the info message "Import action (not wired yet)."

Expected: plugin loads with no Python errors in the QGIS log; clicking shows the message.

- [ ] **Step 7: Commit**

```bash
git add drainworks_plugin/__init__.py drainworks_plugin/metadata.txt drainworks_plugin/plugin.py drainworks_plugin/resources/icon.svg
git commit -m "feat: QGIS plugin scaffold with toolbar action"
```

---

## Task 1: Test harness + dependency check

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/fixtures/minimal.ribx`
- Create: `tests/test_dependencies.py`

- [ ] **Step 1: Copy the RIBX fixture from the library tests**

```bash
mkdir -p ~/Documents/GitHub/qgis-drainworks-plugin/tests/fixtures
cp ~/Documents/GitHub/rgs-ribx/tests/fixtures/minimal.ribx \
   ~/Documents/GitHub/qgis-drainworks-plugin/tests/fixtures/minimal.ribx
```

- [ ] **Step 2: Create `tests/conftest.py`**

```python
import sys
from pathlib import Path

import pytest

# Make the plugin package importable when running pytest from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def tmp_gpkg(tmp_path) -> Path:
    return tmp_path / "sewer.gpkg"
```

- [ ] **Step 3: Write `tests/test_dependencies.py`**

```python
def test_rgs_ribx_importable():
    import rgs_ribx

    assert hasattr(rgs_ribx, "build_from_ribx")


def test_ogr_importable():
    from osgeo import ogr

    assert ogr.GetDriverByName("GPKG") is not None


def test_pyqtgraph_importable():
    import pyqtgraph  # noqa: F401
```

- [ ] **Step 4: Run the tests under the QGIS Python (no installs)**

Use the QGIS-LTR2 Python; make `rgs_ribx` visible with `PYTHONPATH` and set the PROJ/GDAL data dirs so OGR can resolve EPSG codes. Define this canonical command once and reuse it for every later `pytest` step:

```bash
export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3"
export PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj"
export PROJ_DATA="$PROJ_LIB"
export GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal"
export PYTHONPATH="$HOME/Documents/GitHub/qgis-drainworks-plugin:$HOME/Documents/GitHub/rgs-ribx/src"

cd ~/Documents/GitHub/qgis-drainworks-plugin
"$QGIS_PY" -m pytest tests/test_dependencies.py -v
```
Expected: PASS (3 passed). Do NOT `pip install` anything into the QGIS bundle — `rgs_ribx` resolves via `PYTHONPATH`, and `osgeo`/`pyqtgraph`/`pandas`/`lxml` are already present.

> Every later `pytest` step assumes these five env vars are exported in the shell.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/fixtures/minimal.ribx tests/test_dependencies.py
git commit -m "test: harness and dependency checks"
```

---

## Task 2: GeoPackage store (write/read entities)

**Files:**
- Create: `drainworks_plugin/io/__init__.py`
- Create: `drainworks_plugin/io/geopackage_store.py`
- Test: `tests/test_geopackage_store.py`

Pure OGR — no QGIS — so it runs headlessly. Writes the three layers and reads them back into entities.

- [ ] **Step 1: Create `drainworks_plugin/io/__init__.py`** (empty)

```python
```

- [ ] **Step 2: Write the failing test `tests/test_geopackage_store.py`**

```python
import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    MeasurementRow,
    read_pipes,
    write_geopackage,
)


def _build(fixtures_dir):
    return rgs_ribx.build_from_ribx(fixtures_dir / "minimal.ribx")


def test_write_creates_three_layers(fixtures_dir, tmp_gpkg):
    result = _build(fixtures_dir)
    write_geopackage(tmp_gpkg, result.manholes, result.pipes, measurements=[])

    from osgeo import ogr

    ds = ogr.Open(str(tmp_gpkg))
    names = {ds.GetLayer(i).GetName() for i in range(ds.GetLayerCount())}
    assert {"manholes", "pipes", "measurements"} <= names


def test_pipe_roundtrip_preserves_attributes(fixtures_dir, tmp_gpkg):
    result = _build(fixtures_dir)
    write_geopackage(tmp_gpkg, result.manholes, result.pipes, measurements=[])

    pipes = {p.code: p for p in read_pipes(tmp_gpkg)}
    assert "L001" in pipes
    pipe = pipes["L001"]
    assert pipe.manhole1 == "P001"
    assert pipe.bob1 == -2.5
    assert pipe.diameter == 0.3
    assert pipe.geometry_wkt.startswith("LINESTRING")


def test_measurements_written_and_typed(fixtures_dir, tmp_gpkg):
    result = _build(fixtures_dir)
    rows = [MeasurementRow(pipe_code="L001", dist=15.0, bob=-2.3, obb=-2.0,
                           water_level=-2.0, flooded_pct=0.5)]
    write_geopackage(tmp_gpkg, result.manholes, result.pipes, measurements=rows)

    from osgeo import ogr

    ds = ogr.Open(str(tmp_gpkg))
    layer = ds.GetLayerByName("measurements")
    assert layer.GetFeatureCount() == 1
    feat = layer.GetNextFeature()
    assert feat.GetField("pipe_code") == "L001"
    assert feat.GetField("flooded_pct") == 0.5
```

- [ ] **Step 3: Write `drainworks_plugin/io/geopackage_store.py`**

```python
"""Write/read the sewer GeoPackage. Pure OGR (no QGIS) so it is testable.

Layers (EPSG:28992): manholes (Point), pipes (LineString), measurements (Point,
empty geometry — used as an attribute table for lost-capacity results).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from osgeo import ogr, osr

import rgs_ribx

RD_EPSG = 28992


@dataclass
class MeasurementRow:
    """A row for the ``measurements`` layer (lost-capacity output)."""

    pipe_code: str
    dist: float
    bob: float
    obb: float
    water_level: Optional[float] = None
    flooded_pct: Optional[float] = None


def _srs() -> "osr.SpatialReference":
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(RD_EPSG)
    return srs


def _set(feature, name, value) -> None:
    """Set a field, leaving it NULL when value is None."""
    if value is None:
        feature.SetFieldNull(name)
    else:
        feature.SetField(name, value)


def write_geopackage(path, manholes, pipes, measurements) -> Path:
    """Create (overwrite) a GeoPackage with manholes, pipes, measurements."""
    path = Path(path)
    if path.exists():
        path.unlink()

    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(str(path))
    srs = _srs()

    _write_manholes(ds, srs, manholes)
    _write_pipes(ds, srs, pipes)
    _write_measurements(ds, srs, measurements)

    ds = None  # flush + close
    return path


def _write_manholes(ds, srs, manholes) -> None:
    layer = ds.CreateLayer("manholes", srs, ogr.wkbPoint)
    layer.CreateField(ogr.FieldDefn("code", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("node_type", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("ground_level", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("is_sink", ogr.OFTInteger))
    defn = layer.GetLayerDefn()
    for m in manholes:
        feat = ogr.Feature(defn)
        _set(feat, "code", m.code)
        _set(feat, "node_type", m.node_type)
        _set(feat, "ground_level", m.ground_level)
        feat.SetField("is_sink", 1 if m.is_sink else 0)
        if m.geometry_wkt:
            feat.SetGeometry(ogr.CreateGeometryFromWkt(m.geometry_wkt))
        layer.CreateFeature(feat)
        feat = None


def _write_pipes(ds, srs, pipes) -> None:
    layer = ds.CreateLayer("pipes", srs, ogr.wkbLineString)
    str_fields = ["code", "manhole1", "manhole2", "shape", "material",
                  "sewerage_type", "inspection_date"]
    real_fields = ["diameter", "width", "bob1", "bob2", "length"]
    for name in str_fields:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTString))
    for name in real_fields:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
    defn = layer.GetLayerDefn()
    for p in pipes:
        feat = ogr.Feature(defn)
        _set(feat, "code", p.code)
        _set(feat, "manhole1", p.manhole1)
        _set(feat, "manhole2", p.manhole2)
        _set(feat, "shape", p.shape)
        _set(feat, "material", p.material)
        _set(feat, "sewerage_type", p.sewerage_type)
        _set(feat, "inspection_date", p.inspection_date.isoformat() if p.inspection_date else None)
        _set(feat, "diameter", p.diameter)
        _set(feat, "width", p.width)
        _set(feat, "bob1", p.bob1)
        _set(feat, "bob2", p.bob2)
        _set(feat, "length", p.length)
        if p.geometry_wkt:
            feat.SetGeometry(ogr.CreateGeometryFromWkt(p.geometry_wkt))
        layer.CreateFeature(feat)
        feat = None


def _write_measurements(ds, srs, measurements) -> None:
    layer = ds.CreateLayer("measurements", srs, ogr.wkbPoint)
    layer.CreateField(ogr.FieldDefn("pipe_code", ogr.OFTString))
    for name in ["dist", "bob", "obb", "water_level", "flooded_pct"]:
        layer.CreateField(ogr.FieldDefn(name, ogr.OFTReal))
    defn = layer.GetLayerDefn()
    for row in measurements:
        feat = ogr.Feature(defn)
        _set(feat, "pipe_code", row.pipe_code)
        _set(feat, "dist", row.dist)
        _set(feat, "bob", row.bob)
        _set(feat, "obb", row.obb)
        _set(feat, "water_level", row.water_level)
        _set(feat, "flooded_pct", row.flooded_pct)
        layer.CreateFeature(feat)
        feat = None


def read_pipes(path) -> list:
    """Read the ``pipes`` layer back into rgs_ribx.Pipe entities."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("pipes")
    pipes = []
    for feat in layer:
        geom = feat.GetGeometryRef()
        date_str = feat.GetField("inspection_date")
        inspection_date = None
        if date_str:
            from datetime import date

            inspection_date = date.fromisoformat(date_str)
        pipes.append(
            rgs_ribx.Pipe(
                code=feat.GetField("code"),
                manhole1=feat.GetField("manhole1"),
                manhole2=feat.GetField("manhole2"),
                geometry_wkt=geom.ExportToWkt() if geom else None,
                shape=feat.GetField("shape") or "A",
                diameter=feat.GetField("diameter"),
                width=feat.GetField("width"),
                bob1=feat.GetField("bob1"),
                bob2=feat.GetField("bob2"),
                length=feat.GetField("length"),
                material=feat.GetField("material"),
                sewerage_type=feat.GetField("sewerage_type"),
                inspection_date=inspection_date,
            )
        )
    return pipes


def read_manholes(path) -> list:
    """Read the ``manholes`` layer back into rgs_ribx.Manhole entities."""
    ds = ogr.Open(str(path))
    layer = ds.GetLayerByName("manholes")
    manholes = []
    for feat in layer:
        geom = feat.GetGeometryRef()
        manholes.append(
            rgs_ribx.Manhole(
                code=feat.GetField("code"),
                geometry_wkt=geom.ExportToWkt() if geom else None,
                node_type=feat.GetField("node_type"),
                ground_level=feat.GetField("ground_level"),
                is_sink=bool(feat.GetField("is_sink")),
            )
        )
    return manholes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_geopackage_store.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/io/__init__.py drainworks_plugin/io/geopackage_store.py tests/test_geopackage_store.py
git commit -m "feat: GeoPackage store (write entities, read pipes/manholes)"
```

---

## Task 3: Import controller + dialog (RIBX -> GeoPackage -> map)

**Files:**
- Create: `drainworks_plugin/io/import_controller.py`
- Create: `drainworks_plugin/ui/__init__.py`
- Create: `drainworks_plugin/ui/import_dialog.py`
- Modify: `drainworks_plugin/plugin.py`

This is QGIS-coupled (loads layers into the project). Verified manually in QGIS; the GeoPackage-writing path it relies on is already tested in Task 2.

- [ ] **Step 1: Write `drainworks_plugin/io/import_controller.py`**

```python
"""Orchestrate import: RIBX or GeoPackage -> stored .gpkg -> loaded map layers."""

from pathlib import Path

from qgis.core import QgsProject, QgsVectorLayer

import rgs_ribx

from drainworks_plugin.io.geopackage_store import write_geopackage


def import_ribx(ribx_path, gpkg_path) -> "tuple[QgsVectorLayer, QgsVectorLayer]":
    """Parse a RIBX file, write a GeoPackage, and load its layers.

    Returns
    -------
    (manhole_layer, pipe_layer) : tuple of QgsVectorLayer
    """
    result = rgs_ribx.build_from_ribx(ribx_path)
    write_geopackage(gpkg_path, result.manholes, result.pipes, measurements=[])
    return load_geopackage_layers(gpkg_path)


def load_geopackage_layers(gpkg_path) -> "tuple[QgsVectorLayer, QgsVectorLayer]":
    """Load manholes + pipes layers from a GeoPackage into the QGIS project."""
    gpkg_path = Path(gpkg_path)
    pipe_layer = QgsVectorLayer(f"{gpkg_path}|layername=pipes", "Leidingen", "ogr")
    manhole_layer = QgsVectorLayer(f"{gpkg_path}|layername=manholes", "Putten", "ogr")
    if not pipe_layer.isValid() or not manhole_layer.isValid():
        raise RuntimeError(f"Could not load layers from {gpkg_path}")
    project = QgsProject.instance()
    project.addMapLayer(pipe_layer)
    project.addMapLayer(manhole_layer)
    return manhole_layer, pipe_layer
```

- [ ] **Step 2: Write `drainworks_plugin/ui/__init__.py`** (empty)

```python
```

- [ ] **Step 3: Write `drainworks_plugin/ui/import_dialog.py`**

```python
"""Import dialog: pick a RIBX or GeoPackage file and a target GeoPackage."""

import os

from qgis.PyQt.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class ImportDialog(QDialog):
    """Collect the input file and output GeoPackage path."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Drainworks — import sewer data")
        self.input_path = QLineEdit()
        self.output_path = QLineEdit()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("RIBX or GeoPackage to import:"))
        layout.addLayout(self._row(self.input_path, self._browse_input))
        layout.addWidget(QLabel("Target GeoPackage (created/overwritten):"))
        layout.addLayout(self._row(self.output_path, self._browse_output))

        buttons = QHBoxLayout()
        ok = QPushButton("Import")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _row(self, line_edit, handler):
        row = QHBoxLayout()
        browse = QPushButton("Browse…")
        browse.clicked.connect(handler)
        row.addWidget(line_edit)
        row.addWidget(browse)
        return row

    def _browse_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select RIBX or GeoPackage", "", "Sewer data (*.ribx *.xml *.gpkg)"
        )
        if path:
            self.input_path.setText(path)
            if not self.output_path.text():
                base = os.path.splitext(path)[0]
                self.output_path.setText(base + ".gpkg")

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Target GeoPackage", "", "GeoPackage (*.gpkg)")
        if path:
            self.output_path.setText(path)

    def values(self):
        """Return (input_path, output_gpkg_path) as strings."""
        return self.input_path.text(), self.output_path.text()
```

- [ ] **Step 4: Wire the dialog into `drainworks_plugin/plugin.py`**

Replace the `on_import` method body. Find:

```python
    def on_import(self):
        """Placeholder hook, replaced in Task 3."""
        self.iface.messageBar().pushInfo("Drainworks", "Import action (not wired yet).")
```

Replace with:

```python
    def on_import(self):
        """Open the import dialog and import the selected file."""
        from qgis.PyQt.QtWidgets import QDialog

        from drainworks_plugin.io.import_controller import (
            import_ribx,
            load_geopackage_layers,
        )
        from drainworks_plugin.ui.import_dialog import ImportDialog

        dialog = ImportDialog(self.iface.mainWindow())
        if dialog.exec_() != QDialog.Accepted:
            return
        input_path, gpkg_path = dialog.values()
        if not input_path:
            return
        try:
            if input_path.lower().endswith(".gpkg"):
                manhole_layer, pipe_layer = load_geopackage_layers(input_path)
            else:
                manhole_layer, pipe_layer = import_ribx(input_path, gpkg_path)
        except Exception as exc:  # surface to the user, don't crash QGIS
            self.iface.messageBar().pushCritical("Drainworks", f"Import failed: {exc}")
            return
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Imported {pipe_layer.featureCount()} pipes, "
            f"{manhole_layer.featureCount()} manholes.",
        )
```

- [ ] **Step 5: Manual verification in QGIS**

1. Reload the plugin (Plugin Reloader, or restart QGIS).
2. Click the Drainworks toolbar button → dialog opens.
3. Select `tests/fixtures/minimal.ribx`, accept the suggested `.gpkg` output, click Import.
4. Confirm "Leidingen" and "Putten" layers appear and draw at the fixture coordinates (around 100000, 400000 in EPSG:28992). Set the project CRS to EPSG:28992 if features look misplaced.

Expected: success message "Imported 1 pipes, 2 manholes."; layers visible.

- [ ] **Step 6: Commit**

```bash
git add drainworks_plugin/io/import_controller.py drainworks_plugin/ui/ drainworks_plugin/plugin.py
git commit -m "feat: import dialog and RIBX/GeoPackage import controller"
```

---

## Task 4: Drainworks-style symbology

**Files:**
- Create: `drainworks_plugin/styling/__init__.py`
- Create: `drainworks_plugin/styling/colors.py`
- Create: `drainworks_plugin/styling/symbology.py`
- Modify: `drainworks_plugin/io/import_controller.py`

Port the drainworks status colors and apply simple renderers: pipes as colored lines, manholes as colored circles. Initial view colors by `sewerage_type` (data we have); status views can be added later.

- [ ] **Step 1: Create `drainworks_plugin/styling/__init__.py`** (empty)

```python
```

- [ ] **Step 2: Write `drainworks_plugin/styling/colors.py`**

```python
"""Color constants ported from drainworks (packages/drainworks-api map styles)."""

# Object status colors (dark theme base.ts).
STATUS_COLORS = {
    "Geen": "#c54141",
    "Compleet": "#398a39",
    "Uitgevoerd": "#b7f31c",
    "UitgevoerdTijdelijk": "#01aeed",
    "WachtOpGoedkeuring": "#edc708",
    "WerkNietMogelijk": "#F89DE9",
    "AndereEigenaar": "#5b5a5a",
    "IsNieuw": "#775b94",
}

# Pipe outline default.
PIPE_DEFAULT = "#ffffff"
MANHOLE_DEFAULT = "#398a39"

# Lost-capacity color ramp endpoints (dry -> fully flooded).
FLOODED_LOW = "#2c7fb8"    # blue, low loss
FLOODED_HIGH = "#c54141"   # red, high loss
```

- [ ] **Step 3: Write `drainworks_plugin/styling/symbology.py`**

```python
"""Apply renderers to the sewer layers."""

from qgis.core import (
    QgsGraduatedSymbolRenderer,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsRendererRange,
)
from qgis.PyQt.QtGui import QColor

from drainworks_plugin.styling.colors import (
    FLOODED_HIGH,
    FLOODED_LOW,
    MANHOLE_DEFAULT,
    PIPE_DEFAULT,
)


def style_pipes(layer) -> None:
    """Render pipes as white lines, width 0.6 mm."""
    symbol = QgsLineSymbol.createSimple({"color": PIPE_DEFAULT, "width": "0.6"})
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def style_manholes(layer) -> None:
    """Render manholes as green circles, size 2.4 mm."""
    symbol = QgsMarkerSymbol.createSimple(
        {"name": "circle", "color": MANHOLE_DEFAULT, "size": "2.4"}
    )
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def style_measurements_by_flooded(layer) -> None:
    """Graduated blue->red renderer on the ``flooded_pct`` field (0..1)."""
    ranges = []
    steps = [
        (0.0, 0.25, FLOODED_LOW),
        (0.25, 0.5, "#7fcdbb"),
        (0.5, 0.75, "#fec44f"),
        (0.75, 1.01, FLOODED_HIGH),
    ]
    for lower, upper, hex_color in steps:
        symbol = QgsMarkerSymbol.createSimple(
            {"name": "circle", "color": hex_color, "size": "2.6"}
        )
        symbol.setColor(QColor(hex_color))
        label = f"{int(lower * 100)}–{int(min(upper, 1.0) * 100)}%"
        ranges.append(QgsRendererRange(lower, upper, symbol, label))
    renderer = QgsGraduatedSymbolRenderer("flooded_pct", ranges)
    layer.setRenderer(renderer)
    layer.triggerRepaint()
```

- [ ] **Step 4: Apply styling after import. Modify `import_controller.py::load_geopackage_layers`**

Find the return at the end of `load_geopackage_layers`:

```python
    project.addMapLayer(pipe_layer)
    project.addMapLayer(manhole_layer)
    return manhole_layer, pipe_layer
```

Replace with:

```python
    project.addMapLayer(pipe_layer)
    project.addMapLayer(manhole_layer)

    from drainworks_plugin.styling.symbology import style_manholes, style_pipes

    style_pipes(pipe_layer)
    style_manholes(manhole_layer)
    return manhole_layer, pipe_layer
```

- [ ] **Step 5: Manual verification in QGIS**

Re-run the import (Task 3 steps). Confirm pipes draw as white lines and manholes as green circles.

Expected: styled layers; no errors in the log.

- [ ] **Step 6: Commit**

```bash
git add drainworks_plugin/styling/ drainworks_plugin/io/import_controller.py
git commit -m "feat: drainworks-style symbology for pipes/manholes/measurements"
```

---

## Task 5: Network graph + Dijkstra shortest path

**Files:**
- Create: `drainworks_plugin/trajectory/__init__.py`
- Create: `drainworks_plugin/trajectory/network.py`
- Test: `tests/test_network.py`

Pure logic. Build an adjacency from pipes (nodes are manhole codes, edge weight = pipe length) and find the shortest path between two manholes; then chain a sequence of waypoints. Length falls back to geometry length if `length` is missing.

- [ ] **Step 1: Create `drainworks_plugin/trajectory/__init__.py`** (empty)

```python
```

- [ ] **Step 2: Write the failing test `tests/test_network.py`**

```python
import pytest

import rgs_ribx

from drainworks_plugin.trajectory.network import SewerNetwork


def _pipe(code, a, b, length):
    return rgs_ribx.Pipe(code=code, manhole1=a, manhole2=b, length=length, bob1=0, bob2=0)


def test_shortest_path_picks_lower_total_length():
    # P1-P2-P3 (10+10=20) vs P1-P3 direct (25). Shortest is via P2.
    pipes = [
        _pipe("L1", "P1", "P2", 10.0),
        _pipe("L2", "P2", "P3", 10.0),
        _pipe("L3", "P1", "P3", 25.0),
    ]
    net = SewerNetwork(pipes)
    path = net.shortest_path("P1", "P3")
    assert path.manholes == ["P1", "P2", "P3"]
    assert path.pipe_codes == ["L1", "L2"]
    assert path.total_length == pytest.approx(20.0)


def test_direct_edge_when_shortest():
    pipes = [
        _pipe("L1", "P1", "P2", 10.0),
        _pipe("L2", "P2", "P3", 10.0),
        _pipe("L3", "P1", "P3", 5.0),
    ]
    net = SewerNetwork(pipes)
    path = net.shortest_path("P1", "P3")
    assert path.pipe_codes == ["L3"]


def test_route_through_waypoints():
    pipes = [
        _pipe("L1", "P1", "P2", 10.0),
        _pipe("L2", "P2", "P3", 10.0),
        _pipe("L3", "P3", "P4", 10.0),
    ]
    net = SewerNetwork(pipes)
    route = net.route(["P1", "P3", "P4"])
    assert route.manholes == ["P1", "P2", "P3", "P4"]
    assert route.pipe_codes == ["L1", "L2", "L3"]


def test_no_path_raises():
    pipes = [_pipe("L1", "P1", "P2", 10.0), _pipe("L9", "P8", "P9", 10.0)]
    net = SewerNetwork(pipes)
    with pytest.raises(ValueError):
        net.shortest_path("P1", "P9")
```

- [ ] **Step 3: Write `drainworks_plugin/trajectory/network.py`**

```python
"""Sewer network graph + Dijkstra shortest path over manholes.

Edge weight is pipe length (meters). Pure Python; no QGIS, no networkx.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Optional


@dataclass
class Path:
    """A route through the network."""

    manholes: list = field(default_factory=list)   # ordered manhole codes
    pipe_codes: list = field(default_factory=list)  # pipe per consecutive pair
    total_length: float = 0.0


class SewerNetwork:
    """Undirected weighted graph of manholes connected by pipes."""

    def __init__(self, pipes) -> None:
        # node -> list of (neighbor, pipe_code, weight)
        self._adj = defaultdict(list)
        for pipe in pipes:
            weight = pipe.length if pipe.length is not None else 1.0
            if weight <= 0:
                weight = 1.0
            self._adj[pipe.manhole1].append((pipe.manhole2, pipe.code, weight))
            self._adj[pipe.manhole2].append((pipe.manhole1, pipe.code, weight))

    def shortest_path(self, start: str, end: str) -> Path:
        """Dijkstra shortest path from ``start`` to ``end`` manhole."""
        if start not in self._adj:
            raise ValueError(f"Unknown manhole: {start}")
        dist = {start: 0.0}
        prev = {}            # node -> (prev_node, pipe_code)
        heap = [(0.0, start)]
        visited = set()

        while heap:
            d, node = heappop(heap)
            if node in visited:
                continue
            visited.add(node)
            if node == end:
                break
            for neighbor, pipe_code, weight in self._adj[node]:
                if neighbor in visited:
                    continue
                nd = d + weight
                if nd < dist.get(neighbor, float("inf")):
                    dist[neighbor] = nd
                    prev[neighbor] = (node, pipe_code)
                    heappush(heap, (nd, neighbor))

        if end not in dist:
            raise ValueError(f"No path from {start} to {end}")

        # Reconstruct.
        manholes = [end]
        pipe_codes = []
        cur = end
        while cur != start:
            pnode, pcode = prev[cur]
            pipe_codes.append(pcode)
            manholes.append(pnode)
            cur = pnode
        manholes.reverse()
        pipe_codes.reverse()
        return Path(manholes=manholes, pipe_codes=pipe_codes, total_length=dist[end])

    def route(self, waypoints: list) -> Path:
        """Chain shortest paths through an ordered list of manhole waypoints."""
        if len(waypoints) < 2:
            raise ValueError("Need at least two waypoints")
        full = Path(manholes=[waypoints[0]], pipe_codes=[], total_length=0.0)
        for a, b in zip(waypoints, waypoints[1:]):
            leg = self.shortest_path(a, b)
            # Append leg, avoiding duplicating the shared node.
            full.manholes.extend(leg.manholes[1:])
            full.pipe_codes.extend(leg.pipe_codes)
            full.total_length += leg.total_length
        return full
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_network.py -v` (or any Python with `rgs_ribx` installed)
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/trajectory/__init__.py drainworks_plugin/trajectory/network.py tests/test_network.py
git commit -m "feat: sewer network graph with Dijkstra shortest path"
```

---

## Task 6: Profile builder (route -> ordered longitudinal profile)

**Files:**
- Create: `drainworks_plugin/sideview/__init__.py`
- Create: `drainworks_plugin/sideview/profile_builder.py`
- Test: `tests/test_profile_builder.py`

Turn a `Path` into an ordered list of `(cumulative_distance, bob, obb)` vertices plus observation markers, ready for the side-view. Each pipe contributes a start vertex (bob at the start node) and an end vertex (bob at the end node), oriented so the path is continuous. Cumulative distance accumulates pipe lengths.

- [ ] **Step 1: Create `drainworks_plugin/sideview/__init__.py`** (empty)

```python
```

- [ ] **Step 2: Write the failing test `tests/test_profile_builder.py`**

```python
import pytest

import rgs_ribx

from drainworks_plugin.sideview.profile_builder import build_profile
from drainworks_plugin.trajectory.network import Path


def _pipe(code, a, b, bob_a, bob_b, length, diameter=0.3):
    return rgs_ribx.Pipe(code=code, manhole1=a, manhole2=b,
                         bob1=bob_a, bob2=bob_b, length=length, diameter=diameter, shape="A")


def test_profile_orientation_and_cumulative_distance():
    pipes = {
        "L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-2.4, length=20.0),
        "L2": _pipe("L2", "P2", "P3", bob_a=-2.4, bob_b=-2.8, length=20.0),
    }
    path = Path(manholes=["P1", "P2", "P3"], pipe_codes=["L1", "L2"], total_length=40.0)

    profile = build_profile(path, pipes, observations_by_pipe={})

    # 4 vertices (2 per pipe), distances 0, 20, 20, 40.
    dists = [v.dist for v in profile.vertices]
    assert dists == pytest.approx([0.0, 20.0, 20.0, 40.0])
    bobs = [v.bob for v in profile.vertices]
    assert bobs == pytest.approx([-2.0, -2.4, -2.4, -2.8])
    # obb = bob + diameter
    assert profile.vertices[0].obb == pytest.approx(-1.7)


def test_profile_flips_pipe_when_traversed_backwards():
    # Path goes P2 -> P1 but the pipe is stored P1 -> P2; bobs must flip.
    pipes = {"L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-2.4, length=20.0)}
    path = Path(manholes=["P2", "P1"], pipe_codes=["L1"], total_length=20.0)

    profile = build_profile(path, pipes, observations_by_pipe={})
    bobs = [v.bob for v in profile.vertices]
    # Traversed backwards: start at P2 (bob2=-2.4), end at P1 (bob1=-2.0)
    assert bobs == pytest.approx([-2.4, -2.0])


def test_observations_placed_at_cumulative_distance():
    pipes = {
        "L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-2.4, length=20.0),
        "L2": _pipe("L2", "P2", "P3", bob_a=-2.4, bob_b=-2.8, length=20.0),
    }
    path = Path(manholes=["P1", "P2", "P3"], pipe_codes=["L1", "L2"], total_length=40.0)
    obs = rgs_ribx.Observation(object_code="L2", code="BCA", distance=5.0)

    profile = build_profile(path, pipes, observations_by_pipe={"L2": [obs]})

    assert len(profile.observations) == 1
    marker = profile.observations[0]
    # L2 starts at cumulative 20.0; observation at dist 5.0 -> 25.0
    assert marker.dist == pytest.approx(25.0)
    assert marker.code == "BCA"
```

- [ ] **Step 3: Write `drainworks_plugin/sideview/profile_builder.py`**

```python
"""Assemble a longitudinal profile from a network Path.

Output is two parallel things: the invert/crown polyline (vertices) and a list
of observation markers placed at cumulative distance along the route.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProfileVertex:
    """One vertex of the invert/crown polyline."""

    dist: float                 # cumulative distance along the route (m)
    bob: float                  # invert level (m NAP)
    obb: float                  # crown level (m NAP)
    water_level: Optional[float] = None


@dataclass
class ObservationMarker:
    """An observation positioned along the route."""

    dist: float
    code: str
    char1: Optional[str] = None
    remarks: Optional[str] = None


@dataclass
class Profile:
    """A complete side-view profile."""

    vertices: list = field(default_factory=list)
    observations: list = field(default_factory=list)
    pipe_spans: list = field(default_factory=list)  # (pipe_code, start_dist, end_dist)


def _diameter(pipe) -> float:
    return pipe.diameter if pipe.diameter is not None else 0.0


def build_profile(path, pipes: dict, observations_by_pipe: dict) -> Profile:
    """Build a Profile from a network Path.

    Parameters
    ----------
    path : drainworks_plugin.trajectory.network.Path
    pipes : dict[str, rgs_ribx.Pipe]
    observations_by_pipe : dict[str, list[rgs_ribx.Observation]]
        Observations keyed by pipe code; each has ``distance`` from the pipe's
        own start node.
    """
    profile = Profile()
    cumulative = 0.0

    for pipe_code, from_node in zip(path.pipe_codes, path.manholes):
        pipe = pipes[pipe_code]
        # Orient the pipe so that it starts at ``from_node``.
        if pipe.manhole1 == from_node:
            start_bob, end_bob = pipe.bob1, pipe.bob2
            forward = True
        else:
            start_bob, end_bob = pipe.bob2, pipe.bob1
            forward = False
        length = pipe.length if pipe.length is not None else 0.0
        diam = _diameter(pipe)
        span_start = cumulative
        span_end = cumulative + length

        profile.vertices.append(
            ProfileVertex(dist=span_start, bob=start_bob, obb=start_bob + diam)
        )
        profile.vertices.append(
            ProfileVertex(dist=span_end, bob=end_bob, obb=end_bob + diam)
        )
        profile.pipe_spans.append((pipe_code, span_start, span_end))

        for obs in observations_by_pipe.get(pipe_code, []):
            if obs.distance is None:
                continue
            # Observation distance is measured from the pipe's own start node;
            # flip it if we traverse the pipe backwards.
            along = obs.distance if forward else (length - obs.distance)
            profile.observations.append(
                ObservationMarker(
                    dist=span_start + along,
                    code=obs.code,
                    char1=obs.char1,
                    remarks=obs.remarks,
                )
            )

        cumulative = span_end

    return profile
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_profile_builder.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add drainworks_plugin/sideview/__init__.py drainworks_plugin/sideview/profile_builder.py tests/test_profile_builder.py
git commit -m "feat: build longitudinal profile from a network route"
```

---

## Task 7: pyqtgraph side-view panel

**Files:**
- Create: `drainworks_plugin/sideview/sideview_panel.py`

QGIS-coupled widget (pyqtgraph). Verified manually with a synthetic profile. The data assembly it draws is already tested in Task 6.

- [ ] **Step 1: Write `drainworks_plugin/sideview/sideview_panel.py`**

```python
"""A dockable pyqtgraph panel showing a longitudinal sewer profile.

Draws the invert (bob) line, the crown (obb) line, an optional water-level
fill (verloren berging), and observation markers. pyqtgraph gives free zoom/pan.
"""

import pyqtgraph as pg
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDockWidget, QVBoxLayout, QWidget


class SideViewPanel(QDockWidget):
    """Dock widget plotting a :class:`Profile`."""

    def __init__(self, parent=None):
        super().__init__("Drainworks — side-view", parent)
        self.setObjectName("DrainworksSideView")
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "Afstand", units="m")
        self.plot.setLabel("left", "Hoogte (NAP)", units="m")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.addLegend()
        layout.addWidget(self.plot)
        self.setWidget(container)

    def show_profile(self, profile) -> None:
        """Render a Profile (from profile_builder.build_profile)."""
        self.plot.clear()

        dists = [v.dist for v in profile.vertices]
        bobs = [v.bob for v in profile.vertices]
        obbs = [v.obb for v in profile.vertices]

        # Crown (top of pipe).
        self.plot.plot(dists, obbs, pen=pg.mkPen("#888888", width=1), name="Bovenkant buis")
        # Invert (bottom of pipe).
        self.plot.plot(dists, bobs, pen=pg.mkPen("#333333", width=2), name="BOB (bodem)")

        # Water-level fill (verloren berging) where water_level is set.
        water = [v.water_level if v.water_level is not None else v.bob for v in profile.vertices]
        if any(v.water_level is not None for v in profile.vertices):
            bob_curve = pg.PlotCurveItem(dists, bobs)
            water_curve = pg.PlotCurveItem(dists, water)
            fill = pg.FillBetweenItem(bob_curve, water_curve, brush=pg.mkBrush(44, 127, 184, 120))
            self.plot.addItem(fill)
            self.plot.plot(dists, water, pen=pg.mkPen("#2c7fb8", width=1, style=Qt.DashLine),
                           name="Waterpeil")

        # Observation markers as vertical lines with labels.
        for marker in profile.observations:
            line = pg.InfiniteLine(
                pos=marker.dist, angle=90,
                pen=pg.mkPen("#c54141", width=1, style=Qt.DotLine),
                label=marker.code, labelOpts={"position": 0.95, "color": "#c54141"},
            )
            self.plot.addItem(line)

        self.plot.autoRange()
```

- [ ] **Step 2: Manual verification in QGIS Python console**

Paste in the QGIS Python console:

```python
from drainworks_plugin.sideview.sideview_panel import SideViewPanel
from drainworks_plugin.sideview.profile_builder import Profile, ProfileVertex, ObservationMarker
from qgis.PyQt.QtCore import Qt

panel = SideViewPanel(iface.mainWindow())
iface.mainWindow().addDockWidget(Qt.BottomDockWidgetArea, panel)

p = Profile(
    vertices=[
        ProfileVertex(0, -2.0, -1.7, water_level=-1.85),
        ProfileVertex(20, -2.4, -2.1, water_level=-2.1),
        ProfileVertex(40, -2.2, -1.9, water_level=-1.95),
    ],
    observations=[ObservationMarker(12.5, "BCA", char1="A")],
)
panel.show_profile(p)
```

Expected: a dock with a crown line, a bob line, a blue water-level fill, and a dotted observation line labeled "BCA". Zoom/pan with the mouse works.

- [ ] **Step 3: Commit**

```bash
git add drainworks_plugin/sideview/sideview_panel.py
git commit -m "feat: pyqtgraph side-view panel"
```

---

## Task 8: Trajectory map tool (click manholes to pick a route)

**Files:**
- Create: `drainworks_plugin/trajectory/map_tool.py`
- Modify: `drainworks_plugin/plugin.py`

QGIS-coupled map tool. The user clicks manholes; the tool snaps to the nearest manhole feature, accumulates waypoints, computes the route on each new point, builds the profile, and updates the side-view. Verified manually.

- [ ] **Step 1: Write `drainworks_plugin/trajectory/map_tool.py`**

```python
"""Map tool: click near manholes to build a trajectory and show its side-view."""

from qgis.core import QgsPointXY, QgsProject
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt

import rgs_ribx

from drainworks_plugin.io.geopackage_store import read_manholes, read_pipes
from drainworks_plugin.sideview.profile_builder import build_profile
from drainworks_plugin.trajectory.network import SewerNetwork


class TrajectoryMapTool(QgsMapTool):
    """Pick manholes on the canvas; show the longitudinal profile of the route."""

    def __init__(self, canvas, manhole_layer, gpkg_path, side_view_panel, message_bar):
        super().__init__(canvas)
        self.canvas = canvas
        self.manhole_layer = manhole_layer
        self.gpkg_path = gpkg_path
        self.side_view = side_view_panel
        self.message_bar = message_bar
        self.waypoints = []

        pipes = read_pipes(gpkg_path)
        self._pipes_by_code = {p.code: p for p in pipes}
        self._network = SewerNetwork(pipes)
        self._observations_by_pipe = self._load_observations(gpkg_path)

    def _load_observations(self, gpkg_path) -> dict:
        """Re-parse observations from the source if available.

        Observations are not stored in the GeoPackage in this version; return
        empty mapping. (Follow-up task can add an ``observations`` layer.)
        """
        return {}

    def canvasReleaseEvent(self, event):  # noqa: N802 (QGIS-required name)
        if event.button() == Qt.RightButton:
            self.waypoints = []
            self.message_bar.pushInfo("Drainworks", "Trajectory reset.")
            return

        point = self.toMapCoordinates(event.pos())
        code = self._nearest_manhole_code(point)
        if code is None:
            return
        if self.waypoints and self.waypoints[-1] == code:
            return
        self.waypoints.append(code)

        if len(self.waypoints) >= 2:
            self._update_side_view()

    def _nearest_manhole_code(self, point: QgsPointXY):
        """Return the code of the nearest manhole feature to ``point``."""
        nearest_code = None
        nearest_dist = float("inf")
        for feat in self.manhole_layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            d = geom.distance(self._point_geometry(point))
            if d < nearest_dist:
                nearest_dist = d
                nearest_code = feat["code"]
        return nearest_code

    @staticmethod
    def _point_geometry(point: QgsPointXY):
        from qgis.core import QgsGeometry

        return QgsGeometry.fromPointXY(point)

    def _update_side_view(self):
        try:
            route = self._network.route(self.waypoints)
        except ValueError as exc:
            self.message_bar.pushWarning("Drainworks", str(exc))
            return
        profile = build_profile(route, self._pipes_by_code, self._observations_by_pipe)
        self.side_view.show_profile(profile)
        self.side_view.show()
        self.message_bar.pushInfo(
            "Drainworks",
            f"Route: {' → '.join(route.manholes)} ({route.total_length:.1f} m)",
        )
```

- [ ] **Step 2: Wire a "Pick trajectory" action into `plugin.py`**

Add imports and state. In `drainworks_plugin/plugin.py`, modify `__init__` to track layers and the side-view. Find:

```python
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.menu = "&Drainworks"
```

Replace with:

```python
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.menu = "&Drainworks"
        self.manhole_layer = None
        self.pipe_layer = None
        self.gpkg_path = None
        self.side_view = None
        self.map_tool = None
```

Add a second action in `initGui`. Find:

```python
        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
```

Replace with:

```python
        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)

        traj = QAction(icon, "Pick trajectory (side-view)", self.iface.mainWindow())
        traj.triggered.connect(self.on_pick_trajectory)
        self.iface.addToolBarIcon(traj)
        self.iface.addPluginToMenu(self.menu, traj)
        self.actions.append(traj)
```

Record the imported gpkg path + layers in `on_import`. Find the success block:

```python
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Imported {pipe_layer.featureCount()} pipes, "
            f"{manhole_layer.featureCount()} manholes.",
        )
```

Replace with:

```python
        self.manhole_layer = manhole_layer
        self.pipe_layer = pipe_layer
        self.gpkg_path = input_path if input_path.lower().endswith(".gpkg") else gpkg_path
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Imported {pipe_layer.featureCount()} pipes, "
            f"{manhole_layer.featureCount()} manholes.",
        )
```

Add the handler method (place after `on_import`):

```python
    def on_pick_trajectory(self):
        """Activate the trajectory map tool and ensure the side-view dock exists."""
        if self.manhole_layer is None or self.gpkg_path is None:
            self.iface.messageBar().pushWarning("Drainworks", "Import data first.")
            return

        from qgis.PyQt.QtCore import Qt

        from drainworks_plugin.sideview.sideview_panel import SideViewPanel
        from drainworks_plugin.trajectory.map_tool import TrajectoryMapTool

        if self.side_view is None:
            self.side_view = SideViewPanel(self.iface.mainWindow())
            self.iface.mainWindow().addDockWidget(Qt.BottomDockWidgetArea, self.side_view)

        self.map_tool = TrajectoryMapTool(
            self.iface.mapCanvas(),
            self.manhole_layer,
            self.gpkg_path,
            self.side_view,
            self.iface.messageBar(),
        )
        self.iface.mapCanvas().setMapTool(self.map_tool)
        self.iface.messageBar().pushInfo(
            "Drainworks", "Click manholes to build a route. Right-click to reset."
        )
```

- [ ] **Step 3: Manual verification in QGIS**

1. Reload the plugin; import `minimal.ribx` (only 2 manholes, 1 pipe — enough to test).
2. Click "Pick trajectory (side-view)".
3. Click near P001, then near P002. Confirm the side-view dock shows the single-pipe profile and a message reports the route + length.
4. Right-click resets the route.

> For a richer test, import a real multi-pipe RIBX and pick non-adjacent manholes; confirm the shortest path is chosen and the profile is continuous.

Expected: route computed; side-view updates; reset works.

- [ ] **Step 4: Commit**

```bash
git add drainworks_plugin/trajectory/map_tool.py drainworks_plugin/plugin.py
git commit -m "feat: trajectory map tool wired to side-view"
```

---

## Task 9: Lost-capacity runner (compute + write back + style)

**Files:**
- Create: `drainworks_plugin/lostcapacity/__init__.py`
- Create: `drainworks_plugin/lostcapacity/runner.py`
- Modify: `drainworks_plugin/plugin.py`
- Test: `tests/test_lostcapacity_runner.py`

Reads pipes/manholes from the GeoPackage, builds profiles (from the `measurements` layer if present, else just endpoints), runs `rgs_ribx.compute_lost_capacity`, writes results to the `measurements` layer, and styles it. The compute/store logic is pytest-testable; reloading the styled layer into the project is manual.

- [ ] **Step 1: Create `drainworks_plugin/lostcapacity/__init__.py`** (empty)

```python
```

- [ ] **Step 2: Write the failing test `tests/test_lostcapacity_runner.py`**

```python
import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    MeasurementRow,
    write_geopackage,
)
from drainworks_plugin.lostcapacity.runner import compute_and_store


def test_compute_and_store_writes_flooded_pct(tmp_gpkg):
    # A sagging pipe between two sinks; one interior measurement at the dip.
    manholes = [
        rgs_ribx.Manhole(code="P1", is_sink=True),
        rgs_ribx.Manhole(code="P2", is_sink=True),
    ]
    pipes = [
        rgs_ribx.Pipe(code="L1", manhole1="P1", manhole2="P2",
                      bob1=-2.0, bob2=-2.0, diameter=0.3, shape="A", length=30.0),
    ]
    measurements = [MeasurementRow(pipe_code="L1", dist=15.0, bob=-2.3, obb=-2.0)]
    write_geopackage(tmp_gpkg, manholes, pipes, measurements)

    n = compute_and_store(tmp_gpkg)
    assert n == 1

    from osgeo import ogr

    ds = ogr.Open(str(tmp_gpkg))
    feat = ds.GetLayerByName("measurements").GetNextFeature()
    assert feat.GetField("water_level") is not None
    assert feat.GetField("flooded_pct") > 0
```

- [ ] **Step 3: Write `drainworks_plugin/lostcapacity/runner.py`**

```python
"""Compute lost capacity from a GeoPackage and write results back to it."""

from collections import defaultdict

from osgeo import ogr

import rgs_ribx

from drainworks_plugin.io.geopackage_store import read_manholes, read_pipes


def _read_measurement_profiles(gpkg_path) -> dict:
    """Read interior measurement points per pipe into MeasurementPoint objects."""
    ds = ogr.Open(str(gpkg_path))
    layer = ds.GetLayerByName("measurements")
    profiles = defaultdict(list)
    if layer is None:
        return profiles
    for feat in layer:
        profiles[feat.GetField("pipe_code")].append(
            rgs_ribx.MeasurementPoint(
                dist=feat.GetField("dist"),
                bob=feat.GetField("bob"),
                obb=feat.GetField("obb"),
            )
        )
    return profiles


def compute_and_store(gpkg_path) -> int:
    """Run lost-capacity and update the ``measurements`` layer in place.

    Returns the number of measurement rows updated.
    """
    manholes = {m.code: m for m in read_manholes(gpkg_path)}
    pipes = {p.code: p for p in read_pipes(gpkg_path)}
    profiles = _read_measurement_profiles(gpkg_path)

    rgs_ribx.compute_lost_capacity(manholes, pipes, profiles)

    # Write results back. Match rows by (pipe_code, dist).
    results = {}
    for pipe_code, points in profiles.items():
        for mp in points:
            results[(pipe_code, round(mp.dist, 6))] = mp

    ds = ogr.Open(str(gpkg_path), update=1)
    layer = ds.GetLayerByName("measurements")
    updated = 0
    layer.ResetReading()
    for feat in layer:
        key = (feat.GetField("pipe_code"), round(feat.GetField("dist"), 6))
        mp = results.get(key)
        if mp is None:
            continue
        if mp.water_level is None:
            feat.SetFieldNull("water_level")
        else:
            feat.SetField("water_level", mp.water_level)
        if mp.flooded_pct is None:
            feat.SetFieldNull("flooded_pct")
        else:
            feat.SetField("flooded_pct", float(mp.flooded_pct))
        layer.SetFeature(feat)
        updated += 1
    ds = None
    return updated
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$QGIS_PY" -m pytest tests/test_lostcapacity_runner.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Add a "Compute lost capacity" action to `plugin.py`**

In `initGui`, after the trajectory action block, add:

```python
        loss = QAction(icon, "Compute lost capacity", self.iface.mainWindow())
        loss.triggered.connect(self.on_compute_loss)
        self.iface.addToolBarIcon(loss)
        self.iface.addPluginToMenu(self.menu, loss)
        self.actions.append(loss)
```

Add the handler after `on_pick_trajectory`:

```python
    def on_compute_loss(self):
        """Compute lost capacity and load the styled measurements layer."""
        if self.gpkg_path is None:
            self.iface.messageBar().pushWarning("Drainworks", "Import data first.")
            return
        from qgis.core import QgsProject, QgsVectorLayer

        from drainworks_plugin.lostcapacity.runner import compute_and_store
        from drainworks_plugin.styling.symbology import style_measurements_by_flooded

        try:
            n = compute_and_store(self.gpkg_path)
        except Exception as exc:
            self.iface.messageBar().pushCritical("Drainworks", f"Computation failed: {exc}")
            return

        layer = QgsVectorLayer(f"{self.gpkg_path}|layername=measurements", "Verloren berging", "ogr")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            style_measurements_by_flooded(layer)
        self.iface.messageBar().pushSuccess("Drainworks", f"Lost capacity computed for {n} points.")
```

- [ ] **Step 6: Manual verification in QGIS**

This needs a GeoPackage with interior measurement rows. Create one in the QGIS Python console:

```python
import rgs_ribx
from drainworks_plugin.io.geopackage_store import write_geopackage, MeasurementRow
path = "/tmp/loss_demo.gpkg"
manholes = [rgs_ribx.Manhole(code="P1", geometry_wkt="POINT (100000 400000)", is_sink=True),
            rgs_ribx.Manhole(code="P2", geometry_wkt="POINT (100030 400000)", is_sink=True)]
pipes = [rgs_ribx.Pipe(code="L1", manhole1="P1", manhole2="P2", bob1=-2.0, bob2=-2.0,
                       diameter=0.3, shape="A", length=30.0,
                       geometry_wkt="LINESTRING (100000 400000, 100030 400000)")]
meas = [MeasurementRow(pipe_code="L1", dist=15.0, bob=-2.3, obb=-2.0)]
write_geopackage(path, manholes, pipes, meas)
```

Then import `/tmp/loss_demo.gpkg` via the dialog, click "Compute lost capacity", and confirm a "Verloren berging" point layer appears colored by flooded percentage and a success message shows.

Expected: measurement point at the dip is colored (>0% flooded).

- [ ] **Step 7: Commit**

```bash
git add drainworks_plugin/lostcapacity/ drainworks_plugin/plugin.py tests/test_lostcapacity_runner.py
git commit -m "feat: lost-capacity runner with map action and styling"
```

---

## Task 10: Finish the branch

- [ ] **Step 1: Run the full headless test suite**

Run:
```bash
cd ~/Documents/GitHub/qgis-drainworks-plugin
"$QGIS_PY" -m pytest -v
```
Expected: all tests pass (dependencies, geopackage_store, network, profile_builder, lostcapacity_runner).

- [ ] **Step 2: Full manual smoke test in QGIS**

Verify the end-to-end flow on a real multi-pipe RIBX:
1. Import RIBX → styled pipes/manholes appear.
2. Pick a trajectory across several manholes → continuous side-view with zoom/pan.
3. (If interior measurements exist) Compute lost capacity → colored measurement layer + water-level fill in the side-view.

- [ ] **Step 3: Use the finishing-a-development-branch skill**

REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch`. Do NOT push without explicit instruction (user's global rule).

---

## Open items to confirm with the user during execution

1. **Observation layer.** This plan does not yet persist observations to the GeoPackage, so the side-view shows no observation markers from imported data (the marker code path is tested with synthetic data and ready). Adding an `observations` layer to `geopackage_store` + loading it in `map_tool._load_observations` is a natural follow-up task — confirm desired observation fields/labels (the full set is in `rgs_ribx.Observation`).
2. **Measurement (longitudinal profile) source.** The lost-capacity runner reads interior points from the `measurements` layer, which is empty after a plain RIBX import. Populating it requires the RIBX→profile mapping flagged in the rgs-ribx plan (inclination/helling observations → `MeasurementPoint`s). Confirm the inclination observation codes against a real RIBX before building that extractor.
3. **Sink detection.** `is_sink` is currently always 0 after import (RIBX has no explicit sink flag). The lost-capacity algorithm needs at least one sink. Decide how sinks are chosen — e.g. lowest-BOB manholes, outfalls by node type, or a manual "mark as sink" tool — and add a task for it.
4. **Status symbology.** drainworks colors by inspection/cleaning status; we don't import status. If status views are wanted, decide how status is derived from observations and add a renderer task using `STATUS_COLORS` (already ported in `styling/colors.py`).
