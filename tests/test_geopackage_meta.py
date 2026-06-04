from drainworks_plugin.io.geopackage_store import (
    base_fingerprint,
    berging_fingerprint,
    read_meta,
    write_base,
    write_meta,
)

import rgs_ribx
from rgs_ribx.model.raw import RawMeasurements


def _base(tmp_gpkg, bob2=-2.6):
    manholes = [rgs_ribx.Manhole(code="A", geometry_wkt="POINT (0 0)", ground_level=0.2),
                rgs_ribx.Manhole(code="B", geometry_wkt="POINT (30 0)", ground_level=0.1)]
    pipes = [rgs_ribx.Pipe(code="L1", manhole1="A", manhole2="B", bob1=-2.0, bob2=bob2,
                           diameter=0.3, length=30.0, geometry_wkt="LINESTRING (0 0, 30 0)")]
    raw = {"L1": RawMeasurements("L1", "AA", reverse=False,
                                 points=[{"dist": 0.0, "value": 0.0}])}
    write_base(tmp_gpkg, manholes, pipes, raw)


def test_fingerprint_stable_and_changes_on_bob_edit(tmp_gpkg, tmp_path):
    _base(tmp_gpkg)
    fp1 = base_fingerprint(tmp_gpkg)
    assert fp1 == base_fingerprint(tmp_gpkg)        # stable
    other = tmp_path / "other.gpkg"
    _base(other, bob2=-3.0)
    assert base_fingerprint(other) != fp1           # a BOB change changes it


def test_berging_fingerprint_depends_on_sinks():
    assert berging_fingerprint("fp", ["A"]) == berging_fingerprint("fp", ["A"])
    assert berging_fingerprint("fp", ["A"]) != berging_fingerprint("fp", ["A", "B"])


def test_meta_roundtrip_and_merge(tmp_gpkg):
    _base(tmp_gpkg)
    assert read_meta(tmp_gpkg) == {}
    write_meta(tmp_gpkg, {"a": 1, "b": {"x": 2}})
    write_meta(tmp_gpkg, {"b": {"x": 3}, "c": [1, 2]})   # merge/replace
    assert read_meta(tmp_gpkg) == {"a": 1, "b": {"x": 3}, "c": [1, 2]}
