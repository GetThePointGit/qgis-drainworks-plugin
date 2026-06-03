"""A reusable pyqtgraph widget showing a longitudinal sewer profile.

Draws the invert (bob) line, the crown (obb) line, an optional water-level fill
(verloren berging), and observation markers. pyqtgraph gives free zoom/pan.
Embedded in the Drainworks dock.
"""

import pyqtgraph as pg
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QVBoxLayout, QWidget


class SideViewWidget(QWidget):
    """Plots a :class:`Profile` (from profile_builder.build_profile)."""

    # Emitted with the distance (m) along the route under the cursor, or -1 when
    # the cursor leaves the plot. The dock maps it to a point on the canvas.
    hovered = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOptions(antialias=True)
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.setLabel("bottom", "Afstand", units="m")
        self.plot.setLabel("left", "Hoogte (NAP)", units="m")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.addLegend()
        layout.addWidget(self.plot)

        self._cursor = pg.InfiniteLine(angle=90, pen=pg.mkPen("#c54141", width=1))
        self._cursor.hide()
        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def _on_mouse_moved(self, pos):
        if not self.plot.sceneBoundingRect().contains(pos):
            self._cursor.hide()
            self.hovered.emit(-1.0)
            return
        x = self.plot.getViewBox().mapSceneToView(pos).x()
        self._cursor.setPos(x)
        self._cursor.show()
        self.hovered.emit(float(x))

    def set_cursor(self, dist):
        """Show/move the vertical cursor at ``dist`` (or hide when None)."""
        if dist is None:
            self._cursor.hide()
        else:
            self._cursor.setPos(float(dist))
            self._cursor.show()

    def clear(self) -> None:
        self.plot.clear()
        self._cursor.hide()

    def show_profile(self, profile) -> None:
        """Render a Profile."""
        self.plot.clear()

        dists = [v.dist for v in profile.vertices]
        bobs = [v.bob for v in profile.vertices]
        obbs = [v.obb for v in profile.vertices]
        if not dists:
            return

        # Straight pipe BOB line (bob1->bob2) so fluctuation of the measured
        # invert around it is visible.
        if profile.ideal:
            self.plot.plot(
                [d for d, _ in profile.ideal], [b for _, b in profile.ideal],
                pen=pg.mkPen("#cc8400", width=1, style=Qt.DashLine), name="BOB leiding (recht)",
            )

        # Crown (top of pipe) and measured invert with a marker per point.
        self.plot.plot(dists, obbs, pen=pg.mkPen("#888888", width=1), name="Bovenkant buis")
        self.plot.plot(
            dists, bobs, pen=pg.mkPen("#333333", width=2), name="BOB gemeten",
            symbol="o", symbolSize=4, symbolBrush="#333333", symbolPen=None,
        )

        # Water-level fill (verloren berging) where water_level is set.
        water = [v.water_level if v.water_level is not None else v.bob for v in profile.vertices]
        if any(v.water_level is not None for v in profile.vertices):
            bob_curve = pg.PlotCurveItem(dists, bobs)
            water_curve = pg.PlotCurveItem(dists, water)
            fill = pg.FillBetweenItem(bob_curve, water_curve, brush=pg.mkBrush(44, 127, 184, 120))
            self.plot.addItem(fill)
            self.plot.plot(dists, water, pen=pg.mkPen("#2c7fb8", width=1, style=Qt.DashLine),
                           name="Waterpeil")

        # Manholes as vertical grey lines with the put code at the top.
        for dist, code in getattr(profile, "manholes", []):
            line = pg.InfiniteLine(
                pos=dist, angle=90,
                pen=pg.mkPen("#398a39", width=1),
                label=code, labelOpts={"position": 0.08, "color": "#398a39",
                                       "rotateAxis": (1, 0)},
            )
            self.plot.addItem(line)

        # Observation markers as vertical dotted lines with labels.
        for marker in profile.observations:
            line = pg.InfiniteLine(
                pos=marker.dist, angle=90,
                pen=pg.mkPen("#c54141", width=1, style=Qt.DotLine),
                label=marker.code, labelOpts={"position": 0.95, "color": "#c54141"},
            )
            self.plot.addItem(line)

        # Re-add the hover cursor (plot.clear() removed it).
        self._cursor.hide()
        self.plot.addItem(self._cursor)
        self.plot.autoRange()
