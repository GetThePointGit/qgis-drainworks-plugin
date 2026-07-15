"""Step 2 — enrich base data: validate, integrate heights, build segments.

Reads the (possibly edited) ``manholes``/``pipes``/``measurements_raw`` from the
GeoPackage and writes ``profile`` + ``segments``, plus ``valid``/``issues`` on the
base layers. Any previously computed berging is wiped (segments are recreated
empty); step 3 fills them.

The step is split into a **compute** half (read + pure computation, safe to run in a
``QgsTask`` worker thread) and a **write** half (all GeoPackage writes). Writing /
finalising a large GeoPackage in a worker thread crashes QGIS on Windows, so the
controller runs :func:`enrich_compute` off-thread and :func:`enrich_write` on the
main thread. :func:`enrich` chains both for synchronous callers and tests.
"""

import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    base_fingerprint_from,
    linestring_substring_wkt,
    point_along_wkt,
    read_manholes,
    read_pipes,
    read_raw_measurements,
    refresh_pipe_derived,
    set_validation,
    write_meta,
    write_profile,
    write_segments,
)

# Defaults (configurable via the dock in Plan C).
MIN_SEGMENT = 1.0   # m, measured pipes
BOB_SEGMENT = 5.0   # m, pipes without measurements


def enrich_compute(gpkg_path, correct_bob=True, min_segment=MIN_SEGMENT,
                   bob_segment=BOB_SEGMENT, on_progress=None) -> dict:
    """Read the base data and compute the enrichment (no GeoPackage writes).

    Parameters
    ----------
    gpkg_path : str or pathlib.Path
        Path to the Drainworks GeoPackage.
    correct_bob : bool, optional
        Whether to correct the BOB heights from the measurements (default True).
    min_segment, bob_segment : float, optional
        Minimum segment length for measured / BOB-only pipes (m).
    on_progress : callable, optional
        ``on_progress(fraction, label)`` (0..1) for a stepped progress bar; errors
        in the callback are ignored.

    Returns
    -------
    dict
        A write-plan consumed by :func:`enrich_write` with keys ``validation``,
        ``profile_rows``, ``segment_rows``, ``settings``, ``enrich_fingerprint``
        and ``summary``.
    """
    def _report(frac, label):
        if on_progress is not None:
            try:
                on_progress(frac, label)
            except Exception:
                pass

    _report(0.05, "Basisdata lezen…")
    manholes = read_manholes(gpkg_path)
    pipes = read_pipes(gpkg_path)
    pipes_by_code = {p.code: p for p in pipes}
    raw = read_raw_measurements(gpkg_path)

    # 1. Validation (measured length = furthest raw point per pipe).
    _report(0.25, "Valideren…")
    measured_length = {code: max((pt["dist"] for pt in rm.points), default=0.0)
                       for code, rm in raw.items()}
    validation = rgs_ribx.validate_network(manholes, pipes, measured_length=measured_length)

    # 2. Heights -> profile points (with map geometry interpolated along the pipe).
    _report(0.50, "Hoogtes integreren…")
    profiles = rgs_ribx.integrate_profiles(pipes_by_code, raw, correct_bob=correct_bob)
    profile_rows = []
    for code, points in profiles.items():
        pipe = pipes_by_code.get(code)
        wkt = pipe.geometry_wkt if pipe else None
        for mp in points:
            profile_rows.append({
                "pipe_code": code, "dist": mp.dist, "bob": mp.bob, "obb": mp.obb,
                "geometry_wkt": point_along_wkt(wkt, mp.dist) if wkt else None,
            })

    # 3. Segments (measured aggregation, BOB fallback for the rest).
    _report(0.80, "Segmenten bouwen…")
    segment_rows = []
    for code, pipe in pipes_by_code.items():
        segs = rgs_ribx.build_segments(pipe, profiles.get(code, []),
                                       min_length=min_segment, bob_length=bob_segment)
        for seg in segs:
            geom = linestring_substring_wkt(pipe.geometry_wkt, seg["dist_from"], seg["dist_to"]) \
                if pipe.geometry_wkt else None
            segment_rows.append({**seg, "geometry_wkt": geom})

    n_pipe_issues = sum(1 for v in validation["pipes"].values() if v)
    n_manhole_issues = sum(1 for v in validation["manholes"].values() if v)
    all_issues = [i for v in validation["pipes"].values() for i in v]
    all_issues += [i for v in validation["manholes"].values() for i in v]
    n_errors = sum(1 for i in all_issues if getattr(i, "severity", "error") == "error")
    n_warnings = sum(1 for i in all_issues if getattr(i, "severity", "error") == "warning")
    summary = {
        "n_profile_points": len(profile_rows),
        "n_segments": len(segment_rows),
        "n_pipes_with_issues": n_pipe_issues,
        "n_manholes_with_issues": n_manhole_issues,
        "n_errors": n_errors,
        "n_warnings": n_warnings,
    }
    _report(1.0, "Berekend")
    return {
        "validation": validation,
        "profile_rows": profile_rows,
        "segment_rows": segment_rows,
        "settings": {"correct_bob": correct_bob, "min_segment": min_segment,
                     "bob_segment": bob_segment},
        # Fingerprint of the base data exactly as read above (before set_validation
        # touches valid/issues, which are not part of the base fingerprint).
        "enrich_fingerprint": base_fingerprint_from(pipes, raw, manholes),
        "summary": summary,
    }


def enrich_write(gpkg_path, plan, on_progress=None) -> dict:
    """Apply an :func:`enrich_compute` plan to the GeoPackage (all writes here).

    Must run on the **main thread**: writing/finalising a large GeoPackage in a
    ``QgsTask`` worker thread crashes QGIS on Windows.

    Parameters
    ----------
    gpkg_path : str or pathlib.Path
        Path to the Drainworks GeoPackage.
    plan : dict
        The write-plan returned by :func:`enrich_compute`.
    on_progress : callable, optional
        ``on_progress(fraction, label)`` (0..1) for a stepped progress bar.

    Returns
    -------
    dict
        ``plan["summary"]``.
    """
    def _report(frac, label):
        if on_progress is not None:
            try:
                on_progress(frac, label)
            except Exception:
                pass

    _report(0.05, "Validatie wegschrijven…")
    set_validation(gpkg_path, plan["validation"])
    refresh_pipe_derived(gpkg_path)
    _report(0.20, "Profiel wegschrijven…")
    write_profile(gpkg_path, plan["profile_rows"])
    _report(0.70, "Segmenten wegschrijven…")
    write_segments(gpkg_path, plan["segment_rows"])
    _report(0.95, "Afronden…")
    summary = plan["summary"]
    write_meta(gpkg_path, {
        "enrich_fingerprint": plan["enrich_fingerprint"],
        "enrich_settings": plan["settings"],
        "enrich_summary": {"n_segments": summary["n_segments"], "n_errors": summary["n_errors"],
                           "n_warnings": summary["n_warnings"]},
    })
    _report(1.0, "Klaar")
    return summary


def enrich(gpkg_path, correct_bob=True, min_segment=MIN_SEGMENT,
           bob_segment=BOB_SEGMENT, on_progress=None) -> dict:
    """Run step 2 over a GeoPackage (compute + write). Returns a summary dict.

    Convenience wrapper that chains :func:`enrich_compute` and :func:`enrich_write`
    for synchronous callers and tests. ``on_progress(fraction, label)`` (0..1), if
    given, spans both halves (compute 0..0.6, write 0.6..1.0).
    """
    def _report(frac, label):
        if on_progress is not None:
            try:
                on_progress(frac, label)
            except Exception:
                pass

    plan = enrich_compute(gpkg_path, correct_bob=correct_bob, min_segment=min_segment,
                          bob_segment=bob_segment,
                          on_progress=lambda f, l: _report(0.6 * f, l))
    return enrich_write(gpkg_path, plan, on_progress=lambda f, l: _report(0.6 + 0.4 * f, l))
