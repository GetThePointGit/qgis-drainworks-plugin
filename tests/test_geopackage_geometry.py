"""Tests for the pure WKT geometry helpers in geopackage_store."""

from drainworks_plugin.io.geopackage_store import (
    linestring_substring_wkt,
    point_along_wkt,
)


def test_point_along_wkt_interpolates_and_clamps():
    line = "LINESTRING (0 0, 10 0, 10 10)"   # total length 20
    assert point_along_wkt(line, 5) == "POINT (5.000 0.000)"
    assert point_along_wkt(line, 15) == "POINT (10.000 5.000)"
    # distance beyond the line clamps to the last vertex
    assert point_along_wkt(line, 100) == "POINT (10.000 10.000)"
    assert point_along_wkt(line, 0) == "POINT (0.000 0.000)"


def test_point_along_wkt_bad_input_returns_none():
    assert point_along_wkt("POINT (0 0)", 5) is None
    assert point_along_wkt("LINESTRING (0 0)", 5) is None        # < 2 vertices
    assert point_along_wkt(None, 5) is None


def test_linestring_substring_keeps_interior_vertices():
    line = "LINESTRING (0 0, 10 0, 10 10)"
    sub = linestring_substring_wkt(line, 5, 15)
    assert sub.startswith("LINESTRING")
    # from (5,0) over the corner (10,0) to (10,5)
    assert "5.000 0.000" in sub
    assert "10.000 0.000" in sub
    assert "10.000 5.000" in sub


def test_linestring_substring_bad_input_returns_none():
    assert linestring_substring_wkt("LINESTRING (0 0, 10 0)", 5, 5) is None   # d1 <= d0
    assert linestring_substring_wkt("POINT (0 0)", 0, 5) is None
