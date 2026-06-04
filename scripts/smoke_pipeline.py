"""Headless smoke test of the 3-step pipeline via the QgsTask wrappers.

Run with the QGIS-LTR2 python and the PROJ/GDAL env (see the plan header).
Usage: python -u scripts/smoke_pipeline.py path/to/input.ribx /tmp/out.gpkg
"""

import sys

from drainworks_plugin.pipeline.tasks import BergingTask, EnrichTask, ImportTask
from drainworks_plugin.io.geopackage_store import read_segments


def main(input_path, gpkg_path):
    t1 = ImportTask(input_path, None, gpkg_path)
    assert t1.run(), f"import failed: {t1.error}"
    print("imported ->", t1.result, flush=True)

    t2 = EnrichTask(gpkg_path, correct_bob=True)
    assert t2.run(), f"enrich failed: {t2.error}"
    print("enriched ->", t2.result, flush=True)

    t3 = BergingTask(gpkg_path, resolution="accurate")
    assert t3.run(), f"berging failed: {t3.error}"
    segs = read_segments(gpkg_path)
    flooded = [s for s in segs if (s.get("flooded_pct") or 0) > 0]
    print(f"berging -> {t3.result} segments, {len(flooded)} flooded", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
