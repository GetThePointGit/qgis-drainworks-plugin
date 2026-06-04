from drainworks_plugin.trajectory.history import WaypointHistory


def test_set_undo_redo():
    h = WaypointHistory()
    assert h.current == []
    h.set(["A"])
    h.set(["A", "B"])
    assert h.current == ["A", "B"]
    assert h.can_undo() is True
    assert h.undo() == ["A"]
    assert h.undo() == []
    assert h.can_undo() is False
    assert h.redo() == ["A"]
    assert h.current == ["A"]


def test_set_truncates_redo_branch():
    h = WaypointHistory()
    h.set(["A"]); h.set(["A", "B"])
    h.undo()
    h.set(["A", "C"])
    assert h.can_redo() is False
    assert h.current == ["A", "C"]


def test_current_is_a_copy():
    h = WaypointHistory()
    h.set(["A"])
    got = h.current
    got.append("X")
    assert h.current == ["A"]
