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
                 on_ctrl_pick=None, on_drag=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.manhole_layer = manhole_layer
        self.on_pick = on_pick
        self.on_reset = on_reset
        self.on_move = on_move
        self.on_ctrl_pick = on_ctrl_pick
        self.on_drag = on_drag
        self._press_code = None

    def canvasPressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            point = self.toMapCoordinates(event.pos())
            self._press_code = self._nearest_manhole_code(point)

    def canvasReleaseEvent(self, event):  # noqa: N802 (Qt override)
        point = self.toMapCoordinates(event.pos())
        code = self._nearest_manhole_code(point)
        if event.button() == Qt.RightButton:
            # During trajectory editing (on_ctrl_pick wired) a right-click — which is
            # also what macOS makes of Ctrl+click — removes the nearest waypoint instead
            # of clearing everything. Other tools keep the plain reset.
            if self.on_ctrl_pick is not None and code is not None:
                self.on_ctrl_pick(code)
            else:
                self.on_reset()
            return
        if code is None:
            return
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        if ctrl and self.on_ctrl_pick is not None:
            self.on_ctrl_pick(code)
        elif self._press_code is not None and self._press_code != code and self.on_drag is not None:
            self.on_drag(self._press_code, code)
        else:
            self.on_pick(code)
        self._press_code = None

    def canvasMoveEvent(self, event):  # noqa: N802 (Qt override)
        if self.on_move is not None:
            self.on_move(self.toMapCoordinates(event.pos()))

    def _nearest_manhole_code(self, point: QgsPointXY):
        """Return the code of the nearest manhole feature to ``point``."""
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
        return nearest_code
