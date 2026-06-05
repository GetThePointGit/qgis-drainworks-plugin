"""Step 2 — enrich base data: validate, integrate heights, build segments.

Reads the (possibly edited) ``manholes``/``pipes``/``measurements_raw`` from the
GeoPackage and writes ``profile`` + ``segments``, plus ``valid``/``issues`` on the
base layers. Any previously computed berging is wiped (segments are recreated
empty); step 3 fills them.
"""

import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    linestring_substring_wkt,
    point_along_wkt,
    read_manholes,
    read_pipes,
    read_raw_measurements,
    set_validation,
    write_profile,
    write_segments,
)

# Defaults (configurable via the dock in Plan C).
MIN_SEGMENT = 1.0   # m, measured pipes
BOB_SEGMENT = 5.0   # m, pipes without measurements


def enrich(gpkg_path, correct_bob=True, min_segment=MIN_SEGMENT,
           bob_segment=BOB_SEGMENT, on_progress=None) -> dict:
    """Run step 2 over a GeoPackage. Returns a summary dict.

    ``on_progress(fraction, label)`` (0..1), if given, is called at each stage
    (read / validate / integrate / write profile / build segments / write) so the
    caller can show a stepped progress bar. Errors in the callback are ignored.
    """
    def _report(frac, label):
        if on_progress is not None:
            try:
                on_progress(frac, label)
            except Exception:
                pass

    _report(0.03, "Basisdata lezen…")
    manholes = read_manholes(gpkg_path)
    pipes = read_pipes(gpkg_path)
    pipes_by_code = {p.code: p for p in pipes}
    raw = read_raw_measurements(gpkg_path)

    # 1. Validation (measured length = furthest raw point per pipe).
    _report(0.15, "Valideren…")
    measured_length = {code: max((pt["dist"] for pt in rm.points), default=0.0)
                       for code, rm in raw.items()}
    validation = rgs_ribx.validate_network(manholes, pipes, measured_length=measured_length)
    set_validation(gpkg_path, validation)

    # 2. Heights -> profile points (with map geometry interpolated along the pipe).
    _report(0.30, "Hoogtes integreren…")
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
    _report(0.50, "Profiel wegschrijven…")
    write_profile(gpkg_path, profile_rows)

    # 3. Segments (measured aggregation, BOB fallback for the rest).
    _report(0.65, "Segmenten bouwen…")
    segment_rows = []
    for code, pipe in pipes_by_code.items():
        segs = rgs_ribx.build_segments(pipe, profiles.get(code, []),
                                       min_length=min_segment, bob_length=bob_segment)
        for seg in segs:
            geom = linestring_substring_wkt(pipe.geometry_wkt, seg["dist_from"], seg["dist_to"]) \
                if pipe.geometry_wkt else None
            segment_rows.append({**seg, "geometry_wkt": geom})
    _report(0.85, "Segmenten wegschrijven…")
    write_segments(gpkg_path, segment_rows)

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
    _report(0.95, "Afronden…")
    from drainworks_plugin.io.geopackage_store import base_fingerprint_from, write_meta
    write_meta(gpkg_path, {
        # Reuse the base data already read above instead of re-reading the gpkg.
        "enrich_fingerprint": base_fingerprint_from(pipes, raw, manholes),
        "enrich_settings": {"correct_bob": correct_bob, "min_segment": min_segment,
                            "bob_segment": bob_segment},
        "enrich_summary": {"n_segments": summary["n_segments"], "n_errors": summary["n_errors"],
                           "n_warnings": summary["n_warnings"]},
    })
    _report(1.0, "Klaar")
    return summary
