from drainworks_plugin.io.geopackage_store import (
    read_profile,
    read_segments,
    update_segments_berging,
    write_base,
    write_profile,
    write_segments,
)

import rgs_ribx


def _gpkg(tmp_gpkg):
    manholes = [rgs_ribx.Manhole(code="A", geometry_wkt="POINT (0 0)")]
    pipes = [rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="B", bob1=-2.0, bob2=-2.6,
                           diameter=0.3, length=30.0, geometry_wkt="LINESTRING (0 0, 30 0)")]
    write_base(tmp_gpkg, manholes, pipes, raw_measurements={})
    return tmp_gpkg


def test_profile_roundtrip(tmp_gpkg):
    _gpkg(tmp_gpkg)
    rows = [
        {"pipe_code": "L1", "dist": 0.0, "bob": -2.0, "obb": -1.7, "geometry_wkt": "POINT (0 0)"},
        {"pipe_code": "L1", "dist": 30.0, "bob": -2.6, "obb": -2.3, "geometry_wkt": "POINT (30 0)"},
    ]
    assert write_profile(tmp_gpkg, rows) == 2
    got = read_profile(tmp_gpkg)
    assert [round(p.dist, 1) for p in got["L1"]] == [0.0, 30.0]
    assert got["L1"][0].obb == -1.7


def test_segments_roundtrip_and_berging_update(tmp_gpkg):
    _gpkg(tmp_gpkg)
    rows = [{
        "pipe_code": "L1", "dist_from": 0.0, "dist_to": 15.0, "length": 15.0,
        "bob_start": -2.0, "bob_end": -2.3, "bob_highest": -2.0, "slope_avg": -0.02,
        "diameter": 0.3, "n_measurements": 2, "source": "measured",
        "geometry_wkt": "LINESTRING (0 0, 15 0)",
    }]
    assert write_segments(tmp_gpkg, rows) == 1
    segs = read_segments(tmp_gpkg)
    assert len(segs) == 1
    seg = segs[0]
    assert seg["pipe_code"] == "L1" and seg["source"] == "measured"
    assert "fid" in seg

    update_segments_berging(tmp_gpkg, {seg["fid"]: {
        "water_level": -2.1, "flooded_pct": 0.4, "lost_volume": 0.5,
        "flooded_length": 10.0, "flooded_pct_max": 0.6}})
    seg2 = read_segments(tmp_gpkg)[0]
    assert round(seg2["flooded_pct"], 2) == 0.4
    assert round(seg2["flooded_pct_max"], 2) == 0.6
