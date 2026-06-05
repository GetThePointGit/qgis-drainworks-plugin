"""A reusable pyqtgraph widget showing a longitudinal sewer profile.

Draws the invert (bob) line, the crown (obb) line, an optional water-level fill
(verloren berging), and observation markers. pyqtgraph gives free zoom/pan.
Embedded in the Drainworks dock.
"""

import pyqtgraph as pg
from qgis.PyQt.QtCore import QEvent, Qt, pyqtSignal
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
        # Moving off the plot fast (e.g. onto the map) stops sending move events, so
        # the last position would linger. Catch the widget Leave to clear it too.
        self.plot.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Emit ``hovered(-1)`` when the cursor leaves the plot (clears the map ring)."""
        if obj is self.plot and event.type() == QEvent.Leave:
            self._cursor.hide()
            self.hovered.emit(-1.0)
        return super().eventFilter(obj, event)

    def _on_mouse_moved(self, pos):
        """Track the cursor, move the vertical line, and emit ``hovered`` (m)."""
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
        """Clear the plot and hide the hover cursor."""
        self.plot.clear()
        self._cursor.hide()

    def _style(self, key):
        """Return the ``{'color', 'width'}`` style for a line ``key``."""
        from drainworks_plugin.sideview.settings import LINE_DEFAULTS
        lines = getattr(self, "_lines", None) or LINE_DEFAULTS
        return lines.get(key, LINE_DEFAULTS[key])

    def _pen(self, key, dashed=False):
        """Build a pyqtgraph pen for line ``key`` (optionally dashed)."""
        s = self._style(key)
        kw = {"color": s.get("color", "#000000"), "width": s.get("width", 1)}
        if dashed:
            kw["style"] = Qt.DashLine
        return pg.mkPen(**kw)

    def _add_water_fill(self, bob_dists, bobs, water_dists, water_levels):
        """Fill (verloren berging) between the invert and the water-level curves."""
        from qgis.PyQt.QtGui import QColor
        bob_curve = pg.PlotCurveItem(bob_dists, bobs)
        water_curve = pg.PlotCurveItem(water_dists, water_levels)
        brush_color = QColor(self._style("water").get("color", "#2c7fb8"))
        brush_color.setAlpha(120)
        self.plot.addItem(pg.FillBetweenItem(bob_curve, water_curve, brush=pg.mkBrush(brush_color)))
        self.plot.plot(water_dists, water_levels, pen=self._pen("water", dashed=True),
                       name="Waterpeil")

    def show_profile(self, profile) -> None:
        """Render a Profile."""
        self.plot.clear()
        self._last_profile = profile

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
                pen=self._pen("ideal", dashed=True), name="BOB leiding (recht)",
                skipFiniteCheck=True)

        # Crown (top of pipe) and measured invert. Per-point markers are the pyqtgraph
        # bottleneck on long routes, so only draw them for short profiles.
        self.plot.plot(dists, obbs, pen=self._pen("crown"), name="Bovenkant buis",
                       skipFiniteCheck=True)
        bob_color = self._style("bob").get("color", "#333333")
        marker_kw = (dict(symbol="o", symbolSize=4, symbolBrush=bob_color, symbolPen=None)
                     if len(dists) <= 500 else {})
        self.plot.plot(dists, bobs, pen=self._pen("bob"), name="BOB gemeten",
                       skipFiniteCheck=True, **marker_kw)

        # Water-level fill (verloren berging) where water_level is set.
        water = [v.water_level if v.water_level is not None else v.bob for v in profile.vertices]
        if any(v.water_level is not None for v in profile.vertices):
            self._add_water_fill(dists, bobs, dists, water)

        # Each put: a solid green invert->maaiveld line, plus a thin light full-height
        # line carrying the put code as a vertical label. Both stay out of auto-zoom.
        show_codes = getattr(self, "_show_putcodes", True)
        put_color = self._style("put").get("color", "#398a39")
        levels = getattr(profile, "manhole_levels", [])
        for dist, code, bottom, ground in levels:
            top = ground if ground is not None else bottom
            item = pg.PlotCurveItem([dist, dist], [bottom, top], pen=self._pen("put"))
            self.plot.addItem(item, ignoreBounds=True)
            line = pg.InfiniteLine(
                pos=dist, angle=90, pen=pg.mkPen(put_color, width=1),
                label=(code if show_codes else None),
                labelOpts={"position": 0.92, "color": put_color, "rotateAxis": (1, 0)})
            self.plot.addItem(line)
        # Maaiveld line connecting the put ground levels (excluded from auto-zoom).
        ground_pts = [(d, g) for d, _c, _b, g in levels if g is not None]
        if len(ground_pts) >= 2:
            maaiveld = pg.PlotCurveItem(
                [d for d, _ in ground_pts], [g for _, g in ground_pts],
                pen=self._pen("maaiveld", dashed=True), name="Maaiveld")
            self.plot.addItem(maaiveld, ignoreBounds=True)

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

    def apply_settings(self, settings):
        """Apply SideViewSettings (re-render the current profile if any)."""
        self._show_putcodes = settings.show_putcodes
        self._lines = settings.lines
        legend = self.plot.plotItem.legend
        if legend is not None:
            anchors = {
                "top-left": ((0, 0), (0, 0), (10, 10)),
                "top-right": ((1, 0), (1, 0), (-10, 10)),
                "bottom-left": ((0, 1), (0, 1), (10, -10)),
                "bottom-right": ((1, 1), (1, 1), (-10, -10)),
                "below": ((0.5, 1), (0.5, 1), (0, 0)),
            }
            a = anchors.get(settings.legend_position, anchors["top-left"])
            legend.anchor(*a)
            if hasattr(legend, "setColumnCount"):
                legend.setColumnCount(8 if settings.legend_position == "below" else 1)
            legend.setBrush(pg.mkBrush(255, 255, 255, 220) if settings.legend_white_bg else None)
        if getattr(self, "_last_profile", None) is not None:
            self.show_profile(self._last_profile)

    def show_water(self, water_points):
        """Draw the verloren-berging water fill from [(dist, level)] points."""
        if not water_points or getattr(self, "_last_profile", None) is None:
            return
        verts = self._last_profile.vertices
        if not verts:
            return
        dists = [v.dist for v in verts]
        bobs = [v.bob for v in verts]
        self._add_water_fill(dists, bobs, [d for d, _ in water_points],
                             [lvl for _, lvl in water_points])
