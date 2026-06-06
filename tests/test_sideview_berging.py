from drainworks_plugin.sideview.berging import route_berging


class _Route:
    def __init__(self, pipe_codes, manholes):
        self.pipe_codes = pipe_codes
        self.manholes = manholes


def test_route_berging_builds_water_line_and_volume():
    route = _Route(["L1"], ["A", "B"])
    pipes = {"L1": type("P", (), {"manhole1": "A", "manhole2": "B", "length": 30.0})()}
    segments_by_pipe = {"L1": [
        {"dist_from": 0.0, "dist_to": 15.0, "water_level": -2.1, "lost_volume": 0.3},
        {"dist_from": 15.0, "dist_to": 30.0, "water_level": -2.2, "lost_volume": 0.5},
    ]}
    water, volume = route_berging(route, pipes, segments_by_pipe)
    assert round(volume, 2) == 0.8
    # one point per segment, at the segment midpoint
    assert [round(d, 1) for d, _ in water] == [7.5, 22.5]
    assert any(abs(level - (-2.1)) < 1e-9 for _d, level in water)


def test_route_berging_reversed_pipe_orients_distance():
    route = _Route(["L1"], ["B", "A"])
    pipes = {"L1": type("P", (), {"manhole1": "A", "manhole2": "B", "length": 30.0})()}
    segments_by_pipe = {"L1": [
        {"dist_from": 0.0, "dist_to": 10.0, "water_level": -2.5, "lost_volume": 0.4},
    ]}
    water, volume = route_berging(route, pipes, segments_by_pipe)
    assert round(volume, 2) == 0.4
    assert max(d for d, _ in water) <= 30.0 + 1e-9
    assert min(d for d, _ in water) >= 20.0 - 1e-9
