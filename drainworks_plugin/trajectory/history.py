"""Undo/redo history for the trajectory waypoint list (pure)."""


class WaypointHistory:
    """A linear undo/redo stack of waypoint lists.

    ``set(waypoints)`` pushes a new state (truncating any redo branch). ``undo`` /
    ``redo`` move the cursor; ``current`` returns a copy of the active state.
    """

    def __init__(self):
        self._stack = [[]]
        self._cursor = 0

    @property
    def current(self):
        """A copy of the active waypoint list."""
        return list(self._stack[self._cursor])

    def set(self, waypoints):
        """Push ``waypoints`` as the new state, dropping any redo branch."""
        self._stack = self._stack[: self._cursor + 1]
        self._stack.append(list(waypoints))
        self._cursor = len(self._stack) - 1

    def can_undo(self):
        """Whether there is an earlier state to step back to."""
        return self._cursor > 0

    def can_redo(self):
        """Whether there is a later state to step forward to."""
        return self._cursor < len(self._stack) - 1

    def undo(self):
        """Step back one state and return it (a copy)."""
        if self.can_undo():
            self._cursor -= 1
        return self.current

    def redo(self):
        """Step forward one state and return it (a copy)."""
        if self.can_redo():
            self._cursor += 1
        return self.current
