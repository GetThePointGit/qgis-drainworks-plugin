#!/usr/bin/env python3
"""Generate an example GeoPackage: 10 manholes in a 5x2 grid for routing tests.

Manholes P01..P10 sit on a 5-column, 2-row grid (EPSG:28992, 40 m spacing) and
are connected horizontally and vertically by pipes, so the network has loops and
multiple shortest-path options. The inverts slope down to the lowest corner
(P10), which is flagged as the sink. One pipe is given a sagging interior
profile so "verloren berging" has something to show.

Run with the QGIS-LTR2 Python and the PROJ/GDAL env (so EPSG:28992 resolves):

    export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3"
    export PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj"
    export PROJ_DATA="$PROJ_LIB"
    export GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal"
    export PYTHONPATH="$PWD:$HOME/Documents/GitHub/rgs-ribx/src"
    "$QGIS_PY" scripts/make_example_grid.py
"""

import os
import sys

# Make the plugin package + rgs_ribx importable when run directly.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.expanduser("~/Documents/GitHub/rgs-ribx/src"))

import rgs_ribx
from rgs_ribx.model.geometry import wkt_linestring_length

from drainworks_plugin.io.geopackage_store import MeasurementRow, write_geopackage

COLS, ROWS = 5, 2
X0, Y0, STEP = 100000.0, 400000.0, 40.0
DIAMETER = 0.3


def code(col, row):
    return f"P{row * COLS + col + 1:02d}"


def position(col, row):
    return (X0 + col * STEP, Y0 + row * STEP)


def invert(col, row):
    # Slope down towards the far corner (col=4, row=1) so P10 is the low point.
    return -2.0 - (col * 0.20 + row * 0.10)


def build():
    manholes = []
    coords = {}
    inverts = {}
    sink_code = code(COLS - 1, ROWS - 1)  # P10
    for row in range(ROWS):
        for col in range(COLS):
            c = code(col, row)
            x, y = position(col, row)
            coords[c] = (x, y)
            inverts[c] = invert(col, row)
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
    n = 0

    def add_pipe(a, b):
        nonlocal n
        n += 1
        (xa, ya), (xb, yb) = coords[a], coords[b]
        wkt = f"LINESTRING ({xa:.3f} {ya:.3f}, {xb:.3f} {yb:.3f})"
        pipes.append(
            rgs_ribx.Pipe(
                code=f"L{n:02d}",
                manhole1=a,
                manhole2=b,
                geometry_wkt=wkt,
                shape="A",
                diameter=DIAMETER,
                bob1=inverts[a],
                bob2=inverts[b],
                length=wkt_linestring_length(wkt),
            )
        )
        return pipes[-1]

    # Horizontal connections.
    for row in range(ROWS):
        for col in range(COLS - 1):
            add_pipe(code(col, row), code(col + 1, row))
    # Vertical connections.
    for col in range(COLS):
        for row in range(ROWS - 1):
            add_pipe(code(col, row), code(col, row + 1))

    # Give the first horizontal pipe (L01) a sagging interior profile so the
    # midpoint floods (verloren berging > 0).
    dip_pipe = pipes[0]
    b1, b2 = dip_pipe.bob1, dip_pipe.bob2
    measurements = [
        MeasurementRow(pipe_code=dip_pipe.code, dist=10.0, bob=min(b1, b2) - 0.10, obb=min(b1, b2) - 0.10 + DIAMETER),
        MeasurementRow(pipe_code=dip_pipe.code, dist=20.0, bob=min(b1, b2) - 0.18, obb=min(b1, b2) - 0.18 + DIAMETER),
        MeasurementRow(pipe_code=dip_pipe.code, dist=30.0, bob=min(b1, b2) - 0.10, obb=min(b1, b2) - 0.10 + DIAMETER),
    ]
    return manholes, pipes, measurements, sink_code


def main():
    manholes, pipes, measurements, sink_code = build()
    out = os.path.join(REPO, "example", "grid10.gpkg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_geopackage(out, manholes, pipes, measurements)
    print(f"Wrote {out}")
    print(f"  {len(manholes)} manholes (sink: {sink_code}), {len(pipes)} pipes, "
          f"{len(measurements)} measurement points on {pipes[0].code}")


if __name__ == "__main__":
    main()
