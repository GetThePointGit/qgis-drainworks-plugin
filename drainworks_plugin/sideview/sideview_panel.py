"""A dockable pyqtgraph panel showing a longitudinal sewer profile.

Draws the invert (bob) line, the crown (obb) line, an optional water-level
fill (verloren berging), and observation markers. pyqtgraph gives free zoom/pan.
"""

import pyqtgraph as pg
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDockWidget, QVBoxLayout, QWidget


class SideViewPanel(QDockWidget):
    """Dock widget plotting a :class:`Profile`."""

    def __init__(self, parent=None):
        super().__init__("Drainworks — side-view", parent)
        self.setObjectName("DrainworksSideView")
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "Afstand", units="m")
        self.plot.setLabel("left", "Hoogte (NAP)", units="m")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.addLegend()
        layout.addWidget(self.plot)
        self.setWidget(container)

    def show_profile(self, profile) -> None:
        """Render a Profile (from profile_builder.build_profile)."""
        self.plot.clear()

        dists = [v.dist for v in profile.vertices]
        bobs = [v.bob for v in profile.vertices]
        obbs = [v.obb for v in profile.vertices]

        # Crown (top of pipe).
        self.plot.plot(dists, obbs, pen=pg.mkPen("#888888", width=1), name="Bovenkant buis")
        # Invert (bottom of pipe).
        self.plot.plot(dists, bobs, pen=pg.mkPen("#333333", width=2), name="BOB (bodem)")

        # Water-level fill (verloren berging) where water_level is set.
        water = [v.water_level if v.water_level is not None else v.bob for v in profile.vertices]
        if any(v.water_level is not None for v in profile.vertices):
            bob_curve = pg.PlotCurveItem(dists, bobs)
            water_curve = pg.PlotCurveItem(dists, water)
            fill = pg.FillBetweenItem(bob_curve, water_curve, brush=pg.mkBrush(44, 127, 184, 120))
            self.plot.addItem(fill)
            self.plot.plot(dists, water, pen=pg.mkPen("#2c7fb8", width=1, style=Qt.DashLine),
                           name="Waterpeil")

        # Observation markers as vertical lines with labels.
        for marker in profile.observations:
            line = pg.InfiniteLine(
                pos=marker.dist, angle=90,
                pen=pg.mkPen("#c54141", width=1, style=Qt.DotLine),
                label=marker.code, labelOpts={"position": 0.95, "color": "#c54141"},
            )
            self.plot.addItem(line)

        self.plot.autoRange()
