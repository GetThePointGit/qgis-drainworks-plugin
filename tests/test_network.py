import pytest

import rgs_ribx

from drainworks_plugin.trajectory.network import SewerNetwork


def _pipe(code, a, b, length):
    return rgs_ribx.Pipe(code=code, manhole1=a, manhole2=b, length=length, bob1=0, bob2=0)


def test_shortest_path_picks_lower_total_length():
    pipes = [
        _pipe("L1", "P1", "P2", 10.0),
        _pipe("L2", "P2", "P3", 10.0),
        _pipe("L3", "P1", "P3", 25.0),
    ]
    net = SewerNetwork(pipes)
    path = net.shortest_path("P1", "P3")
    assert path.manholes == ["P1", "P2", "P3"]
    assert path.pipe_codes == ["L1", "L2"]
    assert path.total_length == pytest.approx(20.0)


def test_direct_edge_when_shortest():
    pipes = [
        _pipe("L1", "P1", "P2", 10.0),
        _pipe("L2", "P2", "P3", 10.0),
        _pipe("L3", "P1", "P3", 5.0),
    ]
    net = SewerNetwork(pipes)
    path = net.shortest_path("P1", "P3")
    assert path.pipe_codes == ["L3"]


def test_route_through_waypoints():
    pipes = [
        _pipe("L1", "P1", "P2", 10.0),
        _pipe("L2", "P2", "P3", 10.0),
        _pipe("L3", "P3", "P4", 10.0),
    ]
    net = SewerNetwork(pipes)
    route = net.route(["P1", "P3", "P4"])
    assert route.manholes == ["P1", "P2", "P3", "P4"]
    assert route.pipe_codes == ["L1", "L2", "L3"]


def test_no_path_raises():
    pipes = [_pipe("L1", "P1", "P2", 10.0), _pipe("L9", "P8", "P9", 10.0)]
    net = SewerNetwork(pipes)
    with pytest.raises(ValueError):
        net.shortest_path("P1", "P9")
