#!/usr/bin/env python3
"""Generate an example GeoPackage of manholes in a grid for routing/berging tests.

Manholes sit on a COLS x ROWS grid (EPSG:28992) connected horizontally and
vertically, so the network has loops and multiple shortest paths. Two terrains:

- default slope: inverts fall to the far corner (the sink); the first pipe gets
  a measured sag so "verloren berging" has something to show.
- ``--basin``: a gentle plane plus a central depression, so water pools in the
  basin (lost storage) even without measured points — exercising the BOB
  fallback. No measurements are written.

Run with the QGIS-LTR2 Python and the PROJ/GDAL env (so EPSG:28992 resolves):

    export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3"
    export PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj"
    export PROJ_DATA="$PROJ_LIB"
    export GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal"
    export PYTHONPATH="$PWD:$HOME/Documents/GitHub/rgs-ribx/src"
    "$QGIS_PY" scripts/make_example_grid.py                       # small 5x2
    "$QGIS_PY" scripts/make_example_grid.py --cols 12 --rows 8 --basin \
        --out example/grid_large.gpkg
"""

import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.expanduser("~/Documents/GitHub/rgs-ribx/src"))

import rgs_ribx
from rgs_ribx.model.geometry import wkt_linestring_length

from drainworks_plugin.io.geopackage_store import MeasurementRow, write_geopackage

X0, Y0 = 100000.0, 400000.0
DIAMETER = 0.3


def code(col, row, cols):
    return f"P{row * cols + col + 1:02d}"


def invert(col, row, cols, rows, basin):
    if not basin:
        return -2.0 - (col * 0.20 + row * 0.10)
    plane = -2.0 - 0.04 * col - 0.03 * row
    cx, cy = (cols - 1) * 0.45, (rows - 1) * 0.5
    sx, sy = max(cols / 4.0, 1.0), max(rows / 4.0, 1.0)
    gauss = math.exp(-(((col - cx) / sx) ** 2 + ((row - cy) / sy) ** 2))
    return plane - 0.8 * gauss


def build(cols, rows, spacing, basin):
    coords, inverts = {}, {}
    manholes = []
    sink_code = code(cols - 1, rows - 1, cols)
    for row in range(rows):
        for col in range(cols):
            c = code(col, row, cols)
            x, y = X0 + col * spacing, Y0 + row * spacing
            coords[c] = (x, y)
            inverts[c] = invert(col, row, cols, rows, basin)
            manholes.append(
                rgs_ribx.Manhole(
                    code=c,
                    geometry_wkt=f"POINT ({x:.3f} {y:.3f})",
                    node_type="put",
                    ground_level=0.0,
                    is_sink=(c == sink_code),
                )
            )

    pipes = []

    def add_pipe(a, b):
        (xa, ya), (xb, yb) = coords[a], coords[b]
        wkt = f"LINESTRING ({xa:.3f} {ya:.3f}, {xb:.3f} {yb:.3f})"
        pipes.append(
            rgs_ribx.Pipe(
                code=f"L{len(pipes) + 1:03d}", manhole1=a, manhole2=b, geometry_wkt=wkt,
                shape="A", diameter=DIAMETER, bob1=inverts[a], bob2=inverts[b],
                length=wkt_linestring_length(wkt),
            )
        )

    for row in range(rows):
        for col in range(cols - 1):
            add_pipe(code(col, row, cols), code(col + 1, row, cols))
    for col in range(cols):
        for row in range(rows - 1):
            add_pipe(code(col, row, cols), code(col, row + 1, cols))

    measurements = []
    if not basin:
        dip = pipes[0]
        low = min(dip.bob1, dip.bob2)
        measurements = [
            MeasurementRow(pipe_code=dip.code, dist=10.0, bob=low - 0.10, obb=low - 0.10 + DIAMETER),
            MeasurementRow(pipe_code=dip.code, dist=20.0, bob=low - 0.18, obb=low - 0.18 + DIAMETER),
            MeasurementRow(pipe_code=dip.code, dist=30.0, bob=low - 0.10, obb=low - 0.10 + DIAMETER),
        ]
    return manholes, pipes, measurements, sink_code


def main():
    parser = argparse.ArgumentParser(description="Generate a grid example GeoPackage.")
    parser.add_argument("--cols", type=int, default=5)
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--spacing", type=float, default=40.0)
    parser.add_argument("--basin", action="store_true", help="central depression (pooling)")
    parser.add_argument("--out", default=os.path.join(REPO, "example", "grid10.gpkg"))
    args = parser.parse_args()

    manholes, pipes, measurements, sink_code = build(args.cols, args.rows, args.spacing, args.basin)
    out = args.out if os.path.isabs(args.out) else os.path.join(REPO, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_geopackage(out, manholes, pipes, measurements)
    print(f"Wrote {out}")
    print(f"  {len(manholes)} manholes (sink: {sink_code}), {len(pipes)} pipes, "
          f"{len(measurements)} measured points, terrain={'basin' if args.basin else 'slope'}")


if __name__ == "__main__":
    main()
