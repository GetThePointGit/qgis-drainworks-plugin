from drainworks_plugin.io.geopackage_store import read_segments, write_base
from drainworks_plugin.pipeline.tasks import BergingTask, EnrichTask, ImportTask

import rgs_ribx
from rgs_ribx.model.raw import RawMeasurements


def test_import_task_parses_without_writing(fixtures_dir, tmp_gpkg):
    # The import task only PARSES (off-thread); the GeoPackage write happens later on
    # the main thread, so no file is written by task.run() itself.
    task = ImportTask(str(fixtures_dir / "inclined.ribx"), None, str(tmp_gpkg))
    assert task.run() is True
    assert task.result is not None and task.result.pipes      # parsed BuildResult
    assert task.gpkg_path == str(tmp_gpkg)
    assert not tmp_gpkg.exists()                              # no write in the worker


def _base(tmp_gpkg):
    manholes = [rgs_ribx.Manhole(code="P1", is_sink=True, geometry_wkt="POINT (0 0)"),
                rgs_ribx.Manhole(code="P2", is_sink=True, geometry_wkt="POINT (30 0)")]
    pipes = [rgs_ribx.Pipe(code="L1", manhole1="P1", manhole2="P2", bob1=-2.0, bob2=-2.0,
                           diameter=0.5, length=30.0, shape="A",
                           geometry_wkt="LINESTRING (0 0, 30 0)")]
    raw = {"L1": RawMeasurements("L1", "AA", reverse=False, points=[
        {"dist": 0.0, "value": 0.0}, {"dist": 10.0, "value": -0.3},
        {"dist": 20.0, "value": -0.3}, {"dist": 30.0, "value": 0.0}])}
    write_base(tmp_gpkg, manholes, pipes, raw)


def test_enrich_task_run_builds_segments(tmp_gpkg):
    _base(tmp_gpkg)
    task = EnrichTask(str(tmp_gpkg), correct_bob=False)
    assert task.run() is True
    assert task.result is not None and task.result["n_segments"] >= 1
    assert read_segments(str(tmp_gpkg))


def test_berging_task_run_fills_segments(tmp_gpkg):
    _base(tmp_gpkg)
    assert EnrichTask(str(tmp_gpkg), correct_bob=False).run() is True
    task = BergingTask(str(tmp_gpkg), resolution="accurate")
    assert task.run() is True
    assert any((s.get("flooded_pct") or 0) > 0 for s in read_segments(str(tmp_gpkg)))


def test_task_run_captures_error(tmp_gpkg):
    task = EnrichTask(str(tmp_gpkg) + ".missing", correct_bob=False)
    assert task.run() is False
    assert task.error is not None
