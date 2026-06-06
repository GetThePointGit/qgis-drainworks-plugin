"""Map tool that reports clicked manholes to a controller (the dock).

Left-click picks the nearest manhole and calls ``on_pick(code)``; right-click
calls ``on_reset()``. All trajectory state lives in the controller.
"""

from qgis.core import QgsGeometry, QgsPointXY
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt


class TrajectoryMapTool(QgsMapTool):
    """Pick manholes on the canvas; delegate handling to callbacks."""

    def __init__(self, canvas, manhole_layer, on_pick, on_reset, on_move=None,
                 on_ctrl_pick=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.manhole_layer = manhole_layer
        self.on_pick = on_pick
        self.on_reset = on_reset
        self.on_move = on_move
        self.on_ctrl_pick = on_ctrl_pick

    def canvasReleaseEvent(self, event):  # noqa: N802 (Qt override)
        """Dispatch a click to pick, ctrl-pick or reset the nearest manhole."""
        point = self.toMapCoordinates(event.pos())
        right = event.button() == Qt.RightButton
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        # During trajectory editing (on_ctrl_pick wired) a right-click — which is also
        # what macOS makes of Ctrl+click — passes the *snapped* waypoint, or None when
        # the click is not on a manhole, so the controller can remove a point or finish.
        if self.on_ctrl_pick is not None and (right or (ctrl and not right)):
            tol = self.canvas.mapUnitsPerPixel() * 18
            self.on_ctrl_pick(self._nearest_manhole_code(point, max_dist=tol))
            return
        if right:
            self.on_reset()
            return
        code = self._nearest_manhole_code(point)
        if code is not None:
            self.on_pick(code)

    def _nearest_manhole_code(self, point: QgsPointXY, max_dist=None):
        """Return the nearest manhole code to ``point`` (or None beyond ``max_dist``)."""
        target = QgsGeometry.fromPointXY(point)
        nearest_code = None
        nearest_dist = float("inf")
        for feat in self.manhole_layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            d = geom.distance(target)
            if d < nearest_dist:
                nearest_dist = d
                nearest_code = feat["code"]
        if max_dist is not None and nearest_dist > max_dist:
            return None
        return nearest_code

    def canvasMoveEvent(self, event):  # noqa: N802 (Qt override)
        """Report the hovered map coordinate to ``on_move`` (if wired)."""
        if self.on_move is not None:
            self.on_move(self.toMapCoordinates(event.pos()))
