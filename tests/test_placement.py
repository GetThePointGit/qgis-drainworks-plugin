import rgs_ribx
from drainworks_plugin.trajectory.network import SewerNetwork
from drainworks_plugin.trajectory.placement import place_waypoint


def _net():
    # A - B - C - D in a line, plus a spur E off B, and an isolated X.
    pipes = [
        rgs_ribx.Pipe(code="AB", manhole1="A", manhole2="B", length=10.0),
        rgs_ribx.Pipe(code="BC", manhole1="B", manhole2="C", length=10.0),
        rgs_ribx.Pipe(code="CD", manhole1="C", manhole2="D", length=10.0),
        rgs_ribx.Pipe(code="BE", manhole1="B", manhole2="E", length=10.0),
        rgs_ribx.Pipe(code="XY", manhole1="X", manhole2="Y", length=10.0),
    ]
    return SewerNetwork(pipes)


def test_empty_adds_first():
    assert place_waypoint(_net(), [], None, "A") == (["A"], "A")


def test_existing_waypoint_selects_only():
    assert place_waypoint(_net(), ["A", "D"], "A", "D") == (["A", "D"], "D")


def test_on_route_inserts_tussenpunt():
    # route A->D runs through B and C; clicking C inserts it as a waypoint.
    new, active = place_waypoint(_net(), ["A", "D"], "A", "C")
    assert new == ["A", "C", "D"] and active == "C"


def test_last_selected_appends():
    new, active = place_waypoint(_net(), ["A", "B"], "B", "E")
    assert new == ["A", "B", "E"] and active == "E"


def test_single_point_appends():
    new, active = place_waypoint(_net(), ["A"], "A", "B")
    assert new == ["A", "B"] and active == "B"


def test_first_selected_prepends():
    new, active = place_waypoint(_net(), ["B", "C"], "B", "A")
    assert new == ["A", "B", "C"] and active == "A"


def test_middle_selected_moves():
    # waypoints A,B,D (B middle); selecting B then clicking E moves B->E.
    new, active = place_waypoint(_net(), ["A", "B", "D"], "B", "E")
    assert new == ["A", "E", "D"] and active == "E"


def test_unreachable_returns_none():
    assert place_waypoint(_net(), ["A", "B"], "B", "X") is None
