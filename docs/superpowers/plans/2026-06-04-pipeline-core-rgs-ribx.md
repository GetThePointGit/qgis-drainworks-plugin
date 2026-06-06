# Pipeline Core (rgs-ribx) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the `rgs-ribx` library so parsing yields *raw* inclination measurements, and a separate, re-runnable `enrich` step integrates heights, builds aggregated segments, and validates — the foundation for the plugin's 3-step pipeline.

**Architecture:** Additive and non-breaking. `build_from_ribx` / `build_from_sufrib` keep their current output but also populate `BuildResult.raw_measurements` (per pipe: measurement type, direction, and raw `(dist, value)` points). New pure-Python modules `enrich.py` (integrate heights from raw + the pipe's current BOBs), `segments.py` (aggregate into segments), and `validation.py` (completeness + range checks) operate on plain entities so the plugin (a later plan) can re-run them after edits. No QGIS, no Django.

**Tech Stack:** Python 3.9+, pytest. Reuses `rgs_ribx.model.inclination.build_inclination_profile` and `rgs_ribx.lost_capacity.correct_profile_to_bobs`.

**Spec:** `docs/superpowers/specs/2026-06-04-drainworks-1.0-refinements-design.md` (sections 1 + 4).

**Repo:** `~/Documents/GitHub/rgs-ribx`. Run tests with `.venv/bin/python -m pytest` (Python 3.12 venv from earlier). Also works on the QGIS-LTR2 Python via `PYTHONPATH=src`.

> **Git (user rule):** never commit on `main`. Start with `git switch -c feature/pipeline-core`. Never `git push` unless told.

---

## File Structure

```
rgs-ribx/src/rgs_ribx/
├── model/
│   ├── build.py          # MODIFY: populate BuildResult.raw_measurements (additive)
│   ├── raw.py            # CREATE: RawMeasurements dataclass (per-pipe mtype/reverse/points)
│   ├── enrich.py         # CREATE: integrate_profiles() — raw + pipes -> {code: [MeasurementPoint]}
│   ├── segments.py       # CREATE: Segment dataclass + build_segments()
│   └── validation.py     # CREATE: validate_network() -> per-feature issues
└── (tests/ mirrors)
```

Responsibilities:
- `raw.py` — the data carrier for un-integrated measurements (one per pipe).
- `enrich.py` — turn raw measurements + current BOBs into a height profile (with optional BOB correction). Re-runnable.
- `segments.py` — aggregate a profile (or a BOB line) into segments with the spec's attributes.
- `validation.py` — completeness + range checks, returning structured issues.

---

## Task 1: RawMeasurements data carrier

**Files:**
- Create: `src/rgs_ribx/model/raw.py`
- Test: `tests/test_raw.py`

- [ ] **Step 1: Write the failing test** `tests/test_raw.py`:

```python
from rgs_ribx.model.raw import RawMeasurements


def test_raw_measurements_holds_points_type_and_direction():
    raw = RawMeasurements(
        pipe_code="L1",
        measurement_type="J",
        reverse=False,
        points=[{"dist": 0.0, "value": -2.0}, {"dist": 10.0, "value": -5.0}],
    )
    assert raw.pipe_code == "L1"
    assert raw.measurement_type == "J"
    assert raw.reverse is False
    assert len(raw.points) == 2
    assert raw.points[0]["value"] == -2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_raw.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rgs_ribx.model.raw'`

- [ ] **Step 3: Write `src/rgs_ribx/model/raw.py`**:

```python
"""Raw (un-integrated) inclination/height measurements for one pipe."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawMeasurements:
    """The measurements of one pipe before height integration.

    ``measurement_type`` is the integration type (``J`` degrees, ``K`` percent,
    ``A``/``AA`` relative, ``B``/absolute). ``reverse`` is True when the survey
    ran from the pipe's manhole2. ``points`` are ``{"dist": float, "value": float}``.
    """

    pipe_code: str
    measurement_type: str
    reverse: bool = False
    points: list = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_raw.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rgs_ribx/model/raw.py tests/test_raw.py
git commit -m "feat: RawMeasurements data carrier"
```

---

## Task 2: Height integration (enrich)

**Files:**
- Create: `src/rgs_ribx/model/enrich.py`
- Test: `tests/test_enrich.py`

This integrates raw measurements into a height profile using each pipe's current
BOBs, with optional BOB correction. It reuses the validated
`build_inclination_profile` and `correct_profile_to_bobs`.

- [ ] **Step 1: Write the failing test** `tests/test_enrich.py`:

```python
import rgs_ribx
from rgs_ribx.model.enrich import integrate_profiles
from rgs_ribx.model.raw import RawMeasurements


def _pipe(code, bob1, bob2, length=30.0, diameter=0.3):
    return rgs_ribx.Pipe(code=code, manhole1="A", manhole2="B",
                         bob1=bob1, bob2=bob2, length=length, diameter=diameter, shape="A")


def test_integrate_absolute_type_b_profile():
    pipes = {"L1": _pipe("L1", -2.0, -2.0)}
    raw = {"L1": RawMeasurements("L1", "AA", reverse=False, points=[
        {"dist": 0.0, "value": 0.0},
        {"dist": 15.0, "value": -0.3},
        {"dist": 30.0, "value": 0.0},
    ])}
    profiles = integrate_profiles(pipes, raw, correct_bob=False)
    pts = sorted(profiles["L1"], key=lambda p: p.dist)
    assert [round(p.dist, 1) for p in pts] == [0.0, 15.0, 30.0]
    # AA = bob1 + (bob2-bob1)*pct + value ; flat bobs -> -2.0 + value
    assert [round(p.bob, 2) for p in pts] == [-2.0, -2.3, -2.0]


def test_integrate_applies_bob_correction_per_pipe():
    # Linear drift below a flat ideal -> de-trended to the ideal at all points.
    pipes = {"L1": _pipe("L1", -2.0, -2.0)}
    raw = {"L1": RawMeasurements("L1", "AA", reverse=False, points=[
        {"dist": 0.0, "value": -0.5},
        {"dist": 15.0, "value": -0.6},
        {"dist": 30.0, "value": -0.7},
    ])}
    profiles = integrate_profiles(pipes, raw, correct_bob=True)
    pts = sorted(profiles["L1"], key=lambda p: p.dist)
    assert [round(p.bob, 2) for p in pts] == [-2.0, -2.0, -2.0]


def test_integrate_skips_pipe_without_bobs():
    pipes = {"L1": _pipe("L1", None, None)}
    raw = {"L1": RawMeasurements("L1", "J", points=[{"dist": 0.0, "value": 0.0}])}
    assert integrate_profiles(pipes, raw, correct_bob=True) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_enrich.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rgs_ribx.model.enrich'`

- [ ] **Step 3: Write `src/rgs_ribx/model/enrich.py`**:

```python
"""Integrate raw measurements into a height profile per pipe (re-runnable).

Uses the pipe's current BOBs (so edited BOBs are honoured) and, optionally,
de-trends the profile onto those BOBs (sawtooth correction).
"""

from __future__ import annotations

from rgs_ribx.lost_capacity.profile import correct_profile_to_bobs
from rgs_ribx.model.inclination import build_inclination_profile


def integrate_profiles(pipes_by_code, raw_by_code, correct_bob=True):
    """Return ``{pipe_code: [MeasurementPoint]}`` for pipes that have raw points.

    Parameters
    ----------
    pipes_by_code : dict[str, Pipe]
    raw_by_code : dict[str, RawMeasurements]
    correct_bob : bool
        Apply BOB de-trending after integration.
    """
    profiles = {}
    for code, raw in raw_by_code.items():
        pipe = pipes_by_code.get(code)
        if pipe is None or pipe.bob1 is None or pipe.bob2 is None:
            continue
        if not raw.points:
            continue
        # Survey ran from manhole2 when reversed -> integrate from bob2.
        start_bob, end_bob = (pipe.bob2, pipe.bob1) if raw.reverse else (pipe.bob1, pipe.bob2)
        points = build_inclination_profile(
            [dict(p) for p in raw.points],
            horizontal_distance=pipe.length or 0.0,
            bob1=start_bob,
            bob2=end_bob,
            measurement_type=raw.measurement_type,
            diameter=pipe.diameter or 0.0,
            reverse=raw.reverse,
        )
        if not points:
            continue
        if correct_bob:
            correct_profile_to_bobs(points, pipe.bob1, pipe.bob2, pipe.length)
        profiles[code] = points
    return profiles
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_enrich.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rgs_ribx/model/enrich.py tests/test_enrich.py
git commit -m "feat: integrate_profiles (height integration + BOB correction)"
```

---

## Task 3: Segment building

**Files:**
- Create: `src/rgs_ribx/model/segments.py`
- Test: `tests/test_segments.py`

Aggregate a pipe's profile into segments of at least `min_length` (default 1.0 m),
carrying the spec attributes. For pipes without a measured profile, build
fixed-length BOB segments (default 5.0 m) from the straight bob1→bob2 line.

- [ ] **Step 1: Write the failing test** `tests/test_segments.py`:

```python
import rgs_ribx
from rgs_ribx.lost_capacity.profile import MeasurementPoint
from rgs_ribx.model.segments import build_segments


def _pipe(code, bob1, bob2, length=30.0, diameter=0.3):
    return rgs_ribx.Pipe(code=code, manhole1="A", manhole2="B",
                         bob1=bob1, bob2=bob2, length=length, diameter=diameter, shape="A")


def test_measured_segments_merge_to_min_length():
    pipe = _pipe("L1", -2.0, -2.0, length=4.0)
    # 0.5 m spacing -> 8 short steps; min_length 1.0 -> ~4 segments.
    pts = [MeasurementPoint(dist=d / 2.0, bob=-2.0 - (0.1 if d == 3 else 0.0), obb=-1.7)
           for d in range(9)]
    segs = build_segments(pipe, pts, min_length=1.0)
    assert all(s["length"] >= 1.0 - 1e-9 or s is segs[-1] for s in segs)
    assert segs[0]["dist_from"] == 0.0
    assert round(segs[-1]["dist_to"], 1) == 4.0
    assert all(s["source"] == "measured" for s in segs)
    # carries required attributes
    s = segs[0]
    for key in ("pipe_code", "dist_from", "dist_to", "length", "bob_start",
                "bob_end", "bob_highest", "slope_avg", "diameter", "n_measurements", "source"):
        assert key in s


def test_bob_segments_for_pipe_without_measurements():
    pipe = _pipe("L1", -2.0, -2.6, length=12.0)
    segs = build_segments(pipe, [], bob_length=5.0)
    # 12 m / 5 m -> 3 segments (5, 5, 2)
    assert [round(s["length"], 1) for s in segs] == [5.0, 5.0, 2.0]
    assert all(s["source"] == "bob" for s in segs)
    # straight line: bob_start of first = bob1
    assert round(segs[0]["bob_start"], 2) == -2.0
    assert round(segs[-1]["bob_end"], 2) == -2.6


def test_no_segments_without_bobs_or_points():
    assert build_segments(_pipe("L1", None, None), []) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_segments.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rgs_ribx.model.segments'`

- [ ] **Step 3: Write `src/rgs_ribx/model/segments.py`**:

```python
"""Aggregate a pipe profile (or its BOB line) into segments.

Measured pipes: merge consecutive measurement points into segments of at least
``min_length``. Un-measured pipes: split the straight bob1->bob2 line into
``bob_length`` pieces. Each segment carries van/tot distance, start/end BOB,
highest BOB, mean slope, diameter, measurement count and source.
"""

from __future__ import annotations


def _segment(pipe, d0, d1, b_start, b_end, b_high, n, source):
    length = d1 - d0
    slope = ((b_end - b_start) / length) if length else 0.0
    return {
        "pipe_code": pipe.code,
        "dist_from": d0,
        "dist_to": d1,
        "length": length,
        "bob_start": b_start,
        "bob_end": b_end,
        "bob_highest": b_high,
        "slope_avg": slope,
        "diameter": pipe.diameter,
        "n_measurements": n,
        "source": source,
    }


def build_segments(pipe, profile_points, min_length=1.0, bob_length=5.0):
    """Return a list of segment dicts for one pipe."""
    pts = sorted(profile_points, key=lambda p: p.dist)
    if len(pts) >= 2:
        return _measured_segments(pipe, pts, min_length)
    if pipe.bob1 is not None and pipe.bob2 is not None and pipe.length:
        return _bob_segments(pipe, bob_length)
    return []


def _measured_segments(pipe, pts, min_length):
    segments = []
    start_i = 0
    for i in range(1, len(pts)):
        spanned = pts[i].dist - pts[start_i].dist
        is_last = i == len(pts) - 1
        if spanned >= min_length or is_last:
            window = pts[start_i:i + 1]
            bobs = [p.bob for p in window]
            segments.append(_segment(
                pipe, window[0].dist, window[-1].dist, window[0].bob, window[-1].bob,
                max(bobs), len(window), "measured"))
            start_i = i
    return segments


def _bob_segments(pipe, bob_length):
    segments = []
    length = pipe.length
    d = 0.0
    while d < length - 1e-9:
        d1 = min(d + bob_length, length)
        b0 = pipe.bob1 + (pipe.bob2 - pipe.bob1) * (d / length)
        b1 = pipe.bob1 + (pipe.bob2 - pipe.bob1) * (d1 / length)
        segments.append(_segment(pipe, d, d1, b0, b1, max(b0, b1), 0, "bob"))
        d = d1
    return segments
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_segments.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rgs_ribx/model/segments.py tests/test_segments.py
git commit -m "feat: build_segments (measured aggregation + BOB fallback segments)"
```

---

## Task 4: Network validation

**Files:**
- Create: `src/rgs_ribx/model/validation.py`
- Test: `tests/test_validation.py`

Per-feature completeness + range checks. Returns `{ "pipes": {code: [issue,...]},
"manholes": {code: [issue,...]} }` where each issue is a short string.

- [ ] **Step 1: Write the failing test** `tests/test_validation.py`:

```python
import rgs_ribx
from rgs_ribx.model.validation import validate_network


def test_pipe_completeness_and_ranges():
    manholes = [rgs_ribx.Manhole(code="A"), rgs_ribx.Manhole(code="B")]
    pipes = [
        # ok pipe
        rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="B", bob1=-2.0, bob2=-2.1,
                      diameter=0.3, length=30.0),
        # missing bob2, diameter out of range, manhole2 not present
        rgs_ribx.Pipe(code="L2", manhole1="A", manhole2="Z", bob1=-2.0, bob2=None,
                      diameter=5.0, length=30.0),
    ]
    result = validate_network(manholes, pipes)
    assert result["pipes"]["L1"] == []
    issues = " | ".join(result["pipes"]["L2"]).lower()
    assert "bob" in issues          # missing bob2
    assert "diameter" in issues     # 5.0 m -> 5000 mm > 3000
    assert "knoop" in issues or "manhole" in issues  # dangling manhole2


def test_measured_length_mismatch_flagged():
    manholes = [rgs_ribx.Manhole(code="A"), rgs_ribx.Manhole(code="B")]
    pipe = rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="B", bob1=-2.0, bob2=-2.1,
                         diameter=0.3, length=30.0)
    # measured length 50 m vs geometry 30 m -> >20% mismatch
    result = validate_network(manholes, [pipe], measured_length={"L1": 50.0})
    assert any("lengte" in i.lower() for i in result["pipes"]["L1"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rgs_ribx.model.validation'`

- [ ] **Step 3: Write `src/rgs_ribx/model/validation.py`**:

```python
"""Completeness + range validation of the sewer network (per feature)."""

from __future__ import annotations

DIAMETER_MIN_MM = 50.0
DIAMETER_MAX_MM = 3000.0
LENGTH_TOLERANCE = 0.20  # measured vs geometry length


def validate_network(manholes, pipes, measured_length=None):
    """Return {'pipes': {code: [issues]}, 'manholes': {code: [issues]}}."""
    measured_length = measured_length or {}
    manhole_codes = {m.code for m in manholes}

    pipe_issues = {}
    for p in pipes:
        issues = []
        if not p.code:
            issues.append("Leidingcode ontbreekt")
        if p.bob1 is None or p.bob2 is None:
            issues.append("BOB ontbreekt (begin of eind)")
        if p.diameter is None:
            issues.append("Diameter ontbreekt")
        else:
            d_mm = p.diameter * 1000.0
            if d_mm < DIAMETER_MIN_MM or d_mm > DIAMETER_MAX_MM:
                issues.append(f"Diameter buiten bereik ({d_mm:.0f} mm)")
        for ref in (p.manhole1, p.manhole2):
            if not ref or ref not in manhole_codes:
                issues.append(f"Knooppunt ontbreekt of onbekend ({ref!r})")
        ml = measured_length.get(p.code)
        if ml is not None and p.length:
            if abs(ml - p.length) > LENGTH_TOLERANCE * p.length:
                issues.append(f"Meetlengte wijkt af (gemeten {ml:.1f} m vs {p.length:.1f} m)")
        pipe_issues[p.code] = issues

    manhole_issues = {}
    for m in manholes:
        issues = []
        if not m.code:
            issues.append("Putcode ontbreekt")
        if m.geometry_wkt is None:
            issues.append("Geometrie ontbreekt")
        manhole_issues[m.code] = issues

    return {"pipes": pipe_issues, "manholes": manhole_issues}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_validation.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rgs_ribx/model/validation.py tests/test_validation.py
git commit -m "feat: validate_network (completeness + range checks)"
```

---

## Task 5: Expose raw measurements from RIBX parsing (additive)

**Files:**
- Modify: `src/rgs_ribx/model/build.py`
- Modify: `src/rgs_ribx/__init__.py`
- Test: `tests/test_build_raw.py`
- Modify fixture: `tests/fixtures/minimal.ribx`

`build_from_ribx` must also populate `BuildResult.raw_measurements`
(`{pipe_code: RawMeasurements}`) from the BXA observations, **without** changing
its existing behaviour. The integration step (Task 2) consumes this later.

- [ ] **Step 1: Add two BXA observations to the pipe in `tests/fixtures/minimal.ribx`**

Find the `<ZB_A>` ... `</ZB_A>` block's existing `<ZC>` entries and add two BXA rows just before `</ZB_A>` (B = type J, D = angle, I = distance):

```xml
    <ZC>
      <A>BXA</A>
      <B>J</B>
      <D>0.0</D>
      <I>0.0</I>
    </ZC>
    <ZC>
      <A>BXA</A>
      <B>J</B>
      <D>-1.0</D>
      <I>30.0</I>
    </ZC>
```

- [ ] **Step 2: Write the failing test** `tests/test_build_raw.py`:

```python
import rgs_ribx


def test_build_from_ribx_exposes_raw_measurements(fixtures_dir):
    result = rgs_ribx.build_from_ribx(fixtures_dir / "minimal.ribx")
    raw = result.raw_measurements
    assert "L001" in raw
    rm = raw["L001"]
    assert rm.measurement_type == "J"
    assert rm.reverse is False
    dists = sorted(p["dist"] for p in rm.points)
    assert dists == [0.0, 30.0]
    assert any(p["value"] == -1.0 for p in rm.points)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_build_raw.py -v`
Expected: FAIL with `AttributeError: 'BuildResult' object has no attribute 'raw_measurements'`

- [ ] **Step 4: Add `raw_measurements` to `BuildResult` and populate it.**

In `src/rgs_ribx/model/build.py`, find the `BuildResult` dataclass:

```python
@dataclass
class BuildResult:
    """Container for entities built from one RIBX file."""

    manholes: list
    pipes: list
    inspections: list
    errors: object  # pandas DataFrame from the parser
    measurements: dict = None  # {pipe_code: [MeasurementPoint]} from inclination
```

Replace with:

```python
@dataclass
class BuildResult:
    """Container for entities built from one RIBX file."""

    manholes: list
    pipes: list
    inspections: list
    errors: object  # pandas DataFrame from the parser
    measurements: dict = None      # {pipe_code: [MeasurementPoint]} (integrated, legacy)
    raw_measurements: dict = None  # {pipe_code: RawMeasurements} (un-integrated)
```

In the same file, find the pipe loop where `_build_inclination` is called (inside `build_from_objects`):

```python
            # Inspection ran from AAB; reverse if that is the second node.
            start_node = _opt_str(_get(row, fm.PIPE_START_NODE_FIELD))
            reverse = bool(start_node) and start_node == pipe.manhole2
            profile = _build_inclination(observations.get("A"), idx, pipe, reverse)
            if profile:
                measurements[pipe.code] = profile
```

Replace with (keeps the integrated profile AND records raw):

```python
            # Inspection ran from AAB; reverse if that is the second node.
            start_node = _opt_str(_get(row, fm.PIPE_START_NODE_FIELD))
            reverse = bool(start_node) and start_node == pipe.manhole2
            profile = _build_inclination(observations.get("A"), idx, pipe, reverse)
            if profile:
                measurements[pipe.code] = profile
            raw = _raw_inclination(observations.get("A"), idx, pipe.code, reverse)
            if raw is not None:
                raw_measurements[pipe.code] = raw
```

Find the start of `build_from_objects` where `measurements = {}` is initialised and add `raw_measurements = {}` next to it. Then find the return:

```python
    manholes = list(seen_manholes.values())
    return manholes, pipes, inspections, measurements
```

Replace with:

```python
    manholes = list(seen_manholes.values())
    return manholes, pipes, inspections, measurements, raw_measurements
```

Add the helper near `_build_inclination` (import `RawMeasurements` at the top of build.py: `from rgs_ribx.model.raw import RawMeasurements`):

```python
def _raw_inclination(obs_df, object_idx, pipe_code, reverse):
    """Collect raw BXA points (dist, value) + type for one pipe, or None."""
    if obs_df is None or len(obs_df) == 0:
        return None
    subset = obs_df[
        (obs_df["_object_idx"] == object_idx) & (obs_df["A"] == fm.INCLINATION_CODE)
    ]
    if len(subset) == 0:
        return None
    measurement_type = None
    points = []
    for _i, row in subset.iterrows():
        dist = _to_float(_get(row, "I"))
        value = _to_float(_get(row, "D"))
        if dist is None or value is None:
            continue
        if measurement_type is None:
            measurement_type = _opt_str(_get(row, "B"))
        points.append({"dist": dist, "value": value})
    if not points:
        return None
    return RawMeasurements(pipe_code=pipe_code, measurement_type=measurement_type or "",
                           reverse=reverse, points=points)
```

Update `build_from_ribx` to unpack the new 5-tuple and pass `raw_measurements`:

```python
def build_from_ribx(ribx_path: "Path | str") -> BuildResult:
    """Parse a RIBX file and build the domain model."""
    objects, observations, errors = ribx_to_pandas(ribx_path)
    manholes, pipes, inspections, measurements, raw_measurements = build_from_objects(
        objects, observations)
    return BuildResult(
        manholes=manholes,
        pipes=pipes,
        inspections=inspections,
        errors=errors,
        measurements=measurements,
        raw_measurements=raw_measurements,
    )
```

- [ ] **Step 5: Run test to verify it passes (and no regressions)**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all green — the existing `build_from_objects` callers all go through `build_from_ribx`, which now unpacks 5 values; if any other caller unpacks 4, fix it to 5).

- [ ] **Step 6: Commit**

```bash
git add src/rgs_ribx/model/build.py tests/test_build_raw.py tests/fixtures/minimal.ribx
git commit -m "feat: expose raw_measurements from RIBX parsing (additive)"
```

---

## Task 6: Expose raw measurements from SUFRIB parsing (additive)

**Files:**
- Modify: `src/rgs_ribx/model/build.py`
- Test: `tests/test_sufrib.py` (extend)

`build_from_sufrib` must also populate `BuildResult.raw_measurements` from the
`*MRIO` rows, without changing its current output.

- [ ] **Step 1: Write the failing test** — add to `tests/test_sufrib.py`:

```python
def test_build_from_sufrib_exposes_raw_measurements(tmp_path):
    rib, rmb = _write_example(tmp_path)
    res = rgs_ribx.build_from_sufrib([str(rib), str(rmb)])
    raw = res.raw_measurements
    assert "L1" in raw
    rm = raw["L1"]
    assert rm.measurement_type == "AA"   # ZYR=C, ZYS=B -> AA
    assert rm.reverse is False           # ZYB=1
    assert sorted(p["dist"] for p in rm.points) == [0.0, 15.0, 30.0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_sufrib.py::test_build_from_sufrib_exposes_raw_measurements -v`
Expected: FAIL with `AttributeError` (raw_measurements is None for the SUFRIB path).

- [ ] **Step 3: Populate `raw_measurements` in `build_from_sufrib`.**

In `src/rgs_ribx/model/build.py`, find `_build_sufrib_measurements` and add a sibling that returns raw. Then have `build_from_sufrib` set both. Add this function next to `_build_sufrib_measurements`:

```python
def _raw_sufrib_measurements(mrios, pipes_by_code) -> dict:
    """Group *MRIO rows into RawMeasurements per pipe."""
    by_sewer = {}
    for row in mrios:
        sewer = (row.get("ZYE") or "").strip()
        if sewer:
            by_sewer.setdefault(sewer, []).append(row)
    result = {}
    for sewer, rows in by_sewer.items():
        if sewer not in pipes_by_code:
            continue
        zyr = (rows[0].get("ZYR") or "").upper()
        zys = (rows[0].get("ZYS") or "").upper()
        mtype = {"AE": "J", "AF": "K", "CB": "AA"}.get(zyr + zys, "AA")
        reverse = rows[0].get("ZYB") == "2"
        points = []
        for row in rows:
            dist = _to_float(row.get("ZYA"))
            value = _to_float(row.get("ZYT"))
            if dist is None or value is None:
                continue
            exp = _to_int(row.get("ZYU"))
            if exp is not None:
                value *= 10 ** exp
            points.append({"dist": dist, "value": value})
        if points:
            result[sewer] = RawMeasurements(pipe_code=sewer, measurement_type=mtype,
                                            reverse=reverse, points=points)
    return result
```

In `build_from_sufrib`, find:

```python
    pipes_by_code = {p.code: p for p in pipes}
    measurements = _build_sufrib_measurements(mrios, pipes_by_code)
    return BuildResult(manholes=manholes, pipes=pipes, inspections=[],
                       errors=None, measurements=measurements)
```

Replace with:

```python
    pipes_by_code = {p.code: p for p in pipes}
    measurements = _build_sufrib_measurements(mrios, pipes_by_code)
    raw_measurements = _raw_sufrib_measurements(mrios, pipes_by_code)
    return BuildResult(manholes=manholes, pipes=pipes, inspections=[],
                       errors=None, measurements=measurements,
                       raw_measurements=raw_measurements)
```

- [ ] **Step 4: Run test to verify it passes (and no regressions)**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all green)

- [ ] **Step 5: Commit**

```bash
git add src/rgs_ribx/model/build.py tests/test_sufrib.py
git commit -m "feat: expose raw_measurements from SUFRIB parsing (additive)"
```

---

## Task 7: Public API + end-to-end enrich test

**Files:**
- Modify: `src/rgs_ribx/__init__.py`
- Test: `tests/test_pipeline_end_to_end.py`

Expose the new functions and prove the full step-2 flow (parse → integrate →
segments → validate) works from raw measurements, re-runnable after a BOB change.

- [ ] **Step 1: Write the failing test** `tests/test_pipeline_end_to_end.py`:

```python
import rgs_ribx


def test_enrich_pipeline_from_ribx(fixtures_dir):
    res = rgs_ribx.build_from_ribx(fixtures_dir / "minimal.ribx")
    pipes = {p.code: p for p in res.pipes}

    profiles = rgs_ribx.integrate_profiles(pipes, res.raw_measurements, correct_bob=True)
    assert "L001" in profiles and len(profiles["L001"]) >= 2

    segs = rgs_ribx.build_segments(pipes["L001"], profiles["L001"], min_length=1.0)
    assert segs and all(s["source"] == "measured" for s in segs)

    issues = rgs_ribx.validate_network(res.manholes, res.pipes)
    assert "L001" in issues["pipes"]


def test_enrich_is_rerunnable_after_bob_change(fixtures_dir):
    res = rgs_ribx.build_from_ribx(fixtures_dir / "minimal.ribx")
    pipes = {p.code: p for p in res.pipes}
    first = rgs_ribx.integrate_profiles(pipes, res.raw_measurements, correct_bob=True)
    first_end = sorted(first["L001"], key=lambda p: p.dist)[-1].bob

    pipes["L001"].bob2 = pipes["L001"].bob2 - 1.0  # edit a BOB
    second = rgs_ribx.integrate_profiles(pipes, res.raw_measurements, correct_bob=True)
    second_end = sorted(second["L001"], key=lambda p: p.dist)[-1].bob
    assert round(second_end - first_end, 2) == -1.0  # end follows the edited BOB
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pipeline_end_to_end.py -v`
Expected: FAIL with `AttributeError: module 'rgs_ribx' has no attribute 'integrate_profiles'`

- [ ] **Step 3: Export the new functions in `src/rgs_ribx/__init__.py`.**

Find the import block and `__all__`. Add these imports near the other model imports:

```python
from rgs_ribx.model.enrich import integrate_profiles
from rgs_ribx.model.segments import build_segments
from rgs_ribx.model.validation import validate_network
```

Add to `__all__`:

```python
    "integrate_profiles",
    "build_segments",
    "validate_network",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_pipeline_end_to_end.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full suite + ruff**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src tests`
Expected: all tests pass; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/rgs_ribx/__init__.py tests/test_pipeline_end_to_end.py
git commit -m "feat: export enrich/segments/validation; end-to-end pipeline test"
```

---

## Task 8: Finish the branch

- [ ] **Step 1: Verify everything**

Run:
```bash
cd ~/Documents/GitHub/rgs-ribx
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
.venv/bin/python -c "import rgs_ribx; print([x for x in ('integrate_profiles','build_segments','validate_network','build_from_ribx','build_from_sufrib') if hasattr(rgs_ribx, x)])"
```
Expected: all tests pass; ruff clean; all five names present.

- [ ] **Step 2: Use the finishing-a-development-branch skill**

REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch`. Do NOT push without explicit instruction (user's global rule).

---

## Notes for the follow-up plans (B and C)

- **Plan B (plugin data layer)** will: add `measurements_raw` / `profile` / `segments` layers to `geopackage_store`; split the runner into `enrich` (step 2: `integrate_profiles` + `build_segments` + `validate_network`, write profile/segments + `valid`/`issues` fields) and `berging` (step 3: flood-fill, accurate=on profile→aggregate to segments, fast=on segment endpoints); change import to write base + raw only.
- **Plan C (GUI & UX)** will: three step buttons + staleness + `QgsTask` async; trajectory rework; side-view settings + live BOB-line update; sinks table; opmaak legend/icon.
- The legacy `BuildResult.measurements` (integrated) stays until Plan B switches the plugin over, then it can be removed.
