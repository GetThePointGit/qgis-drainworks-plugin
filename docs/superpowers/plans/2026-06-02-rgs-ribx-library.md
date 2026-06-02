# rgs-ribx Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone, pure-Python library (`rgs-ribx`) that reads RIBX sewer inspection files into a typed data model and computes "verloren berging" (lost storage capacity) — with no dependency on Django, QGIS, or networkx.

**Architecture:** Three layers. (1) `parsing` extracts RIBX XML into pandas DataFrames (ported verbatim from drainworks' `import_new`). (2) `model` maps those DataFrames into immutable dataclasses (`Manhole`, `Pipe`, `Inspection`, `Observation`) carrying WKT geometry in EPSG:28992. (3) `lost_capacity` ports the lizard-progress flood-fill algorithm to a tiny pure-Python graph and computes a flooded percentage per measurement point. The QGIS plugin (separate plan) consumes this library.

**Tech Stack:** Python 3.9+ (QGIS-compatible), `lxml` (bundled in QGIS), `pandas` (bundled in QGIS), `pytest` for tests. NO networkx, NO shapely, NO geopandas, NO Django.

**Source material (read-only references — paths relative to `~/Documents/GitHub/`):**
- RIBX parsing: `drainworks/backend/drainworks/import_new/ribx_to_pandas.py`, `error_codes.py`, `error_warning_df.py`, `object_headers/*.csv`
- Field mappings: `drainworks/backend/drainworks/import_new/save_to_sewerage.py` (constants `REF_FIELDS`, `DATE_FIELDS`, `MATERIAL_FIELDS`, etc.)
- Verloren berging: `lizard-progress/src/sewer/lost_capacity.py` and `lizard-progress/src/sewer/models.py` lines 515-598 (`PipeMeasurement.set_water_level`, `compute_flooded_pct`, `disc_segment`)

**Target repo:** `~/Documents/GitHub/rgs-ribx` (currently empty: `.git`, `.gitignore`, `LICENSE` only; remote `GetThePoint/rgs-ribx`).

> **IMPORTANT — git workflow (user's global rule):** Never commit on `main`. Before Task 1, in the `rgs-ribx` repo run `git switch -c feature/ribx-library`. Never `git push` unless explicitly told.

---

## File Structure

```
rgs-ribx/
├── pyproject.toml                       # packaging + pytest + ruff config
├── README.md
├── src/rgs_ribx/
│   ├── __init__.py                      # public API re-exports
│   ├── errors.py                        # error codes + ErrorCollector
│   ├── parsing/
│   │   ├── __init__.py
│   │   ├── ribx_to_pandas.py            # ported from drainworks (adjusted imports)
│   │   ├── headers.py                   # load object-header CSVs
│   │   └── object_headers/*.csv         # copied data files
│   ├── model/
│   │   ├── __init__.py
│   │   ├── geometry.py                  # GML pos/posList string -> WKT
│   │   ├── entities.py                  # Manhole, Pipe, Inspection, Observation
│   │   ├── field_maps.py                # RIBX tag -> attribute constants
│   │   └── build.py                     # DataFrames/records -> entities
│   └── lost_capacity/
│       ├── __init__.py
│       ├── graph.py                     # tiny pure-Python Graph (replaces networkx)
│       ├── profile.py                   # MeasurementPoint + flooded_pct math
│       └── compute.py                   # compute_lost_capacity orchestrator
└── tests/
    ├── conftest.py
    ├── fixtures/minimal.ribx
    ├── test_errors.py
    ├── test_ribx_to_pandas.py
    ├── test_headers.py
    ├── test_geometry.py
    ├── test_entities.py
    ├── test_build.py
    ├── test_profile.py
    ├── test_graph.py
    └── test_compute.py
```

**Responsibilities:**
- `parsing/` — pure XML → tabular. No domain knowledge beyond RIBX structure.
- `model/` — turns tabular data into typed domain objects; the only place that knows RIBX tag names map to which concept.
- `lost_capacity/` — pure math + graph. Input is plain entities, output is annotated measurement points.

---

## Task 0: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/rgs_ribx/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Switch to a feature branch**

```bash
cd ~/Documents/GitHub/rgs-ribx
git switch -c feature/ribx-library
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "rgs-ribx"
version = "0.1.0"
description = "Read RIBX sewer inspection data and compute lost storage capacity."
readme = "README.md"
requires-python = ">=3.9"
license = { text = "MIT" }
authors = [{ name = "Bastiaan Roos" }]
dependencies = [
    "lxml>=4.9",
    "pandas>=1.5",
]

[project.optional-dependencies]
dev = ["pytest>=7", "ruff>=0.4"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
rgs_ribx = ["parsing/object_headers/*.csv"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.ruff]
line-length = 100
target-version = "py39"
```

- [ ] **Step 3: Create empty package init**

`src/rgs_ribx/__init__.py`:

```python
"""rgs-ribx: read RIBX sewer data and compute lost storage capacity."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Create `tests/conftest.py`**

```python
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
```

- [ ] **Step 5: Install in editable mode and verify pytest collects nothing yet**

Run:
```bash
cd ~/Documents/GitHub/rgs-ribx
python -m pip install -e ".[dev]"
python -m pytest
```
Expected: `no tests ran` (exit code 5) — confirms environment works.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/rgs_ribx/__init__.py tests/conftest.py
git commit -m "chore: scaffold rgs-ribx package"
```

---

## Task 1: Error collection

**Files:**
- Create: `src/rgs_ribx/errors.py`
- Test: `tests/test_errors.py`

The parser emits errors/warnings. drainworks returns these as a pandas DataFrame; we keep the same shape (columns `level, line_nr, value, code, message`) so the ported parser drops in unchanged, but wrap creation in our own helper.

- [ ] **Step 1: Write the failing test**

`tests/test_errors.py`:

```python
import pandas as pd

from rgs_ribx.errors import (
    XML_FILE_NOT_FOUND,
    XML_SYNTAX_ERROR,
    create_error_warning_df,
)


def test_error_codes_are_distinct_ints():
    assert isinstance(XML_FILE_NOT_FOUND, int)
    assert XML_FILE_NOT_FOUND != XML_SYNTAX_ERROR


def test_create_error_warning_df_has_expected_columns():
    df = create_error_warning_df(
        [{"level": "error", "line_nr": 3, "value": "x", "code": XML_SYNTAX_ERROR, "message": "boom"}]
    )
    assert list(df.columns) == ["level", "line_nr", "value", "code", "message"]
    assert len(df) == 1
    assert df.iloc[0]["code"] == XML_SYNTAX_ERROR


def test_create_error_warning_df_empty():
    df = create_error_warning_df([])
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["level", "line_nr", "value", "code", "message"]
    assert len(df) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rgs_ribx.errors'`

- [ ] **Step 3: Write `src/rgs_ribx/errors.py`**

```python
"""Error/warning codes and the tabular collector used by the parser.

Codes mirror drainworks' import_new/error_codes.py so the ported parser
works unchanged. Only the XML-parsing codes are needed in this library.
"""

import pandas as pd

# --- XML parsing (ribx_to_pandas) ---
XML_FILE_NOT_FOUND = 1
XML_SYNTAX_ERROR = 2
XML_WRONG_ROOT = 3
XML_MISSING_ZA = 4
XML_UNKNOWN_OBJECT_TYPE = 5
XML_NO_OBJECTS = 6

ERROR_WARNING_COLUMNS = ["level", "line_nr", "value", "code", "message"]


def create_error_warning_df(errors: list[dict]) -> pd.DataFrame:
    """Build a DataFrame of errors/warnings with a fixed column order.

    Parameters
    ----------
    errors : list of dict
        Each dict has keys ``level, line_nr, value, code, message``.

    Returns
    -------
    pandas.DataFrame
        One row per error, columns in :data:`ERROR_WARNING_COLUMNS` order.
    """
    if not errors:
        return pd.DataFrame(columns=ERROR_WARNING_COLUMNS)
    return pd.DataFrame(errors, columns=ERROR_WARNING_COLUMNS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_errors.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rgs_ribx/errors.py tests/test_errors.py
git commit -m "feat: error/warning codes and collector"
```

---

## Task 2: Port the RIBX parser (ribx_to_pandas)

**Files:**
- Create: `src/rgs_ribx/parsing/__init__.py`
- Create: `src/rgs_ribx/parsing/ribx_to_pandas.py`
- Create: `tests/fixtures/minimal.ribx`
- Test: `tests/test_ribx_to_pandas.py`

The source file at `drainworks/backend/drainworks/import_new/ribx_to_pandas.py` is self-contained except for two imports (`error_codes`, `error_warning_df`). We copy it and repoint those imports to `rgs_ribx.errors`.

- [ ] **Step 1: Create `src/rgs_ribx/parsing/__init__.py`**

```python
from rgs_ribx.parsing.ribx_to_pandas import (
    OBJECT_TYPE_MAP,
    OBSERVATION_COLUMNS,
    ribx_to_pandas,
)

__all__ = ["ribx_to_pandas", "OBJECT_TYPE_MAP", "OBSERVATION_COLUMNS"]
```

- [ ] **Step 2: Create the parser by copying the source and adjusting imports**

Copy the file verbatim, then change only the import block. Run:

```bash
cp ~/Documents/GitHub/drainworks/backend/drainworks/import_new/ribx_to_pandas.py \
   ~/Documents/GitHub/rgs-ribx/src/rgs_ribx/parsing/ribx_to_pandas.py
```

Then replace the import block at the top of `src/rgs_ribx/parsing/ribx_to_pandas.py`. Find:

```python
from drainworks.import_new.error_codes import (
    XML_FILE_NOT_FOUND,
    XML_MISSING_ZA,
    XML_NO_OBJECTS,
    XML_SYNTAX_ERROR,
    XML_UNKNOWN_OBJECT_TYPE,
    XML_WRONG_ROOT,
)
from drainworks.import_new.error_warning_df import create_error_warning_df
```

Replace with:

```python
from rgs_ribx.errors import (
    XML_FILE_NOT_FOUND,
    XML_MISSING_ZA,
    XML_NO_OBJECTS,
    XML_SYNTAX_ERROR,
    XML_UNKNOWN_OBJECT_TYPE,
    XML_WRONG_ROOT,
    create_error_warning_df,
)
```

Leave the rest of the file (the `OBJECT_TYPE_MAP`, `OBSERVATION_COLUMNS`, `_extract_element_value`, `_parse_object`, `ribx_to_pandas` definitions) exactly as-is.

- [ ] **Step 3: Create the test fixture `tests/fixtures/minimal.ribx`**

A minimal but valid RIBX: one pipe (ZB_A) between two manholes with geometry, BOBs, and two observations; one manhole (ZB_C). Coordinates in EPSG:28992 (RD).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<DATA>
  <ZA>
    <A>NL</A>
    <B>1.5.1</B>
  </ZA>
  <ZB_A>
    <AAA>L001</AAA>
    <AAD>P001</AAD>
    <AAE><gml:Point xmlns:gml="http://www.opengis.net/gml"><gml:pos>100000.000 400000.000</gml:pos></gml:Point></AAE>
    <AAF>P002</AAF>
    <AAG><gml:Point xmlns:gml="http://www.opengis.net/gml"><gml:pos>100030.000 400000.000</gml:pos></gml:Point></AAG>
    <ABF>2024-06-15</ABF>
    <ACA>A</ACA>
    <ACB>0.300</ACB>
    <ACD>PVC</ACD>
    <ACR>-2.500</ACR>
    <ACS>-2.600</ACS>
    <AXY><gml:LineString xmlns:gml="http://www.opengis.net/gml"><gml:posList>100000.000 400000.000 100030.000 400000.000</gml:posList></gml:LineString></AXY>
    <ZC>
      <A>BAF</A>
      <I>0.0</I>
    </ZC>
    <ZC>
      <A>BCA</A>
      <B>A</B>
      <I>12.5</I>
    </ZC>
  </ZB_A>
  <ZB_C>
    <CAA>P001</CAA>
    <CAB><gml:Point xmlns:gml="http://www.opengis.net/gml"><gml:pos>100000.000 400000.000</gml:pos></gml:Point></CAB>
    <CBF>2024-06-15</CBF>
    <CAS>0.250</CAS>
    <CAR>D-01</CAR>
  </ZB_C>
</DATA>
```

> Note on field meanings used later: `ACA`=shape, `ACB`=diameter (m), `ACD`=material, `ACR`=bob start, `ACS`=bob end, `CAS`=cover/ground level. These match drainworks' `save_to_sewerage` mappings and the object-header CSVs.

- [ ] **Step 4: Write the failing test `tests/test_ribx_to_pandas.py`**

```python
from rgs_ribx.parsing import ribx_to_pandas


def test_parses_pipe_and_manhole(fixtures_dir):
    objects, observations, errors = ribx_to_pandas(fixtures_dir / "minimal.ribx")

    assert set(objects.keys()) == {"A", "C"}
    assert objects["A"].iloc[0]["AAA"] == "L001"
    assert objects["A"].iloc[0]["ACB"] == "0.300"
    assert objects["C"].iloc[0]["CAA"] == "P001"
    # No error rows for a valid file
    assert (errors["level"] == "error").sum() == 0


def test_geometry_extracted_as_text(fixtures_dir):
    objects, _observations, _errors = ribx_to_pandas(fixtures_dir / "minimal.ribx")
    # gml:Point pos -> raw "x y" string
    assert objects["A"].iloc[0]["AAE"] == "100000.000 400000.000"
    # gml:LineString posList -> raw coordinate string
    assert objects["A"].iloc[0]["AXY"] == "100000.000 400000.000 100030.000 400000.000"


def test_observations_linked_to_object(fixtures_dir):
    _objects, observations, _errors = ribx_to_pandas(fixtures_dir / "minimal.ribx")
    obs_a = observations["A"]
    assert len(obs_a) == 2
    assert set(obs_a["_object_code"]) == {"L001"}
    assert sorted(obs_a["A"]) == ["BAF", "BCA"]


def test_missing_file_returns_error():
    objects, observations, errors = ribx_to_pandas("/no/such/file.ribx")
    assert objects == {}
    assert (errors["level"] == "error").sum() == 1
```

- [ ] **Step 5: Run test to verify it fails, then passes**

Run: `python -m pytest tests/test_ribx_to_pandas.py -v`
Expected: PASS (4 passed). If it fails on import, re-check the import block edit in Step 2.

- [ ] **Step 6: Commit**

```bash
git add src/rgs_ribx/parsing/ tests/fixtures/minimal.ribx tests/test_ribx_to_pandas.py
git commit -m "feat: port ribx_to_pandas parser with fixture"
```

---

## Task 3: Object-header definitions

**Files:**
- Copy: `src/rgs_ribx/parsing/object_headers/*.csv` (10 CSVs from drainworks)
- Create: `src/rgs_ribx/parsing/headers.py`
- Test: `tests/test_headers.py`

The header CSVs define, per object type, every field code, whether it is required (`heen`/`terug` columns: `A`=verplicht, `O`=optioneel), its `waarde_type`, and min/max. The library exposes them so the plugin can show field labels and the model builder can validate.

- [ ] **Step 1: Copy the CSV data files**

```bash
mkdir -p ~/Documents/GitHub/rgs-ribx/src/rgs_ribx/parsing/object_headers
cp ~/Documents/GitHub/drainworks/backend/drainworks/import_new/object_headers/*.csv \
   ~/Documents/GitHub/rgs-ribx/src/rgs_ribx/parsing/object_headers/
ls ~/Documents/GitHub/rgs-ribx/src/rgs_ribx/parsing/object_headers/
```
Expected: 10 `*_*.csv` files plus `codelijsten_6.13.csv`.

- [ ] **Step 2: Write the failing test `tests/test_headers.py`**

```python
from rgs_ribx.parsing.headers import load_header, header_label


def test_load_header_for_pipe_inspection():
    header = load_header("A")
    assert "AAA" in header
    assert header["AAA"]["naam"] == "Strengreferentie"


def test_header_label_lookup():
    assert header_label("A", "ACB") is not None  # diameter field exists
    assert header_label("C", "CAA") == "Knooppuntreferentie"


def test_unknown_object_type_raises():
    import pytest

    with pytest.raises(KeyError):
        load_header("ZZZ")
```

- [ ] **Step 3: Write `src/rgs_ribx/parsing/headers.py`**

```python
"""Load the per-object-type RIBX field definitions from bundled CSVs."""

import csv
from functools import lru_cache
from importlib import resources

# Maps the one-letter object prefix to its header CSV filename.
_HEADER_FILES = {
    "A": "A_inspectie_leiding.csv",
    "C": "C_inspectie_put.csv",
    "E": "E_inspectie_reiniging_kolk.csv",
    "G": "G_reiniging_leiding.csv",
    "J": "J_reiniging_put.csv",
    "L": "L_stortbon_reiniging.csv",
    "M": "M_calamiteit_reiniging.csv",
    "N": "N_stagnatie_reiniging.csv",
    "Q": "Q_reiniging_drainageleiding.csv",
    "S": "S_reiniging_drainageput.csv",
}


@lru_cache(maxsize=None)
def load_header(object_prefix: str) -> dict:
    """Return the field definitions for an object type.

    Parameters
    ----------
    object_prefix : str
        One-letter object type, e.g. ``"A"`` (pipe inspection).

    Returns
    -------
    dict
        Maps field code (e.g. ``"AAA"``) to a dict of column values
        (``naam``, ``waarde_type``, ``heen``, ``terug``, ``min_waarde``,
        ``max_waarde``, ...).

    Raises
    ------
    KeyError
        If ``object_prefix`` has no header file.
    """
    filename = _HEADER_FILES[object_prefix]
    package = "rgs_ribx.parsing.object_headers"
    text = resources.files(package).joinpath(filename).read_text(encoding="utf-8")
    reader = csv.DictReader(text.splitlines())
    return {row["code"]: row for row in reader if row.get("code")}


def header_label(object_prefix: str, field_code: str) -> str | None:
    """Return the human label (``naam``) for a field, or None if unknown."""
    header = load_header(object_prefix)
    row = header.get(field_code)
    return row["naam"] if row else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_headers.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rgs_ribx/parsing/object_headers/ src/rgs_ribx/parsing/headers.py tests/test_headers.py
git commit -m "feat: bundle and load RIBX object-header definitions"
```

---

## Task 4: Geometry helpers (GML string -> WKT)

**Files:**
- Create: `src/rgs_ribx/model/__init__.py`
- Create: `src/rgs_ribx/model/geometry.py`
- Test: `tests/test_geometry.py`

`ribx_to_pandas` returns raw GML coordinate strings (`"x y"` for points, `"x1 y1 x2 y2 ..."` for linestrings). We convert these to WKT so downstream (QGIS / OGR) can ingest them without shapely.

- [ ] **Step 1: Create `src/rgs_ribx/model/__init__.py`** (empty for now)

```python
```

- [ ] **Step 2: Write the failing test `tests/test_geometry.py`**

```python
import pytest

from rgs_ribx.model.geometry import gml_pos_to_wkt_point, gml_poslist_to_wkt_linestring


def test_point_two_coords():
    assert gml_pos_to_wkt_point("100000.000 400000.000") == "POINT (100000 400000)"


def test_point_with_z_drops_z():
    # 3D coordinate: keep X Y only (QGIS pipe/manhole layers are 2D here)
    assert gml_pos_to_wkt_point("100000 400000 -2.5") == "POINT (100000 400000)"


def test_linestring():
    wkt = gml_poslist_to_wkt_linestring("100000 400000 100030 400000")
    assert wkt == "LINESTRING (100000 400000, 100030 400000)"


def test_none_input_returns_none():
    assert gml_pos_to_wkt_point(None) is None
    assert gml_poslist_to_wkt_linestring("") is None


def test_odd_coordinate_count_raises():
    with pytest.raises(ValueError):
        gml_poslist_to_wkt_linestring("100000 400000 100030")
```

- [ ] **Step 3: Write `src/rgs_ribx/model/geometry.py`**

```python
"""Convert RIBX/GML coordinate strings to WKT (X Y only, EPSG:28992).

RIBX geometry arrives as plain coordinate strings already extracted by the
parser: ``"x y[ z]"`` for points and ``"x1 y1[ z1] x2 y2[ z2] ..."`` for
linestrings. We emit 2D WKT and drop any Z value (the longitudinal profile
uses BOB fields, not geometry Z).
"""


def _fmt(value: float) -> str:
    """Format a coordinate without trailing zeros (100000.000 -> '100000')."""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def gml_pos_to_wkt_point(pos: str | None) -> str | None:
    """Convert a GML ``pos`` string to a WKT POINT, or None if empty."""
    if not pos:
        return None
    parts = [float(p) for p in pos.split()]
    if len(parts) < 2:
        raise ValueError(f"Point needs at least 2 coordinates, got: {pos!r}")
    x, y = parts[0], parts[1]
    return f"POINT ({_fmt(x)} {_fmt(y)})"


def gml_poslist_to_wkt_linestring(poslist: str | None) -> str | None:
    """Convert a GML ``posList`` string to a WKT LINESTRING, or None if empty."""
    if not poslist:
        return None
    coords = [float(p) for p in poslist.split()]
    # We accept 2D (x y) pairs. If a Z is present per vertex the count is a
    # multiple of 3; detect and strip. Otherwise it must be a multiple of 2.
    if len(coords) % 2 == 0 and len(coords) % 3 != 0:
        stride = 2
    elif len(coords) % 3 == 0 and len(coords) % 2 != 0:
        stride = 3
    elif len(coords) % 2 == 0:
        stride = 2  # ambiguous (e.g. 6 values) -> assume 2D pairs
    else:
        raise ValueError(f"Coordinate count not divisible into vertices: {poslist!r}")

    vertices = []
    for i in range(0, len(coords), stride):
        x, y = coords[i], coords[i + 1]
        vertices.append(f"{_fmt(x)} {_fmt(y)}")
    return "LINESTRING (" + ", ".join(vertices) + ")"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_geometry.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rgs_ribx/model/__init__.py src/rgs_ribx/model/geometry.py tests/test_geometry.py
git commit -m "feat: GML coordinate string to WKT helpers"
```

---

## Task 5: Domain entities

**Files:**
- Create: `src/rgs_ribx/model/entities.py`
- Test: `tests/test_entities.py`

Immutable-ish dataclasses for the domain. Field names follow the lizard/drainworks model where they overlap (`bob1`, `bob2`, `shape`, `diameter`, `is_sink`).

- [ ] **Step 1: Write the failing test `tests/test_entities.py`**

```python
from rgs_ribx.model.entities import Manhole, Observation, Pipe, Inspection


def test_manhole_defaults():
    m = Manhole(code="P001", geometry_wkt="POINT (1 2)")
    assert m.code == "P001"
    assert m.is_sink is False
    assert m.ground_level is None


def test_pipe_is_rectangular():
    circ = Pipe(code="L001", manhole1="P001", manhole2="P002", shape="A")
    rect = Pipe(code="L002", manhole1="P001", manhole2="P002", shape="B")
    assert circ.is_rectangular is False
    assert rect.is_rectangular is True


def test_inspection_holds_observations():
    obs = Observation(object_code="L001", code="BCA", distance=12.5)
    insp = Inspection(object_code="L001", object_type="A", observations=[obs])
    assert insp.observations[0].code == "BCA"
    assert insp.observations[0].distance == 12.5
```

- [ ] **Step 2: Write `src/rgs_ribx/model/entities.py`**

```python
"""Typed domain model for sewer inspection data.

All geometry is WKT in EPSG:28992 (RD). Field names follow the
lizard-progress / drainworks models where they overlap so the lost-capacity
algorithm can be ported with minimal change.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

SHAPE_CIRCLE = "A"
SHAPE_RECTANGULAR = "B"
SHAPE_OTHER = "Z"


@dataclass
class Manhole:
    """A sewer manhole (put)."""

    code: str
    geometry_wkt: Optional[str] = None
    node_type: Optional[str] = None       # CAR / JAR (Soort knooppunt)
    ground_level: Optional[float] = None  # CAS putdekselhoogte (m NAP)
    is_sink: bool = False
    source_line: Optional[int] = None


@dataclass
class Pipe:
    """A pipe (leiding/streng) connecting two manholes."""

    code: str
    manhole1: str
    manhole2: str
    geometry_wkt: Optional[str] = None
    shape: str = SHAPE_CIRCLE            # ACA: A circular, B rectangular, Z other
    diameter: Optional[float] = None     # ACB height/diameter (m)
    width: Optional[float] = None        # width for rectangular (m)
    bob1: Optional[float] = None         # ACR start invert level (m NAP)
    bob2: Optional[float] = None         # ACS end invert level (m NAP)
    length: Optional[float] = None       # geometry length (m)
    material: Optional[str] = None       # ACD
    sewerage_type: Optional[str] = None  # ACJ
    inspection_date: Optional[date] = None
    source_line: Optional[int] = None

    @property
    def is_rectangular(self) -> bool:
        return self.shape == SHAPE_RECTANGULAR


@dataclass
class Observation:
    """A single observation (waarneming, ZC row) within an inspection."""

    object_code: str
    code: str                            # field A (e.g. BCA)
    char1: Optional[str] = None          # B
    char2: Optional[str] = None          # C
    char3: Optional[str] = None          # O
    quant1: Optional[str] = None         # D
    quant2: Optional[str] = None         # E
    remarks: Optional[str] = None        # F
    clock1: Optional[str] = None         # G
    clock2: Optional[str] = None         # H
    distance: Optional[float] = None     # I (length-direction distance, m)
    traject_location: Optional[str] = None  # J
    photo_ref: Optional[str] = None      # M
    video_ref: Optional[str] = None      # N


@dataclass
class Inspection:
    """An inspection of one object (pipe or manhole) with its observations."""

    object_code: str
    object_type: str                     # 'A' pipe, 'C' manhole
    date: Optional[date] = None
    observations: list = field(default_factory=list)
```

- [ ] **Step 3: Run test to verify it passes**

Run: `python -m pytest tests/test_entities.py -v`
Expected: PASS (3 passed)

- [ ] **Step 4: Commit**

```bash
git add src/rgs_ribx/model/entities.py tests/test_entities.py
git commit -m "feat: domain entities (Manhole, Pipe, Observation, Inspection)"
```

---

## Task 6: Field maps + build entities from DataFrames

**Files:**
- Create: `src/rgs_ribx/model/field_maps.py`
- Create: `src/rgs_ribx/model/build.py`
- Test: `tests/test_build.py`

This turns the parser output (DataFrames) into entities. Field constants are taken from drainworks' `save_to_sewerage.py`.

- [ ] **Step 1: Write `src/rgs_ribx/model/field_maps.py`**

```python
"""RIBX tag -> concept constants, taken from drainworks save_to_sewerage.py.

Only the subset needed to build the geometry/topology model is included.
"""

# Object reference (code) fields.
REF_FIELDS = {"A": "AAA", "C": "CAA", "G": "GAA", "J": "JAA", "Q": "QAA", "S": "SAA", "E": "EAA"}

# Date fields (YYYY-MM-DD).
DATE_FIELDS = {"A": "ABF", "C": "CBF", "G": "GBF", "J": "JBF", "Q": "QBF", "S": "SBF", "E": "EBF"}

# Pipe node references.
NODE1_FIELDS = {"A": "AAD", "G": "GAD", "Q": "QAD"}
NODE2_FIELDS = {"A": "AAF", "G": "GAF", "Q": "QAF"}

# Geometry fields.
PIPE_GEOM_FIELDS = {"A": "AXY", "G": "GXY", "Q": "QXY"}
NODE1_GEOM_FIELDS = {"A": "AAE", "G": "GAE", "Q": "QAE"}
NODE2_GEOM_FIELDS = {"A": "AAG", "G": "GAG", "Q": "QAG"}
MANHOLE_GEOM_FIELDS = {"C": "CAB", "J": "JAB", "S": "SAB", "E": "EAB"}

# Pipe attributes (inspection pipe ZB_A).
PIPE_SHAPE_FIELD = "ACA"
PIPE_DIAMETER_FIELD = "ACB"
PIPE_WIDTH_FIELD = "ACC"
PIPE_MATERIAL_FIELD = "ACD"
PIPE_SEWERAGE_TYPE_FIELD = "ACJ"
PIPE_BOB1_FIELD = "ACR"
PIPE_BOB2_FIELD = "ACS"

# Manhole attributes (inspection manhole ZB_C).
MANHOLE_NODE_TYPE_FIELD = "CAR"
MANHOLE_GROUND_LEVEL_FIELD = "CAS"

# Observation columns (ZC) -> Observation attribute.
OBSERVATION_FIELD_MAP = {
    "A": "code",
    "B": "char1",
    "C": "char2",
    "O": "char3",
    "D": "quant1",
    "E": "quant2",
    "F": "remarks",
    "G": "clock1",
    "H": "clock2",
    "I": "distance",
    "J": "traject_location",
    "M": "photo_ref",
    "N": "video_ref",
}
```

- [ ] **Step 2: Write the failing test `tests/test_build.py`**

```python
from datetime import date

from rgs_ribx.model.build import build_from_ribx


def test_build_pipe_from_fixture(fixtures_dir):
    result = build_from_ribx(fixtures_dir / "minimal.ribx")
    pipes = {p.code: p for p in result.pipes}
    assert "L001" in pipes
    pipe = pipes["L001"]
    assert pipe.manhole1 == "P001"
    assert pipe.manhole2 == "P002"
    assert pipe.shape == "A"
    assert pipe.diameter == 0.300
    assert pipe.bob1 == -2.500
    assert pipe.bob2 == -2.600
    assert pipe.material == "PVC"
    assert pipe.geometry_wkt == "LINESTRING (100000 400000, 100030 400000)"
    assert pipe.inspection_date == date(2024, 6, 15)


def test_build_manhole_from_fixture(fixtures_dir):
    result = build_from_ribx(fixtures_dir / "minimal.ribx")
    manholes = {m.code: m for m in result.manholes}
    assert "P001" in manholes
    assert manholes["P001"].geometry_wkt == "POINT (100000 400000)"
    assert manholes["P001"].ground_level == 0.250
    assert manholes["P001"].node_type == "D-01"


def test_build_observations_from_fixture(fixtures_dir):
    result = build_from_ribx(fixtures_dir / "minimal.ribx")
    insp = {i.object_code: i for i in result.inspections}
    assert "L001" in insp
    codes = sorted(o.code for o in insp["L001"].observations)
    assert codes == ["BAF", "BCA"]
    bca = next(o for o in insp["L001"].observations if o.code == "BCA")
    assert bca.distance == 12.5
    assert bca.char1 == "A"
```

- [ ] **Step 3: Write `src/rgs_ribx/model/build.py`**

```python
"""Build domain entities from parsed RIBX DataFrames.

Public entry point: :func:`build_from_ribx`. The intermediate
:func:`build_from_objects` works on the dicts/DataFrames returned by
``ribx_to_pandas`` so the plugin can reuse it for GeoPackage-sourced records.
"""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from rgs_ribx.model import field_maps as fm
from rgs_ribx.model.entities import Inspection, Manhole, Observation, Pipe
from rgs_ribx.model.geometry import gml_pos_to_wkt_point, gml_poslist_to_wkt_linestring
from rgs_ribx.parsing import ribx_to_pandas


@dataclass
class BuildResult:
    """Container for entities built from one RIBX file."""

    manholes: list
    pipes: list
    inspections: list
    errors: object  # pandas DataFrame from the parser


def _to_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_date(value) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _get(row, key):
    """Safe column access on a pandas row that may lack the column."""
    if key in row.index:
        v = row[key]
        # pandas uses NaN for missing; treat as None
        if v is None:
            return None
        try:
            import math

            if isinstance(v, float) and math.isnan(v):
                return None
        except TypeError:
            pass
        return v
    return None


def build_from_objects(objects: dict, observations: dict) -> "tuple[list, list, list]":
    """Build (manholes, pipes, inspections) from parser output dicts."""
    manholes: list = []
    pipes: list = []
    inspections: list = []

    seen_manholes: dict = {}

    # --- Pipes (ZB_A) ---
    if "A" in objects:
        df = objects["A"]
        for idx, row in df.iterrows():
            code = _get(row, fm.REF_FIELDS["A"])
            if code is None:
                continue
            pipe = Pipe(
                code=str(code),
                manhole1=str(_get(row, fm.NODE1_FIELDS["A"]) or ""),
                manhole2=str(_get(row, fm.NODE2_FIELDS["A"]) or ""),
                geometry_wkt=gml_poslist_to_wkt_linestring(_get(row, fm.PIPE_GEOM_FIELDS["A"])),
                shape=str(_get(row, fm.PIPE_SHAPE_FIELD) or "A"),
                diameter=_to_float(_get(row, fm.PIPE_DIAMETER_FIELD)),
                width=_to_float(_get(row, fm.PIPE_WIDTH_FIELD)),
                bob1=_to_float(_get(row, fm.PIPE_BOB1_FIELD)),
                bob2=_to_float(_get(row, fm.PIPE_BOB2_FIELD)),
                material=_opt_str(_get(row, fm.PIPE_MATERIAL_FIELD)),
                sewerage_type=_opt_str(_get(row, fm.PIPE_SEWERAGE_TYPE_FIELD)),
                inspection_date=_to_date(_get(row, fm.DATE_FIELDS["A"])),
                source_line=_to_int(_get(row, "_source_line")),
            )
            pipes.append(pipe)

            # Endpoint manholes from pipe node geometry (if not separately present)
            _register_endpoint(seen_manholes, pipe.manhole1,
                               gml_pos_to_wkt_point(_get(row, fm.NODE1_GEOM_FIELDS["A"])))
            _register_endpoint(seen_manholes, pipe.manhole2,
                               gml_pos_to_wkt_point(_get(row, fm.NODE2_GEOM_FIELDS["A"])))

            insp = Inspection(
                object_code=pipe.code,
                object_type="A",
                date=pipe.inspection_date,
                observations=_build_observations(observations.get("A"), pipe.code, idx),
            )
            inspections.append(insp)

    # --- Manholes (ZB_C) — authoritative geometry overrides endpoint guesses ---
    if "C" in objects:
        df = objects["C"]
        for _idx, row in df.iterrows():
            code = _get(row, fm.REF_FIELDS["C"])
            if code is None:
                continue
            seen_manholes[str(code)] = Manhole(
                code=str(code),
                geometry_wkt=gml_pos_to_wkt_point(_get(row, fm.MANHOLE_GEOM_FIELDS["C"])),
                node_type=_opt_str(_get(row, fm.MANHOLE_NODE_TYPE_FIELD)),
                ground_level=_to_float(_get(row, fm.MANHOLE_GROUND_LEVEL_FIELD)),
                source_line=_to_int(_get(row, "_source_line")),
            )

    manholes = list(seen_manholes.values())
    return manholes, pipes, inspections


def _register_endpoint(seen: dict, code: str, wkt) -> None:
    """Add a manhole stub from a pipe endpoint if we don't have it yet."""
    if not code:
        return
    if code not in seen:
        seen[code] = Manhole(code=code, geometry_wkt=wkt)


def _build_observations(obs_df, object_code: str, object_idx: int) -> list:
    if obs_df is None or len(obs_df) == 0:
        return []
    subset = obs_df[obs_df["_object_idx"] == object_idx]
    result = []
    for _i, row in subset.iterrows():
        kwargs = {"object_code": object_code, "code": str(_get(row, "A") or "")}
        for ribx_field, attr in fm.OBSERVATION_FIELD_MAP.items():
            if attr == "code":
                continue
            value = _get(row, ribx_field)
            if attr == "distance":
                kwargs[attr] = _to_float(value)
            else:
                kwargs[attr] = _opt_str(value)
        result.append(Observation(**kwargs))
    return result


def _opt_str(value) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


def _to_int(value) -> Optional[int]:
    f = _to_float(value)
    return int(f) if f is not None else None


def build_from_ribx(ribx_path: "Path | str") -> BuildResult:
    """Parse a RIBX file and build the domain model."""
    objects, observations, errors = ribx_to_pandas(ribx_path)
    manholes, pipes, inspections = build_from_objects(objects, observations)
    return BuildResult(manholes=manholes, pipes=pipes, inspections=inspections, errors=errors)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_build.py -v`
Expected: PASS (3 passed). If `_get` reports a column missing for `ACC`/`ACJ` (not in fixture), it correctly returns None — the test does not assert those.

- [ ] **Step 5: Commit**

```bash
git add src/rgs_ribx/model/field_maps.py src/rgs_ribx/model/build.py tests/test_build.py
git commit -m "feat: build domain entities from RIBX DataFrames"
```

---

## Task 7: Measurement profile + flooded-percentage math

**Files:**
- Create: `src/rgs_ribx/lost_capacity/__init__.py`
- Create: `src/rgs_ribx/lost_capacity/profile.py`
- Test: `tests/test_profile.py`

Port `set_water_level`, `compute_flooded_pct`, and `disc_segment` from lizard `models.py` (lines 532-598) to a plain `MeasurementPoint` dataclass.

- [ ] **Step 1: Create `src/rgs_ribx/lost_capacity/__init__.py`** (empty for now)

```python
```

- [ ] **Step 2: Write the failing test `tests/test_profile.py`**

```python
import math

import pytest

from rgs_ribx.lost_capacity.profile import MeasurementPoint, disc_segment


def test_set_water_level_clamps_between_bob_and_obb():
    p = MeasurementPoint(dist=0.0, bob=-2.0, obb=-1.7)
    p.set_water_level(-5.0)
    assert p.water_level == -2.0  # clamped up to bob
    p.set_water_level(0.0)
    assert p.water_level == -1.7  # clamped down to obb
    p.set_water_level(None)
    assert p.water_level is None


def test_flooded_pct_dry_and_full():
    p = MeasurementPoint(dist=0.0, bob=-2.0, obb=-1.7)  # diameter 0.3
    p.set_water_level(-2.0)
    p.compute_flooded_pct(is_rectangular=False)
    assert p.flooded_pct == 0
    p.set_water_level(-1.7)
    p.compute_flooded_pct(is_rectangular=False)
    assert p.flooded_pct == 1


def test_flooded_pct_rectangular_half():
    p = MeasurementPoint(dist=0.0, bob=0.0, obb=1.0)
    p.set_water_level(0.5)
    p.compute_flooded_pct(is_rectangular=True)
    assert p.flooded_pct == pytest.approx(0.5)


def test_flooded_pct_circular_half_is_half():
    # Water exactly at centre of a circular pipe -> 50% area.
    p = MeasurementPoint(dist=0.0, bob=0.0, obb=1.0)  # diameter 1.0, radius 0.5
    p.set_water_level(0.5)
    p.compute_flooded_pct(is_rectangular=False)
    assert p.flooded_pct == pytest.approx(0.5)


def test_disc_segment_quarter_circle_known_value():
    # Segment height = radius/2 of unit-radius circle.
    area = disc_segment(radius=1.0, height=0.5)
    # angle = 2*acos(0.5) = 2*pi/3 ; area = 0.5*(angle - sin(angle))
    angle = 2 * math.acos(0.5)
    expected = 0.5 * (angle - math.sin(angle))
    assert area == pytest.approx(expected)
```

- [ ] **Step 3: Write `src/rgs_ribx/lost_capacity/profile.py`**

```python
"""Measurement points and flooded-area math.

Ported from lizard-progress src/sewer/models.py (PipeMeasurement.set_water_level,
compute_flooded_pct, disc_segment). Decoupled from Django: the circular/
rectangular choice is passed in as a flag instead of reading the Pipe model.
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class MeasurementPoint:
    """A point along a pipe with an invert (bob) and crown (obb) level.

    ``obb`` (top of pipe) is normally ``bob + diameter``. ``water_level`` and
    ``flooded_pct`` are filled in by the lost-capacity algorithm.
    """

    dist: float
    bob: float
    obb: float
    virtual: bool = False
    water_level: Optional[float] = None
    flooded_pct: Optional[float] = None

    def set_water_level(self, water_level: Optional[float]) -> None:
        """Clamp the water level to lie within [bob, obb]."""
        if water_level is None:
            self.water_level = None
        else:
            self.water_level = max(self.bob, min(self.obb, water_level))

    def compute_flooded_pct(self, is_rectangular: bool) -> None:
        """Compute the fraction of the cross-section that is flooded."""
        if self.water_level is None:
            self.flooded_pct = None
            return

        depth = self.water_level - self.bob
        if depth <= 0.0:
            self.flooded_pct = 0
            return

        diameter = self.obb - self.bob
        if depth >= diameter:
            self.flooded_pct = 1
            return

        if is_rectangular:
            self.flooded_pct = depth / diameter
            return

        # Circular cross-section.
        area = math.pi * ((diameter / 2) ** 2)
        if depth == diameter / 2:
            percentage = 0.5
        elif depth < diameter / 2:
            percentage = disc_segment(radius=diameter / 2, height=depth) / area
        else:
            percentage = (area - disc_segment(radius=diameter / 2, height=diameter - depth)) / area
        self.flooded_pct = percentage


def disc_segment(radius: float, height: float) -> float:
    """Area of a circular segment of given height in a circle of given radius.

    Requires ``0 < height < radius``. See
    https://en.wikipedia.org/wiki/Circular_segment.
    """
    assert height < radius
    assert height != 0
    assert radius != 0

    radius = float(radius)
    height = float(height)

    angle = 2 * math.acos((radius - height) / radius)
    area = ((radius ** 2) / 2) * (angle - math.sin(angle))
    return area
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_profile.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rgs_ribx/lost_capacity/__init__.py src/rgs_ribx/lost_capacity/profile.py tests/test_profile.py
git commit -m "feat: measurement point and flooded-area math"
```

---

## Task 8: Pure-Python graph (replace networkx)

**Files:**
- Create: `src/rgs_ribx/lost_capacity/graph.py`
- Test: `tests/test_graph.py`

A minimal undirected graph with per-node attribute dicts, exposing exactly what the flood-fill algorithm uses: `add_node(node, **attrs)`, `add_edge(a, b)`, `nodes[node]` (attr dict), `neighbors(node)` / `graph[node]` (iterable of neighbors). This replaces `networkx.Graph`.

- [ ] **Step 1: Write the failing test `tests/test_graph.py`**

```python
import pytest

from rgs_ribx.lost_capacity.graph import Graph


def test_add_node_stores_attributes():
    g = Graph()
    g.add_node("a", bob=-2.0, waterlevel=None)
    assert g.nodes["a"]["bob"] == -2.0
    assert g.nodes["a"]["waterlevel"] is None


def test_add_edge_is_undirected():
    g = Graph()
    g.add_node("a")
    g.add_node("b")
    g.add_edge("a", "b")
    assert "b" in g["a"]
    assert "a" in g["b"]


def test_neighbors_sorted_access():
    g = Graph()
    for n in ("a", "b", "c"):
        g.add_node(n)
    g.add_edge("a", "c")
    g.add_edge("a", "b")
    assert sorted(g["a"]) == ["b", "c"]


def test_add_edge_unknown_node_raises():
    g = Graph()
    g.add_node("a")
    with pytest.raises(KeyError):
        g.add_edge("a", "missing")
```

- [ ] **Step 2: Write `src/rgs_ribx/lost_capacity/graph.py`**

```python
"""A tiny undirected graph with per-node attributes.

Only the operations used by the lost-capacity flood-fill are implemented,
so we avoid a networkx dependency (not bundled with QGIS). API mirrors the
networkx subset used: ``add_node(node, **attrs)``, ``add_edge(a, b)``,
``g.nodes[node]`` (attribute dict), ``g[node]`` (neighbor set).
"""


class Graph:
    """Undirected graph keyed by hashable node ids (e.g. tuples)."""

    def __init__(self) -> None:
        self.nodes: dict = {}       # node -> attribute dict
        self._adj: dict = {}        # node -> set of neighbor nodes

    def add_node(self, node, **attrs) -> None:
        """Add a node (or update its attributes if it already exists)."""
        if node not in self.nodes:
            self.nodes[node] = {}
            self._adj[node] = set()
        self.nodes[node].update(attrs)

    def add_edge(self, a, b) -> None:
        """Add an undirected edge between two existing nodes."""
        if a not in self.nodes:
            raise KeyError(a)
        if b not in self.nodes:
            raise KeyError(b)
        self._adj[a].add(b)
        self._adj[b].add(a)

    def __getitem__(self, node):
        """Return the set of neighbors of ``node`` (mirrors networkx ``G[node]``)."""
        return self._adj[node]

    def neighbors(self, node):
        return self._adj[node]

    def __contains__(self, node) -> bool:
        return node in self.nodes
```

- [ ] **Step 3: Run test to verify it passes**

Run: `python -m pytest tests/test_graph.py -v`
Expected: PASS (4 passed)

- [ ] **Step 4: Commit**

```bash
git add src/rgs_ribx/lost_capacity/graph.py tests/test_graph.py
git commit -m "feat: minimal pure-Python graph (replaces networkx)"
```

---

## Task 9: Flood-fill water-level computation

**Files:**
- Create: `src/rgs_ribx/lost_capacity/compute.py`
- Test: `tests/test_compute.py`

Port `lost_capacity.py` (`get_manhole_bobs`, `create_graph`, `compute_water_level`, `neighbouring_nodes_satisfying_condition`, `add_lost_capacity`) to operate on our entities and `Graph`. The orchestrator `compute_lost_capacity` takes the entities plus a dict of measurement profiles and annotates the `MeasurementPoint`s in place.

**Input contract for `compute_lost_capacity`:**
- `manholes: dict[str, Manhole]` keyed by code (must include `is_sink` flags)
- `pipes: dict[str, Pipe]` keyed by code (must have `manhole1`, `manhole2`, `bob1`, `bob2`)
- `profiles: dict[str, list[MeasurementPoint]]` keyed by pipe code — the interior longitudinal profile per pipe (may be empty; endpoints are added by the algorithm)

- [ ] **Step 1: Write the failing test `tests/test_compute.py`**

```python
import pytest

from rgs_ribx.lost_capacity.compute import compute_lost_capacity
from rgs_ribx.lost_capacity.profile import MeasurementPoint
from rgs_ribx.model.entities import Manhole, Pipe


def _circular(bob, diameter=0.3):
    return MeasurementPoint(dist=0.0, bob=bob, obb=bob + diameter)


def test_single_pipe_with_dip_floods_the_dip():
    # Two manholes, one pipe sloping down then up: a dip in the middle holds water.
    # bob1 = -2.0 at P1 (sink), bob2 = -2.0 at P2, mid point sags to -2.3.
    manholes = {
        "P1": Manhole(code="P1", is_sink=True),
        "P2": Manhole(code="P2", is_sink=True),
    }
    pipes = {
        "L1": Pipe(code="L1", manhole1="P1", manhole2="P2",
                   bob1=-2.0, bob2=-2.0, diameter=0.3, shape="A"),
    }
    mid = MeasurementPoint(dist=15.0, bob=-2.3, obb=-2.0)
    profiles = {"L1": [mid]}

    compute_lost_capacity(manholes, pipes, profiles)

    # Water rises to the lowest shoreline (-2.0) so the sagged midpoint is flooded.
    assert mid.water_level == pytest.approx(-2.0)
    assert mid.flooded_pct is not None
    assert mid.flooded_pct > 0


def test_no_dip_means_no_flooding():
    # Monotone downhill pipe: no interior point sits below its downstream shore.
    manholes = {
        "P1": Manhole(code="P1", is_sink=False),
        "P2": Manhole(code="P2", is_sink=True),
    }
    pipes = {
        "L1": Pipe(code="L1", manhole1="P1", manhole2="P2",
                   bob1=-2.0, bob2=-2.6, diameter=0.3, shape="A"),
    }
    mid = MeasurementPoint(dist=15.0, bob=-2.3, obb=-2.0)
    profiles = {"L1": [mid]}

    compute_lost_capacity(manholes, pipes, profiles)

    # Midpoint water level equals its own bob (no extra water held) -> dry.
    assert mid.flooded_pct == 0
```

- [ ] **Step 2: Write `src/rgs_ribx/lost_capacity/compute.py`**

```python
"""Lost-capacity (verloren berging) computation.

Ported from lizard-progress src/sewer/lost_capacity.py, replacing networkx
with rgs_ribx.lost_capacity.graph.Graph and Django models with plain
entities + MeasurementPoint objects.
"""

from collections import defaultdict
from heapq import heappop, heappush
from itertools import chain

from rgs_ribx.lost_capacity.graph import Graph


def compute_lost_capacity(manholes: dict, pipes: dict, profiles: dict) -> None:
    """Annotate each MeasurementPoint in ``profiles`` with water_level + flooded_pct.

    Parameters
    ----------
    manholes : dict[str, Manhole]
    pipes : dict[str, Pipe]
    profiles : dict[str, list[MeasurementPoint]]
        Interior measurement points per pipe code (ordered or not).
    """
    graph, sink_node = create_graph(manholes, pipes, profiles)
    if graph is None:
        return
    compute_water_level(graph, sink_node)
    add_lost_capacity(profiles, pipes, graph)


def get_manhole_bobs(pipes: dict) -> dict:
    """Return {manhole_code: lowest connected bob}."""
    manhole_bobs = defaultdict(list)
    for pipe in pipes.values():
        if pipe.bob1 is not None:
            manhole_bobs[pipe.manhole1].append(pipe.bob1)
        if pipe.bob2 is not None:
            manhole_bobs[pipe.manhole2].append(pipe.bob2)
    return {code: min(bobs) for code, bobs in manhole_bobs.items() if bobs}


def create_graph(manholes: dict, pipes: dict, profiles: dict):
    """Build the graph of puts, pipe-ends, and measurement points."""
    graph = Graph()
    manhole_bobs = get_manhole_bobs(pipes)

    for pipe_code, pipe in pipes.items():
        if pipe.bob1 is None or pipe.bob2 is None:
            continue
        m1, m2 = pipe.manhole1, pipe.manhole2
        interior = sorted(profiles.get(pipe_code, []), key=lambda p: p.dist)

        previous = None
        for location, bob in chain(
            [(("put", m1), manhole_bobs.get(m1, pipe.bob1)),
             (("sewer_end", pipe_code, "1"), pipe.bob1)],
            ((("measurement", pipe_code, mp.dist), mp.bob) for mp in interior),
            [(("sewer_end", pipe_code, "2"), pipe.bob2),
             (("put", m2), manhole_bobs.get(m2, pipe.bob2))],
        ):
            graph.add_node(location, bob=bob, waterlevel=None)
            if previous is not None:
                graph.add_edge(previous, location)
            previous = location

    sink_ids = [code for code, m in manholes.items() if getattr(m, "is_sink", False)]
    sink_ids = [s for s in sink_ids if ("put", s) in graph]
    if not sink_ids:
        return None, None
    if len(sink_ids) == 1:
        sink_id = sink_ids[0]
    else:
        sink_id = min(sink_ids, key=lambda s: graph.nodes[("put", s)]["bob"])
        for higher in sink_ids:
            if higher == sink_id:
                continue
            graph.add_edge(("put", sink_id), ("put", higher))
    return graph, ("put", sink_id)


def compute_water_level(graph: Graph, sink_node) -> None:
    """Flood-fill water levels upward from the sink (Mario Frasca's algorithm)."""
    todo = []
    done = set()
    heappush(todo, (graph.nodes[sink_node]["bob"], sink_node))

    while todo:
        water_level, current_node = heappop(todo)

        def under_water_condition(parent, child):
            return graph.nodes[child]["bob"] < water_level

        under_water_list, shore_node_pairs = neighbouring_nodes_satisfying_condition(
            graph, current_node, done, under_water_condition
        )
        done = done.union(under_water_list)
        for node in under_water_list:
            graph.nodes[node]["waterlevel"] = water_level

        for _shore_from, shore_to in shore_node_pairs:
            def not_going_down_condition(parent, child):
                return graph.nodes[parent]["bob"] <= graph.nodes[child]["bob"]

            going_up_list, peak_node_pairs = neighbouring_nodes_satisfying_condition(
                graph, shore_to, done, not_going_down_condition
            )
            done = done.union(going_up_list)
            for node in going_up_list:
                graph.nodes[node]["waterlevel"] = graph.nodes[node]["bob"]
            for peak_from, peak_to in peak_node_pairs:
                graph.nodes[peak_from]["waterlevel"] = graph.nodes[peak_from]["bob"]
                heappush(todo, (graph.nodes[peak_from]["bob"], peak_to))


def neighbouring_nodes_satisfying_condition(graph: Graph, start, visited, condition):
    """DFS pre-order returning (satisfied_nodes, border_edges).

    See lizard's docstring: border edges are (parent, child) pairs where the
    condition failed and ``child`` is not otherwise satisfied.
    """
    visited = set(visited)
    satisfied = []
    border = []
    stack = [(start, iter([start]))]

    while stack:
        parent, children = stack.pop()
        for child in children:
            if child in visited:
                continue
            if condition(parent, child):
                visited.add(child)
                satisfied.append(child)
                stack.append((child, iter(sorted(graph[child]))))
            else:
                border.append((parent, child))
    satisfied_set = set(satisfied)
    return satisfied, [(p, c) for p, c in border if c not in satisfied_set]


def add_lost_capacity(profiles: dict, pipes: dict, graph: Graph) -> None:
    """Assign water levels + flooded_pct to each interior measurement point."""
    for pipe_code, measurements in profiles.items():
        pipe = pipes[pipe_code]
        for mp in measurements:
            node = ("measurement", pipe_code, mp.dist)
            if node in graph:
                mp.set_water_level(graph.nodes[node]["waterlevel"])
            else:
                mp.set_water_level(None)
            mp.compute_flooded_pct(is_rectangular=pipe.is_rectangular)
```

- [ ] **Step 3: Run test to verify it passes**

Run: `python -m pytest tests/test_compute.py -v`
Expected: PASS (2 passed)

- [ ] **Step 4: Run the whole suite**

Run: `python -m pytest`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add src/rgs_ribx/lost_capacity/compute.py tests/test_compute.py
git commit -m "feat: port lost-capacity flood-fill computation"
```

---

## Task 10: Public API + README

**Files:**
- Modify: `src/rgs_ribx/__init__.py`
- Modify: `src/rgs_ribx/lost_capacity/__init__.py`
- Create: `README.md`
- Test: `tests/test_public_api.py`

- [ ] **Step 1: Write the failing test `tests/test_public_api.py`**

```python
def test_top_level_imports():
    import rgs_ribx

    assert hasattr(rgs_ribx, "build_from_ribx")
    assert hasattr(rgs_ribx, "compute_lost_capacity")
    assert hasattr(rgs_ribx, "MeasurementPoint")
    assert hasattr(rgs_ribx, "Pipe")
    assert hasattr(rgs_ribx, "Manhole")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_public_api.py -v`
Expected: FAIL with `AssertionError` on `build_from_ribx`.

- [ ] **Step 3: Update `src/rgs_ribx/lost_capacity/__init__.py`**

```python
from rgs_ribx.lost_capacity.compute import compute_lost_capacity
from rgs_ribx.lost_capacity.profile import MeasurementPoint, disc_segment

__all__ = ["compute_lost_capacity", "MeasurementPoint", "disc_segment"]
```

- [ ] **Step 4: Update `src/rgs_ribx/__init__.py`**

```python
"""rgs-ribx: read RIBX sewer data and compute lost storage capacity."""

from rgs_ribx.lost_capacity import MeasurementPoint, compute_lost_capacity
from rgs_ribx.model.build import BuildResult, build_from_objects, build_from_ribx
from rgs_ribx.model.entities import Inspection, Manhole, Observation, Pipe

__version__ = "0.1.0"

__all__ = [
    "build_from_ribx",
    "build_from_objects",
    "BuildResult",
    "compute_lost_capacity",
    "MeasurementPoint",
    "Manhole",
    "Pipe",
    "Observation",
    "Inspection",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_public_api.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Write `README.md`**

```markdown
# rgs-ribx

Read RIBX (NEN 13508-2) sewer inspection files into a typed Python data model
and compute "verloren berging" (lost storage capacity). Pure Python — no
Django, no QGIS, no networkx.

## Install

    pip install -e ".[dev]"

## Usage

```python
import rgs_ribx

result = rgs_ribx.build_from_ribx("inspection.ribx")
print(len(result.pipes), "pipes", len(result.manholes), "manholes")

# Lost capacity: build {pipe_code: [MeasurementPoint, ...]} profiles first,
# then annotate them in place.
manholes = {m.code: m for m in result.manholes}
pipes = {p.code: p for p in result.pipes}
profiles = {}  # build from inclination observations; see plugin
rgs_ribx.compute_lost_capacity(manholes, pipes, profiles)
```

## Layout

- `rgs_ribx.parsing` — RIBX XML -> pandas DataFrames + header definitions
- `rgs_ribx.model` — entities + builder + geometry (WKT, EPSG:28992)
- `rgs_ribx.lost_capacity` — flooded-area math + flood-fill water levels
```

- [ ] **Step 7: Run the full suite once more and commit**

Run: `python -m pytest`
Expected: PASS (all green)

```bash
git add src/rgs_ribx/__init__.py src/rgs_ribx/lost_capacity/__init__.py README.md tests/test_public_api.py
git commit -m "feat: public API and README"
```

---

## Task 11: Finish the branch

- [ ] **Step 1: Verify everything**

Run:
```bash
cd ~/Documents/GitHub/rgs-ribx
python -m pytest -v
python -c "import rgs_ribx; print(rgs_ribx.__version__)"
ruff check src tests
```
Expected: all tests pass, version prints, ruff reports no errors (fix any it finds).

- [ ] **Step 2: Use the finishing-a-development-branch skill**

REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch` to decide merge/PR/cleanup. Do NOT push without explicit instruction (user's global rule).

---

## Open items to confirm with the user during execution

These do not block the library but affect how the plugin (separate plan) feeds it:

1. **Longitudinal profile source.** `compute_lost_capacity` needs `profiles: {pipe_code: [MeasurementPoint]}` — the interior bob-along-distance. lizard derives this from `*MRIO` inclination measurements (ZYS types A/AA/B/J/K). In RIBX these correspond to specific observation codes; the exact code mapping must be confirmed against a real RIBX with inclination data. Until then, pipes with no interior points are modeled by their two BOB endpoints (no sag → zero lost capacity).
2. **Sawtooth/BOB correction.** lizard applies `correct_bob_values` (ideal-line correction) before computing. This plan ports the core algorithm only; if real data shows the sawtooth artifact, add a `correct_profile` function as a follow-up task (the math is in `lizard-progress/src/sewer/save_uploaded_data.py::correct_bob_values`).
