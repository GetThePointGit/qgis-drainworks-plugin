"""Unit tests for the berging aggregation math (`_aggregate`)."""

import math

import rgs_ribx
from drainworks_plugin.pipeline.berging import _aggregate


def _pt(dist, bob, obb, water=None, pct=None):
    p = rgs_ribx.MeasurementPoint(dist=dist, bob=bob, obb=obb)
    p.water_level = water
    p.flooded_pct = pct
    return p


def test_aggregate_flooded_segment():
    # Two points 10 m apart, half-full (pct 0.5), water 0.5 m above the invert.
    pts = [_pt(0.0, -2.0, -1.0, water=-1.5, pct=0.5),
           _pt(10.0, -2.0, -1.0, water=-1.5, pct=0.5)]
    out = _aggregate(pts)
    assert round(out["flooded_pct"], 3) == 0.5
    assert round(out["flooded_pct_max"], 3) == 0.5
    assert round(out["water_level"], 3) == -1.5
    assert round(out["water_depth_max"], 3) == 0.5          # -1.5 - (-2.0)
    assert out["flooded_length"] == 10.0
    # area = pct * pi * (diameter/2)^2 with diameter = obb - bob = 1.0
    area = 0.5 * math.pi * 0.5 ** 2
    assert round(out["lost_volume"], 4) == round(area * 10.0, 4)


def test_aggregate_dry_segment_is_zero():
    pts = [_pt(0.0, -2.0, -1.0), _pt(10.0, -2.0, -1.0)]
    out = _aggregate(pts)
    assert out["flooded_pct"] == 0.0
    assert out["flooded_pct_max"] == 0.0
    assert out["flooded_length"] == 0.0
    assert out["lost_volume"] == 0.0
    assert out["water_depth_max"] == 0.0
    assert out["water_level"] is None


def test_aggregate_skips_zero_length_spans():
    # Duplicate distance -> zero-length span must not divide by zero / inflate totals.
    pts = [_pt(0.0, -2.0, -1.0, water=-1.5, pct=0.4),
           _pt(0.0, -2.0, -1.0, water=-1.5, pct=0.4),
           _pt(5.0, -2.0, -1.0, water=-1.5, pct=0.4)]
    out = _aggregate(pts)
    assert out["flooded_length"] == 5.0
    assert round(out["flooded_pct"], 3) == 0.4
