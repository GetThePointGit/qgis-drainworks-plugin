"""Headless smoke test of the 3-step pipeline via the QgsTask wrappers.

Mirrors the real plugin flow: each task only COMPUTES off-thread; the GeoPackage
write half then runs on the main thread (writing/finalising a large GeoPackage in a
worker thread crashes QGIS on Windows).

Run with the QGIS-LTR2 python and the PROJ/GDAL env (see the plan header).
Usage: python -u scripts/smoke_pipeline.py path/to/input.ribx /tmp/out.gpkg
"""

import sys

from drainworks_plugin.io.geopackage_store import read_segments
from drainworks_plugin.io.import_controller import write_base_from_result
from drainworks_plugin.pipeline.berging import berging_write
from drainworks_plugin.pipeline.enrich import enrich_write
from drainworks_plugin.pipeline.tasks import BergingTask, EnrichTask, ImportTask


def main(input_path, gpkg_path):
    t1 = ImportTask(input_path, None, gpkg_path)
    assert t1.run(), f"import failed: {t1.error}"
    write_base_from_result(gpkg_path, t1.result)        # main-thread write
    print("imported", flush=True)

    t2 = EnrichTask(gpkg_path, correct_bob=True)
    assert t2.run(), f"enrich failed: {t2.error}"
    summary = enrich_write(gpkg_path, t2.result)        # main-thread write
    print("enriched ->", summary, flush=True)

    t3 = BergingTask(gpkg_path, resolution="accurate")
    assert t3.run(), f"berging failed: {t3.error}"
    n = berging_write(gpkg_path, t3.result)             # main-thread write
    segs = read_segments(gpkg_path)
    flooded = [s for s in segs if (s.get("flooded_pct") or 0) > 0]
    print(f"berging -> {n} segments, {len(flooded)} flooded", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
