"""Canvas graphics for a trajectory: lettered waypoint markers + dashed route.

A dashed line is used for the route so the underlying data stays visible.
"""

from qgis.core import QgsWkbTypes
from qgis.gui import QgsRubberBand, QgsVertexMarker
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont

MARKER_COLOR = "#5a5a5a"
ROUTE_COLOR = "#5a5a5a"


class LabeledMarker(QgsVertexMarker):
    """A vertex marker that also paints a letter (A, B, C, …) beside it."""

    def __init__(self, canvas, label):
        super().__init__(canvas)
        self._label = label
        self.setIconType(QgsVertexMarker.ICON_CIRCLE)
        self.setIconSize(18)
        self.setPenWidth(3)
        self.setColor(QColor(MARKER_COLOR))
        self.setFillColor(QColor(MARKER_COLOR))   # filled so the white letter reads

    def boundingRect(self):  # noqa: N802 (Qt override)
        """Return the marker bounds enlarged to fit the painted letter."""
        return super().boundingRect().adjusted(-4, -4, 4, 4)

    def paint(self, painter):  # noqa: N802 (Qt override)
        """Paint the marker, then draw the centred white label letter."""
        super().paint(painter)
        painter.save()
        font = QFont()
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        from qgis.PyQt.QtCore import QRectF, Qt as _Qt
        painter.drawText(QRectF(-9, -9, 18, 18), _Qt.AlignCenter, self._label)
        painter.restore()


class TrajectoryGraphics:
    """Owns the route rubber band and the waypoint markers on a canvas."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.route_band = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self.route_band.setColor(QColor(90, 90, 90, 90))   # semi-transparent grey
        self.route_band.setWidth(10)                        # wide band
        self.route_band.setLineStyle(Qt.SolidLine)
        self.markers = []
        self.sink_markers = []
        self.hover_marker = None
        self.active_marker = None

    def _redraw(self):
        """Force an immediate repaint of the canvas overlay (markers/rubber bands)."""
        self.canvas.scene().update()

    def set_markers(self, labelled_points):
        """labelled_points: iterable of (label, QgsPointXY)."""
        self.clear_markers()
        for label, point in labelled_points:
            marker = LabeledMarker(self.canvas, label)
            marker.setCenter(point)
            self.markers.append(marker)
        self._redraw()

    def set_route(self, geometries):
        """Draw the route from a list of QgsGeometry line segments."""
        self.route_band.reset(QgsWkbTypes.LineGeometry)
        for geom in geometries:
            if geom is not None and not geom.isEmpty():
                self.route_band.addGeometry(geom, None)
        self._redraw()

    def set_sink_markers(self, points):
        """points: iterable of QgsPointXY for the chosen sink manholes."""
        for marker in self.sink_markers:
            self.canvas.scene().removeItem(marker)
        self.sink_markers = []
        for point in points:
            marker = QgsVertexMarker(self.canvas)
            marker.setIconType(QgsVertexMarker.ICON_INVERTED_TRIANGLE)
            marker.setColor(QColor("#0079c1"))
            marker.setFillColor(QColor("#01aeed"))
            marker.setIconSize(16)
            marker.setPenWidth(3)
            marker.setCenter(point)
            self.sink_markers.append(marker)
        self._redraw()

    def set_hover(self, point):
        """Show a single marker at ``point`` (QgsPointXY), or hide if None."""
        if self.hover_marker is None:
            self.hover_marker = QgsVertexMarker(self.canvas)
            self.hover_marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
            self.hover_marker.setColor(QColor("#c54141"))
            self.hover_marker.setIconSize(13)
            self.hover_marker.setPenWidth(3)
        if point is None:
            self.hover_marker.hide()
        else:
            self.hover_marker.setCenter(point)
            self.hover_marker.show()
        self._redraw()

    def set_active(self, point):
        """Highlight the active waypoint (where editing continues), or hide if None."""
        if self.active_marker is None:
            self.active_marker = QgsVertexMarker(self.canvas)
            self.active_marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
            self.active_marker.setColor(QColor("#0079c1"))
            self.active_marker.setFillColor(QColor(0, 121, 193, 70))
            self.active_marker.setIconSize(26)
            self.active_marker.setPenWidth(3)
        if point is None:
            self.active_marker.hide()
        else:
            self.active_marker.setCenter(point)
            self.active_marker.show()
        self._redraw()

    def clear_markers(self):
        """Remove the lettered waypoint markers from the canvas."""
        for marker in self.markers:
            self.canvas.scene().removeItem(marker)
        self.markers = []

    def clear(self):
        """Hide/remove all markers and reset the route band (keeps the band)."""
        self.clear_markers()
        for marker in self.sink_markers:
            self.canvas.scene().removeItem(marker)
        self.sink_markers = []
        if self.hover_marker is not None:
            self.hover_marker.hide()
        if self.active_marker is not None:
            self.active_marker.hide()
        self.route_band.reset(QgsWkbTypes.LineGeometry)
        self._redraw()

    def destroy(self):
        """Remove every canvas item (markers + rubber band) for plugin unload."""
        self.clear()
        scene = self.canvas.scene()
        if self.hover_marker is not None:
            scene.removeItem(self.hover_marker)
            self.hover_marker = None
        if self.active_marker is not None:
            scene.removeItem(self.active_marker)
            self.active_marker = None
        if self.route_band is not None:
            scene.removeItem(self.route_band)
            self.route_band = None
        self._redraw()
