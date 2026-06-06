"""Shore-point insertion for the side-view water fill (issues: sloped water, zigzag)."""

import pytest

from drainworks_plugin.sideview.sideview_widget import _shoreline_curves


def test_flat_pool_unchanged():
    # Whole stretch under water at a constant level -> surface stays flat, no shores.
    dists = [0.0, 1.0, 2.0]
    bobs = [-1.0, -1.2, -1.1]
    waters = [-0.5, -0.5, -0.5]
    xs, bb, ww, wet = _shoreline_curves(dists, bobs, waters)
    assert xs == pytest.approx(dists)
    assert ww == pytest.approx(waters)          # flat surface preserved
    assert all(wet)
    assert all(w >= b for b, w in zip(bb, ww))


def test_shore_inserted_at_pool_level_not_dry_invert():
    # Pool level 0 at the wet end; the invert rises -1 -> +1, crossing 0 at the midpoint.
    # A shore must appear at x=1.0 at level 0 (flat surface), NOT slope to the dry invert.
    dists = [0.0, 2.0]
    bobs = [-1.0, 1.0]
    waters = [0.0, 1.0]   # wet (depth 1) then dry (water == invert)
    xs, bb, ww, wet = _shoreline_curves(dists, bobs, waters)

    # shore vertex at x≈1.0, surface level 0
    shore = [(x, w, f) for x, w, f in zip(xs, ww, wet) if abs(x - 1.0) < 1e-6]
    assert shore and abs(shore[0][1] - 0.0) < 1e-9 and shore[0][2] is True
    # surface never above invert, and the dry end carries no water line
    assert all(w >= b - 1e-9 for b, w in zip(bb, ww))
    assert wet[-1] is False                      # dry end -> no surface line


def test_two_pools_separated_by_a_peak():
    # Two sags below water level 0, separated by a peak above it -> two pools, the dashed
    # surface line must break (wet, dry, wet).
    dists = [0.0, 1.0, 2.0, 3.0, 4.0]
    bobs = [-1.0, 0.5, -1.0, 0.5, -1.0]    # sag, peak, sag, peak, sag
    waters = [0.0, 0.5, 0.0, 0.5, 0.0]     # wet, dry(peak), wet, dry(peak), wet
    xs, bb, ww, wet = _shoreline_curves(dists, bobs, waters)
    # the peaks are dry
    assert any((not f) for f in wet)
    # there are wet stretches on both sides of a dry one
    assert wet[0] and wet[-1]
