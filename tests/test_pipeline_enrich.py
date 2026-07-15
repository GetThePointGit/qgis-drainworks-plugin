from drainworks_plugin.io.geopackage_store import (
    read_profile,
    read_segments,
    write_base,
)
from drainworks_plugin.pipeline.enrich import enrich

import pytest
import rgs_ribx


def test_enrich_builds_profile_and_segments(fixtures_dir, tmp_gpkg):
    res = rgs_ribx.build_from_ribx(fixtures_dir / "inclined.ribx")
    write_base(tmp_gpkg, res.manholes, res.pipes, res.raw_measurements)

    summary = enrich(tmp_gpkg, correct_bob=True)

    profile = read_profile(tmp_gpkg)
    assert "L001" in profile and len(profile["L001"]) >= 2

    segs = read_segments(tmp_gpkg)
    assert segs and all(s["pipe_code"] == "L001" for s in segs)
    assert all(s["source"] == "measured" for s in segs)
    assert all(s.get("flooded_pct") in (None, 0, 0.0) for s in segs)

    assert summary["n_segments"] == len(segs)
    assert "n_pipes_with_issues" in summary


def test_enrich_rerun_reflects_edited_bob(fixtures_dir, tmp_gpkg):
    res = rgs_ribx.build_from_ribx(fixtures_dir / "inclined.ribx")
    write_base(tmp_gpkg, res.manholes, res.pipes, res.raw_measurements)
    enrich(tmp_gpkg, correct_bob=True)
    first_end = read_profile(tmp_gpkg)["L001"][-1].bob

    from osgeo import ogr
    ds = ogr.Open(str(tmp_gpkg), update=1)
    layer = ds.GetLayerByName("pipes")
    feat = layer.GetNextFeature()
    feat.SetField("bob2", feat.GetField("bob2") - 1.0)
    layer.SetFeature(feat)
    ds = None

    enrich(tmp_gpkg, correct_bob=True)
    second_end = read_profile(tmp_gpkg)["L001"][-1].bob
    assert round(second_end - first_end, 2) == -1.0


def test_enrich_rerun_recomputes_bob_avg_and_slope(fixtures_dir, tmp_gpkg):
    res = rgs_ribx.build_from_ribx(fixtures_dir / "inclined.ribx")
    write_base(tmp_gpkg, res.manholes, res.pipes, res.raw_measurements)
    enrich(tmp_gpkg, correct_bob=True)

    from osgeo import ogr
    ds = ogr.Open(str(tmp_gpkg), update=1)
    layer = ds.GetLayerByName("pipes")
    feat = layer.GetNextFeature()
    bob1 = feat.GetField("bob1")
    bob2 = feat.GetField("bob2") - 1.0
    length = feat.GetField("length")
    feat.SetField("bob2", bob2)
    layer.SetFeature(feat)
    ds = None

    enrich(tmp_gpkg, correct_bob=True)

    ds = ogr.Open(str(tmp_gpkg))
    feat = ds.GetLayerByName("pipes").GetNextFeature()
    assert feat.GetField("bob_avg") == pytest.approx((bob1 + bob2) / 2.0)
    assert feat.GetField("slope") == pytest.approx(abs(bob1 - bob2) / length)


def test_enrich_summary_counts_errors_and_warnings(tmp_gpkg):
    from drainworks_plugin.io.geopackage_store import write_base
    from drainworks_plugin.pipeline.enrich import enrich
    import rgs_ribx

    manholes = [rgs_ribx.Manhole(code="A", geometry_wkt="POINT (0 0)")]
    pipes = [
        rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="Z", bob1=-2.0, bob2=None,
                      diameter=5.0, length=30.0, geometry_wkt="LINESTRING (0 0, 30 0)"),
    ]
    write_base(tmp_gpkg, manholes, pipes, raw_measurements={})
    summary = enrich(tmp_gpkg, correct_bob=False)
    # missing bob2 + dangling manhole2 -> errors ; diameter 5000 mm -> warning
    assert summary["n_errors"] >= 2
    assert summary["n_warnings"] >= 1


def test_enrich_writes_meta(fixtures_dir, tmp_gpkg):
    import rgs_ribx
    from drainworks_plugin.io.geopackage_store import base_fingerprint, read_meta, write_base
    from drainworks_plugin.pipeline.enrich import enrich

    res = rgs_ribx.build_from_ribx(fixtures_dir / "inclined.ribx")
    write_base(tmp_gpkg, res.manholes, res.pipes, res.raw_measurements)
    enrich(tmp_gpkg, correct_bob=True, min_segment=2.0, bob_segment=4.0)
    meta = read_meta(tmp_gpkg)
    assert meta["enrich_fingerprint"] == base_fingerprint(tmp_gpkg)
    assert meta["enrich_settings"] == {"correct_bob": True, "min_segment": 2.0, "bob_segment": 4.0}
    assert "n_segments" in meta["enrich_summary"]
