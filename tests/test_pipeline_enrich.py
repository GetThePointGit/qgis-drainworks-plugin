from drainworks_plugin.io.geopackage_store import (
    read_profile,
    read_segments,
    write_base,
)
from drainworks_plugin.pipeline.enrich import enrich

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
