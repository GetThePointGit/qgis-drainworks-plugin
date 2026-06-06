# Code review — Drainworks 1.0 (round 2)

Date: 2026-06-06. Reviews the work added to PR #1 since
[`code-review-2026-06-04.md`](code-review-2026-06-04.md): the GeoPackage schema-version
check, stepped progress for all three steps, the import/enrich/berging performance
refactors (plugin + `rgs-ribx`), the side-view water rendering, and the trajectory
right-click behaviour.

Method: three independent reviewers over (1) the side-view water rendering, (2) the
performance refactors, (3) the QgsTask/progress/toggle/trajectory wiring. The flood-fill
change was additionally differential-tested over 3000 random trees (0 mismatches). Plugin
suite 94 green, `rgs-ribx` 64 green.

## Verdict

**No high-severity bugs.** The three performance refactors are behaviour-preserving
(verified by tests + differential testing + fingerprint equality on a 122 MB dataset).
Layering is intact (no OGR in the dock, no Qt in the pure cores). The QGIS-crash risk
(mutating the message bar inside `QgsTask.finished()`) is correctly avoided by the
`QTimer.singleShot(0, …)` deferral, which captures `error`/`result` before deferring.

## Fixed in this round

- **[medium] Re-entrancy could orphan the busy bar.** Starting a second task while one ran
  overwrote `self._busy` without stopping the first (the import button isn't disabled during
  a run). Added guards: `plugin.on_import` returns early if an import task is running;
  `dock._run_task` returns early if `active_task` is set — both with an info message.
- **[test-gap] profile-builder anchor water level.** Added a test that the pipe-end anchors
  inherit the adjacent measured water level (the pool-to-pipe-end extension).
- **[test-gap] `_observation_groups` multi-object.** The RIBX fixtures have a single `ZB_A`,
  so per-object grouping was never exercised. Added `rgs-ribx/tests/test_observation_groups.py`
  (multi-object grouping, int↔float `_object_idx` key, orphan-row drop, empty frame).

## Deferred / accepted (low severity)

- **Legend toggle vs settings dialog.** Clicking the water legend flips an in-memory
  `_show_water`; opening the side-view settings and pressing OK resets it to the saved
  default. Intended split (legend = transient, dialog = persisted); documented in the manual.
- **`read_segments`/`update_segments_berging` use `fi[name]`** (KeyError if a `segments`
  layer lacks a field). The invariant holds — `write_segments` always creates every field and
  `segments` is a Drainworks-internal layer (not part of `check_base_schema`). Left as-is.
- **`check_base_schema` accepts a gpkg with the right layers/fields but no `schema_version`.**
  Intentional (recognise by layers+fields); the required field set is specific enough.
- Nits: `_interp` unguarded on empty `xs` (unreachable via callers); `import bisect`
  function-local; `nan`/`eps` recreated per call; "Klaar"/100% is torn down immediately after
  the final report. None affect behaviour.

## Follow-ups worth a future increment

- A multi-pipe RIBX fixture so the full `build_from_objects` grouping path (not just the unit)
  is covered end-to-end.
- A branching-network unit test for `compute_water_level` (currently covered by the one-off
  differential harness, not a committed regression test).
- Cancel pending `singleShot` finalizers / running tasks in `dock.teardown()` to close the
  one-event-loop-tick unload-mid-task window (largely mitigated by `BusyIndicator` swallowing
  `RuntimeError`).
