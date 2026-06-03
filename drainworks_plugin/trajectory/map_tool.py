"""Map tool that reports clicked manholes to a controller (the dock).

Left-click picks the nearest manhole and calls ``on_pick(code)``; right-click
calls ``on_reset()``. All trajectory state lives in the controller.
"""

from qgis.core import QgsGeometry, QgsPointXY
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt


class TrajectoryMapTool(QgsMapTool):
    """Pick manholes on the canvas; delegate handling to callbacks."""

    def __init__(self, canvas, manhole_layer, on_pick, on_reset, on_move=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.manhole_layer = manhole_layer
        self.on_pick = on_pick
        self.on_reset = on_reset
        self.on_move = on_move

    def canvasReleaseEvent(self, event):  # noqa: N802 (Qt override)
        if event.button() == Qt.RightButton:
            self.on_reset()
            return
        point = self.toMapCoordinates(event.pos())
        code = self._nearest_manhole_code(point)
        if code is not None:
            self.on_pick(code)

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
