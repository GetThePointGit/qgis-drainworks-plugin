"""A reusable pyqtgraph widget showing a longitudinal sewer profile.

Draws the invert (bob) line, the crown (obb) line, an optional water-level fill
(verloren berging), and observation markers. pyqtgraph gives free zoom/pan.
Embedded in the Drainworks dock.
"""

import pyqtgraph as pg
from qgis.PyQt.QtCore import QEvent, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QVBoxLayout, QWidget


def _shoreline_curves(dists, bobs, waters):
    """Return ``(xs, bobs, waters, wet)`` for the water fill, with shore points inserted.

    ``waters`` is the per-vertex water level (the invert where dry). At a wet/dry
    transition a point is inserted where the invert reaches the *pool* level (the wet
    side's water), so the surface stays horizontal across the pool and drops to zero
    there (a shore) instead of sloping toward the next dry invert. The returned
    ``waters`` are clamped to ``>= bobs``; ``wet[i]`` marks points that carry water
    (used to draw the dashed surface line only over pools).
    """
    eps = 1e-9
    xs, bb, ww, wet = [], [], [], []
    for i in range(len(dists)):
        if i > 0:
            d0, b0, w0 = dists[i - 1], bobs[i - 1], waters[i - 1]
            d1, b1, w1 = dists[i], bobs[i], waters[i]
            wet0, wet1 = (w0 - b0 > eps), (w1 - b1 > eps)
            if wet0 != wet1:
                level = w0 if wet0 else w1                 # pool level from the wet side
                t = (level - b0) / (b1 - b0) if b1 != b0 else 0.5
                t = min(max(t, 0.0), 1.0)
                xs.append(d0 + t * (d1 - d0))
                bb.append(level); ww.append(level); wet.append(True)   # shore at pool level
        w = max(waters[i], bobs[i])
        xs.append(dists[i]); bb.append(bobs[i]); ww.append(w)
        wet.append(w - bobs[i] > eps)
    return xs, bb, ww, wet


def _clip_curves(dists, bobs, waters):
    """Return ``(xs, bobs, waters, wet)`` clipping a sloped water surface to the invert.

    Unlike :func:`_shoreline_curves` the surface is kept as given (a sloped
    interpolation), only clamped to ``>= bobs``; a crossing point is inserted where the
    surface meets the invert so the fill drops to zero there. Used by the segment
    overlay (interpolated between segment midpoints).
    """
    eps = 1e-9
    xs, bb, ww, wet = [], [], [], []
    for i in range(len(dists)):
        if i > 0:
            d0, b0, w0 = dists[i - 1], bobs[i - 1], waters[i - 1]
            d1, b1, w1 = dists[i], bobs[i], waters[i]
            f0, f1 = w0 - b0, w1 - b1                    # water depth
            if (f0 > eps) != (f1 > eps) and (f0 - f1) != 0:
                t = f0 / (f0 - f1)
                xs.append(d0 + t * (d1 - d0))
                yc = b0 + t * (b1 - b0)
                bb.append(yc); ww.append(yc); wet.append(True)
        w = max(waters[i], bobs[i])
        xs.append(dists[i]); bb.append(bobs[i]); ww.append(w)
        wet.append(w - bobs[i] > eps)
    return xs, bb, ww, wet


def _interp(x, xs, ys):
    """Linear interpolation of ``ys`` at ``x`` over sorted ``xs`` (clamped to the ends)."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    import bisect
    k = bisect.bisect_right(xs, x)
    x0, x1, y0, y1 = xs[k - 1], xs[k], ys[k - 1], ys[k]
    t = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


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

    def _water_brush(self):
        """Return the translucent brush colour for the water fill."""
        from qgis.PyQt.QtGui import QColor
        c = QColor(self._style("water").get("color", "#2c7fb8"))
        c.setAlpha(120)
        return c

    _WATER_LABEL = "Water (verloren berging)"

    def _water_legend(self, brush_color, active=True):
        """Add the clickable water legend entry; clicking it shows/hides the water.

        Always added when there is water data (even when hidden) so it stays available
        to toggle back on. When hidden the swatch is drawn empty and the label gets
        "(uit)". An empty named curve renders the filled sample (the FillBetweenItem
        itself has no legend entry) and is removed by ``plot.clear()`` each render, so
        it never duplicates. The sample's click is rebound to toggle the actual water.
        """
        label = self._WATER_LABEL if active else f"{self._WATER_LABEL} (uit)"
        swatch = self.plot.plot([], [], pen=self._pen("water", dashed=True),
                                fillLevel=0 if active else None,
                                fillBrush=pg.mkBrush(brush_color) if active else None,
                                name=label)
        legend = self.plot.plotItem.legend
        if legend is None:
            return
        for sample, _label in list(getattr(legend, "items", [])):
            if getattr(sample, "item", None) is swatch:
                sample.mouseClickEvent = self._on_water_legend_click
                break

    def _on_water_legend_click(self, event=None):
        """Toggle the water (line + fill) when its legend entry is clicked."""
        if event is not None:
            try:
                event.accept()
            except Exception:
                pass
        self._show_water = not getattr(self, "_show_water", True)
        if getattr(self, "_last_profile", None) is not None:
            self.show_profile(self._last_profile, getattr(self, "_last_water_overlay", None))

    def _draw_water_runs(self, dists, bobs, waters, curve_fn):
        """Fill water per maximal run of non-None ``waters``, using ``curve_fn``.

        Each run is filled on its own, so water never bridges a gap (``None`` water,
        e.g. a pipe-end anchor or outside the overlay span). ``curve_fn`` builds the
        fill curves for a run: :func:`_shoreline_curves` (flat pools, per-point water)
        or :func:`_clip_curves` (a sloped interpolated surface, the segment overlay).
        """
        brush_color = self._water_brush()
        nan = float("nan")
        i, n = 0, len(dists)
        while i < n:
            if waters[i] is None:
                i += 1
                continue
            j = i
            while j < n and waters[j] is not None:
                j += 1
            d, b, w = dists[i:j], bobs[i:j], waters[i:j]
            i = j
            if len(d) < 2 or not any(wl > bv + 1e-9 for wl, bv in zip(w, b)):
                continue
            xs, bb, ww, wet = curve_fn(d, b, w)
            self.plot.addItem(pg.FillBetweenItem(
                pg.PlotCurveItem(xs, bb), pg.PlotCurveItem(xs, ww),
                brush=pg.mkBrush(brush_color)))
            surf = [wv if f else nan for wv, f in zip(ww, wet)]
            self.plot.plot(xs, surf, pen=self._pen("water", dashed=True), connect="finite")

    def _add_water_fill_aligned(self, dists, bobs, water_levels):
        """Fill per-point water as flat pools with shores (accurate berging)."""
        self._draw_water_runs(dists, bobs, water_levels, _shoreline_curves)

    def _add_water_overlay(self, dists, bobs, water_points):
        """Fill the segment overlay: one level per segment midpoint, interpolated.

        ``water_points`` is ``[(dist, level)]`` (segment midpoints). The surface is the
        straight interpolation between consecutive midpoints, clamped to the invert; no
        water is drawn before the first or after the last midpoint. The fill is built on
        a grid combining the midpoints with the invert vertices inside the span, so it
        works even where the invert has few vertices (e.g. an unmeasured pipe).
        """
        if not water_points:
            return
        wx = [d for d, _ in water_points]
        wy = [lv for _, lv in water_points]
        lo, hi = wx[0], wx[-1]
        if hi <= lo:
            return
        grid = sorted(set(wx) | {d for d in dists if lo <= d <= hi})
        b = [_interp(x, dists, bobs) for x in grid]
        w = [_interp(x, wx, wy) for x in grid]
        self._draw_water_runs(grid, b, w, _clip_curves)

    def show_profile(self, profile, water_overlay=None) -> None:
        """Render a Profile (with an optional segment-midpoint water overlay)."""
        self.plot.clear()
        self._last_profile = profile
        self._last_water_overlay = water_overlay

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

        # Water (verloren berging), toggleable. Per-point water (accurate) draws flat
        # pools; otherwise the segment-midpoint overlay draws an interpolated surface.
        has_water = any(v.water_level is not None for v in profile.vertices) or bool(water_overlay)
        if has_water:
            active = getattr(self, "_show_water", True)
            if active:
                if any(v.water_level is not None for v in profile.vertices):
                    self._add_water_fill_aligned(
                        dists, bobs, [v.water_level for v in profile.vertices])
                elif water_overlay:
                    self._add_water_overlay(dists, bobs, water_overlay)
            # Always keep the clickable legend entry so the water can be toggled back on.
            self._water_legend(self._water_brush(), active=active)

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
        self._show_water = settings.show_water
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
            self.show_profile(self._last_profile, getattr(self, "_last_water_overlay", None))
