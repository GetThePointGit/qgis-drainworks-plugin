import pytest

import rgs_ribx

from drainworks_plugin.sideview.profile_builder import (
    build_profile,
    dist_in_spans,
    live_pipe_spans,
    strip_preview_water,
)
from drainworks_plugin.trajectory.network import Path


def _pipe(code, a, b, bob_a, bob_b, length, diameter=0.3):
    return rgs_ribx.Pipe(code=code, manhole1=a, manhole2=b,
                         bob1=bob_a, bob2=bob_b, length=length, diameter=diameter, shape="A")


def test_profile_orientation_and_cumulative_distance():
    pipes = {
        "L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-2.4, length=20.0),
        "L2": _pipe("L2", "P2", "P3", bob_a=-2.4, bob_b=-2.8, length=20.0),
    }
    path = Path(manholes=["P1", "P2", "P3"], pipe_codes=["L1", "L2"], total_length=40.0)

    profile = build_profile(path, pipes, observations_by_pipe={})

    dists = [v.dist for v in profile.vertices]
    assert dists == pytest.approx([0.0, 20.0, 20.0, 40.0])
    bobs = [v.bob for v in profile.vertices]
    assert bobs == pytest.approx([-2.0, -2.4, -2.4, -2.8])
    assert profile.vertices[0].obb == pytest.approx(-1.7)
    assert [b for _, b in profile.ideal] == pytest.approx([-2.0, -2.4, -2.4, -2.8])


def test_profile_flips_pipe_when_traversed_backwards():
    pipes = {"L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-2.4, length=20.0)}
    path = Path(manholes=["P2", "P1"], pipe_codes=["L1"], total_length=20.0)

    profile = build_profile(path, pipes, observations_by_pipe={})
    bobs = [v.bob for v in profile.vertices]
    assert bobs == pytest.approx([-2.4, -2.0])


def test_observations_placed_at_cumulative_distance():
    pipes = {
        "L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-2.4, length=20.0),
        "L2": _pipe("L2", "P2", "P3", bob_a=-2.4, bob_b=-2.8, length=20.0),
    }
    path = Path(manholes=["P1", "P2", "P3"], pipe_codes=["L1", "L2"], total_length=40.0)
    obs = rgs_ribx.Observation(object_code="L2", code="BCA", distance=5.0)

    profile = build_profile(path, pipes, observations_by_pipe={"L2": [obs]})

    assert len(profile.observations) == 1
    marker = profile.observations[0]
    assert marker.dist == pytest.approx(25.0)
    assert marker.code == "BCA"


def test_partial_measurements_anchored_to_pipe_ends():
    # Inspection covers only 30..38 m of a 40 m pipe; the profile must still start at
    # the pipe's bob1 (0 m) and end at bob2 (40 m) so it doesn't draw across the gap.
    pipes = {"L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-3.0, length=40.0)}
    path = Path(manholes=["P1", "P2"], pipe_codes=["L1"], total_length=40.0)
    measured = [{"dist": 30.0, "bob": -2.7, "obb": -2.4},
                {"dist": 38.0, "bob": -2.9, "obb": -2.6}]

    profile = build_profile(path, pipes, measurements_by_pipe={"L1": measured})

    dists = [v.dist for v in profile.vertices]
    assert dists[0] == pytest.approx(0.0)
    assert dists[-1] == pytest.approx(40.0)
    assert profile.vertices[0].bob == pytest.approx(-2.0)    # bob1 anchor
    assert profile.vertices[-1].bob == pytest.approx(-3.0)   # bob2 anchor
    assert any(v.dist == pytest.approx(30.0) for v in profile.vertices)


def test_partial_measurement_anchors_inherit_adjacent_water_level():
    # Anchors at the pipe ends carry the adjacent measured water level, so a pool can
    # extend (flat, clipped to the invert) to the pipe end instead of stopping short.
    pipes = {"L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-3.0, length=40.0)}
    path = Path(manholes=["P1", "P2"], pipe_codes=["L1"], total_length=40.0)
    measured = [{"dist": 30.0, "bob": -2.7, "obb": -2.4, "water_level": -2.5},
                {"dist": 38.0, "bob": -2.9, "obb": -2.6, "water_level": -2.6}]

    profile = build_profile(path, pipes, measurements_by_pipe={"L1": measured})

    assert profile.vertices[0].water_level == pytest.approx(-2.5)   # start anchor
    assert profile.vertices[-1].water_level == pytest.approx(-2.6)  # end anchor


def test_full_measurements_not_double_anchored():
    # Measurements already reach both ends -> no extra anchor vertices.
    pipes = {"L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-3.0, length=40.0)}
    path = Path(manholes=["P1", "P2"], pipe_codes=["L1"], total_length=40.0)
    measured = [{"dist": 0.0, "bob": -2.0, "obb": -1.7},
                {"dist": 40.0, "bob": -3.0, "obb": -2.7}]

    profile = build_profile(path, pipes, measurements_by_pipe={"L1": measured})

    assert [v.dist for v in profile.vertices] == pytest.approx([0.0, 40.0])


def test_build_profile_emits_manhole_levels_with_ground():
    pipes = {
        "L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-2.6, length=30.0),
    }
    path = Path(manholes=["P1", "P2"], pipe_codes=["L1"], total_length=30.0)
    manholes = {
        "P1": rgs_ribx.Manhole(code="P1", ground_level=0.2),
        "P2": rgs_ribx.Manhole(code="P2", ground_level=0.1),
    }

    profile = build_profile(path, pipes, manholes_by_code=manholes)

    levels = {code: (bottom, ground) for (_d, code, bottom, ground) in profile.manhole_levels}
    assert levels["P1"][1] == 0.2
    assert levels["P2"][1] == 0.1
    assert round(levels["P1"][0], 1) == -2.0
    assert round(levels["P2"][0], 1) == -2.6


def test_live_pipe_spans_marks_only_preview_pipes():
    pipes = {
        "L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-2.5, length=10.0),
        "L2": _pipe("L2", "P2", "P3", bob_a=-2.5, bob_b=-3.0, length=10.0),
    }
    route = Path(manholes=["P1", "P2", "P3"], pipe_codes=["L1", "L2"], total_length=20.0)
    # L1 is committed, L2 is the live (preview-only) pipe.
    spans = live_pipe_spans(route, pipes, committed_codes={"L1"})
    assert spans == [(10.0, 20.0)]
    assert dist_in_spans(15.0, spans)
    assert dist_in_spans(10.0, spans)        # the junction boundary counts as live
    assert not dist_in_spans(9.0, spans)


def test_strip_preview_water_clears_water_on_live_span_and_boundary():
    pipes = {
        "L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-2.5, length=10.0),
        "L2": _pipe("L2", "P2", "P3", bob_a=-2.5, bob_b=-3.0, length=10.0),
    }
    route = Path(manholes=["P1", "P2", "P3"], pipe_codes=["L1", "L2"], total_length=20.0)
    # Committed L1 carries water to its end (the junction); L2 is live with a water point.
    measured = {"L1": [
        {"dist": 0.0, "bob": -2.0, "obb": -1.5, "water_level": -2.2},
        {"dist": 7.0, "bob": -2.35, "obb": -1.85, "water_level": -2.2},
    ]}
    profile = build_profile(route, pipes, measured)
    # The committed end-anchor extends water to the junction (dist 10) before stripping.
    assert any(abs(v.dist - 10.0) < 1e-6 and v.water_level is not None
               for v in profile.vertices)

    spans = strip_preview_water(profile, route, pipes, committed_codes={"L1"})
    assert spans == [(10.0, 20.0)]
    # No water survives at the junction or anywhere in the live span.
    assert all(v.water_level is None for v in profile.vertices if v.dist >= 10.0 - 1e-6)
    # Real committed measurements (before the junction) keep their water.
    assert any(v.water_level is not None for v in profile.vertices if v.dist < 10.0 - 1e-6)


def test_strip_preview_water_noop_when_all_committed():
    pipes = {"L1": _pipe("L1", "P1", "P2", bob_a=-2.0, bob_b=-2.5, length=10.0)}
    route = Path(manholes=["P1", "P2"], pipe_codes=["L1"], total_length=10.0)
    measured = {"L1": [
        {"dist": 0.0, "bob": -2.0, "obb": -1.5, "water_level": -2.2},
        {"dist": 5.0, "bob": -2.25, "obb": -1.75, "water_level": -2.2},
    ]}
    profile = build_profile(route, pipes, measured)
    before = [v.water_level for v in profile.vertices]
    # A fully committed route has no live pipes -> no spans, water untouched.
    spans = strip_preview_water(profile, route, pipes, committed_codes={"L1"})
    assert spans == []
    assert [v.water_level for v in profile.vertices] == before
