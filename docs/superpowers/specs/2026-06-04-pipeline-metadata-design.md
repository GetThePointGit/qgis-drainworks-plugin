# Pipeline metadata + busy messageBar — design (C11)

**Goal:** Persist the pipeline state in the GeoPackage (a `dw_meta` table with a base-data
fingerprint, used settings, summaries, sinks) so that re-opening a GeoPackage shows the
enrich/berging steps green + filled when still up-to-date — with a fingerprint that also
catches in-between/external edits — and show a busy message with a running progress bar in
the messageBar while a step runs.

**Status:** decisions agreed (2026-06-04); feeds `writing-plans`.

**Builds on:** C1–C10. Touches `io/geopackage_store.py`, `pipeline/{enrich,berging}.py`,
`pipeline/state.py`, `ui/dock.py`, `plugin.py`, + a small `ui/busy.py`.

---

## 1. Busy messageBar item

While a step task (import / enrich / berging) runs, show a QGIS **messageBar** item at the
top: a message ("Importeren…" / "Verrijken…" / "Verloren berging berekenen…") plus an
**indeterminate** `QProgressBar` (range 0,0 → animated). The item is removed when the task
finishes (success or error). A small helper `ui/busy.py` (`start_busy(iface, text) ->
item`, `stop_busy(iface, item)`); the dock uses it for enrich/berging (in `_run_task` /
the done callbacks) and `plugin.on_import` for the import task.

## 2. `dw_meta` table in the GeoPackage

A geometry-less `dw_meta` table (`key` TEXT, `value` TEXT with JSON-encoded values) in the
GeoPackage. Store: `read_meta(path) -> {key: value}`, `write_meta(path, dict)` (merges /
replaces keys). Keys used:
- `enrich_fingerprint` — base-data fingerprint at enrich time (§4)
- `enrich_settings` — `{correct_bob, min_segment, bob_segment}`
- `enrich_summary` — `{n_segments, n_errors, n_warnings}`
- `berging_fingerprint` — `enrich_fingerprint` + the sorted sinks (so a sink change or a
  re-enrich invalidates it)
- `berging_settings` — `{resolution}`
- `berging_total` — total lost volume (m³)
- `sinks` — the chosen sink codes

## 3. Steps write their metadata

- **Enrich** (`pipeline/enrich.py`): after writing profile/segments + validation, compute
  the base fingerprint and `write_meta` `enrich_fingerprint` + `enrich_settings`
  (the params it ran with) + `enrich_summary` (`n_segments`/`n_errors`/`n_warnings`).
- **Berging** (`pipeline/berging.py`): after filling the segments, `write_meta`
  `berging_fingerprint` (the current `enrich_fingerprint` from meta + sorted sinks read
  from the manholes' `is_sink`), `berging_settings` (`{resolution}`), `berging_total`
  (`total_lost_volume`), and `sinks`.

## 4. Base-data fingerprint

`geopackage_store.base_fingerprint(path) -> str`: a stable SHA-1 over a canonical
serialisation of the data that drives the enrich output —
- pipes (sorted by code): `code, manhole1, manhole2, bob1, bob2, diameter, length, shape`
  (floats rounded to 6 decimals);
- `measurements_raw` (sorted by pipe_code, dist): `pipe_code, dist, value, mtype, reverse`;
- manholes (sorted by code): `code, ground_level, has_geometry`.
Editing a BOB/diameter/geometry/measurement therefore changes the fingerprint.

## 5. Load-time state restore (green when up-to-date)

`PipelineState` gains `restore(enrich_ran, enrich_fresh, berging_ran, berging_fresh)`
(pure) to set the flags directly. On `set_data`, after loading:
- compute the current `base_fingerprint`; `read_meta`.
- **Enrich:** if a `segments` layer exists →
  `enrich_ran=True`; `enrich_fresh = (meta.enrich_fingerprint == current_fingerprint)`.
  (No segments → not run.) Restore the `enrich_summary` label from meta when fresh.
- **Berging:** if `meta.berging_total` is present and enrich is fresh and
  `meta.berging_fingerprint == enrich_fingerprint + current sinks` → `berging_ran=True,
  berging_fresh=True` and restore the total label; else if berging was run but no longer
  matches → `berging_ran=True, berging_fresh=False`.
- Apply the stored `enrich_settings`/`berging_settings` to the QgsSettings keys so the gear
  dialogs show this GeoPackage's last-used settings (retrievable).

So re-opening an up-to-date GeoPackage shows both step cards "✓ actueel" with their
summary/total; editing the base data (now or earlier, in QGIS or elsewhere) makes the
fingerprint differ → "⚠ verouderd — verrijk opnieuw".

## 6. Sinks (answer + small robustness)

Sinks already persist via the manholes' `is_sink` field (written at berging time, restored
on load). `dw_meta.sinks` additionally records them at berging time for the berging
fingerprint; the `is_sink`-based restore in `set_data` stays the source of truth for the UI.

---

## 7. Out of scope

- No determinate %-progress (the messageBar bar is indeterminate); could be a later round.
- No migration of old GeoPackages without `dw_meta` — they simply read as "not run / no
  fingerprint" and behave like today (steps start stale).

## 8. Defaults

- Fingerprint: SHA-1 hex; floats rounded to 6 decimals.
- Busy bar: indeterminate (range 0,0).
