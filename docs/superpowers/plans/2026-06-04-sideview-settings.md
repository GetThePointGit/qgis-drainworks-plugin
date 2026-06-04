# Side-view Settings + Panel Polish (C7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-line colour/width in the langsprofiel settings, white legend background by default, more legend positions (4 corners + below-horizontal), a fully Dutch dialog, and a shorter panel (gear next to the action button).

**Architecture:** A TDD rework of `SideViewSettings` to a per-line model; then wiring in `sideview_widget.py` (per-line pens + legend positions), `ui/sideview_settings_dialog.py` (per-line rows + Dutch), and a small `ui/dock.py` layout change. Verified by the suite + dock construction smoke + manual check.

**Tech Stack:** PyQt5 / pyqtgraph, pytest.

**Spec:** `docs/superpowers/specs/2026-06-04-sideview-settings-design.md`.

**Repo:** plugin, branch `feature/sideview-settings`. Test/env prefix:
```bash
cd /Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin && export QGIS_PY="/Applications/QGIS-LTR2.app/Contents/MacOS/bin/python3" PROJ_LIB="/Applications/QGIS-LTR2.app/Contents/Resources/proj" PROJ_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/proj" GDAL_DATA="/Applications/QGIS-LTR2.app/Contents/Resources/gdal" PYTHONPATH="/Users/bastiaanroos/Documents/GitHub/qgis-drainworks-plugin:/Users/bastiaanroos/Documents/GitHub/rgs-ribx/src" && "$QGIS_PY" -m pytest <args>
```
Teardown segfault after the summary is harmless. **Never push.**

---

## Task 1: Per-line SideViewSettings model

**Files:** Modify `drainworks_plugin/sideview/settings.py`; Replace `tests/test_sideview_settings.py`.

- [ ] **Step 1: Replace `tests/test_sideview_settings.py`** with the new-model tests:
```python
from drainworks_plugin.sideview.settings import LINE_DEFAULTS, SideViewSettings


def test_defaults():
    s = SideViewSettings()
    assert s.legend_position == "top-left"
    assert s.legend_white_bg is True          # white background on by default
    assert s.show_putcodes is True
    assert s.line("bob")["color"] == "#333333"
    assert s.line("water")["width"] == 1
    assert set(s.lines) == set(LINE_DEFAULTS)


def test_roundtrip_dict():
    s = SideViewSettings()
    s.lines["bob"]["color"] = "#ff0000"
    s.lines["bob"]["width"] = 4
    s2 = SideViewSettings.from_dict(s.to_dict())
    assert s2.line("bob") == {"color": "#ff0000", "width": 4}
    assert s2.legend_white_bg is True


def test_from_dict_fills_missing_lines_and_keys():
    s = SideViewSettings.from_dict({"lines": {"bob": {"color": "#123456"}}})
    assert s.line("bob")["color"] == "#123456"
    assert s.line("bob")["width"] == LINE_DEFAULTS["bob"]["width"]   # filled
    assert s.line("maaiveld") == LINE_DEFAULTS["maaiveld"]           # whole line filled


def test_from_dict_ignores_legacy_flat_keys():
    s = SideViewSettings.from_dict({"line_color": "#000000", "line_width": 9})
    assert s.line("bob") == LINE_DEFAULTS["bob"]   # legacy keys ignored, defaults used
```

- [ ] **Step 2: Run — expect fail** (`ImportError: cannot import name 'LINE_DEFAULTS'`):
`"$QGIS_PY" -m pytest tests/test_sideview_settings.py -v`

- [ ] **Step 3: Replace `drainworks_plugin/sideview/settings.py`** with:
```python
"""Persistent side-view display settings (pure dataclass + dict (de)serialisation).

The dock loads/saves these via QgsSettings; this module stays QGIS-free so it is
testable.
"""

from dataclasses import dataclass, field

# Per-line default colour + width. Keys map to the lines drawn in the side-view.
LINE_DEFAULTS = {
    "bob": {"color": "#333333", "width": 2},        # BOB gemeten (measured invert)
    "crown": {"color": "#888888", "width": 1},      # Bovenkant buis
    "ideal": {"color": "#cc8400", "width": 1},      # BOB leiding (recht)
    "maaiveld": {"color": "#a0522d", "width": 1},   # Maaiveld
    "put": {"color": "#398a39", "width": 2},        # Put-lijn
    "water": {"color": "#2c7fb8", "width": 1},      # Waterpeil
}


def _default_lines():
    return {key: dict(value) for key, value in LINE_DEFAULTS.items()}


@dataclass
class SideViewSettings:
    """User-tunable side-view appearance."""

    legend_position: str = "top-left"   # top-left|top-right|bottom-left|bottom-right|below
    legend_white_bg: bool = True
    show_putcodes: bool = True
    lines: dict = field(default_factory=_default_lines)

    def line(self, key):
        """Return ``{'color', 'width'}`` for a line key (defaults if unknown)."""
        return self.lines.get(key, LINE_DEFAULTS.get(key, {"color": "#000000", "width": 1}))

    def to_dict(self):
        """Return a plain-dict representation."""
        return {
            "legend_position": self.legend_position,
            "legend_white_bg": self.legend_white_bg,
            "show_putcodes": self.show_putcodes,
            "lines": {key: dict(value) for key, value in self.lines.items()},
        }

    @classmethod
    def from_dict(cls, data):
        """Build from a dict, filling missing keys with defaults (legacy-safe)."""
        data = data or {}
        s = cls()
        if "legend_position" in data:
            s.legend_position = data["legend_position"]
        if "legend_white_bg" in data:
            s.legend_white_bg = bool(data["legend_white_bg"])
        if "show_putcodes" in data:
            s.show_putcodes = bool(data["show_putcodes"])
        stored = data.get("lines") or {}
        for key, default in LINE_DEFAULTS.items():
            merged = dict(default)
            merged.update({k: v for k, v in (stored.get(key) or {}).items() if k in default})
            s.lines[key] = merged
        return s
```

- [ ] **Step 4: Run — expect pass:** `"$QGIS_PY" -m pytest tests/test_sideview_settings.py -v`

- [ ] **Step 5: Commit**
```bash
git add drainworks_plugin/sideview/settings.py tests/test_sideview_settings.py
git commit -m "feat: per-line SideViewSettings model (color+width per line, white bg default)"
```

---

## Task 2: Side-view renders per-line styles + new legend positions

**Files:** Modify `drainworks_plugin/sideview/sideview_widget.py`.

- [ ] **Step 1: Add per-line pen helpers.** Add these methods to `SideViewWidget`
(e.g. just before `show_profile`):
```python
    def _style(self, key):
        from drainworks_plugin.sideview.settings import LINE_DEFAULTS
        lines = getattr(self, "_lines", None) or LINE_DEFAULTS
        return lines.get(key, LINE_DEFAULTS[key])

    def _pen(self, key, dashed=False):
        s = self._style(key)
        kw = {"color": s.get("color", "#000000"), "width": s.get("width", 1)}
        if dashed:
            kw["style"] = Qt.DashLine
        return pg.mkPen(**kw)
```

- [ ] **Step 2: Use the per-line pens in `show_profile`.** Replace the ideal/crown/bob
plots and the per-point water fill block:
```python
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
            dists, bobs,
            pen=pg.mkPen(getattr(self, "_line_color", "#333333"),
                         width=getattr(self, "_line_width", 2)),
            name="BOB gemeten",
            symbol="o", symbolSize=4,
            symbolBrush=getattr(self, "_line_color", "#333333"), symbolPen=None,
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
```
with:
```python
        # Straight pipe BOB line (bob1->bob2) so fluctuation of the measured
        # invert around it is visible.
        if profile.ideal:
            self.plot.plot(
                [d for d, _ in profile.ideal], [b for _, b in profile.ideal],
                pen=self._pen("ideal", dashed=True), name="BOB leiding (recht)")

        # Crown (top of pipe) and measured invert with a marker per point.
        self.plot.plot(dists, obbs, pen=self._pen("crown"), name="Bovenkant buis")
        bob_color = self._style("bob").get("color", "#333333")
        self.plot.plot(
            dists, bobs, pen=self._pen("bob"), name="BOB gemeten",
            symbol="o", symbolSize=4, symbolBrush=bob_color, symbolPen=None)

        # Water-level fill (verloren berging) where water_level is set.
        water = [v.water_level if v.water_level is not None else v.bob for v in profile.vertices]
        if any(v.water_level is not None for v in profile.vertices):
            self._add_water_fill(dists, bobs, dists, water)
```
Add the `_add_water_fill` helper (used by both per-point and segment water) to the class:
```python
    def _add_water_fill(self, bob_dists, bobs, water_dists, water_levels):
        from qgis.PyQt.QtGui import QColor
        bob_curve = pg.PlotCurveItem(bob_dists, bobs)
        water_curve = pg.PlotCurveItem(water_dists, water_levels)
        brush_color = QColor(self._style("water").get("color", "#2c7fb8"))
        brush_color.setAlpha(120)
        self.plot.addItem(pg.FillBetweenItem(bob_curve, water_curve, brush=pg.mkBrush(brush_color)))
        self.plot.plot(water_dists, water_levels, pen=self._pen("water", dashed=True),
                       name="Waterpeil")
```

- [ ] **Step 3: Use per-line styles for the put + maaiveld lines.** Replace the put loop
+ maaiveld block:
```python
        show_codes = getattr(self, "_show_putcodes", True)
        levels = getattr(profile, "manhole_levels", [])
        for dist, code, bottom, ground in levels:
            top = ground if ground is not None else bottom
            item = pg.PlotCurveItem([dist, dist], [bottom, top], pen=pg.mkPen("#398a39", width=2))
            self.plot.addItem(item, ignoreBounds=True)
            line = pg.InfiniteLine(
                pos=dist, angle=90, pen=pg.mkPen("#b5d6b5", width=1),
                label=(code if show_codes else None),
                labelOpts={"position": 0.92, "color": "#398a39", "rotateAxis": (1, 0)})
            self.plot.addItem(line)
        # Maaiveld line connecting the put ground levels (excluded from auto-zoom).
        ground_pts = [(d, g) for d, _c, _b, g in levels if g is not None]
        if len(ground_pts) >= 2:
            maaiveld = pg.PlotCurveItem(
                [d for d, _ in ground_pts], [g for _, g in ground_pts],
                pen=pg.mkPen("#a0522d", width=1, style=Qt.DashLine), name="Maaiveld")
            self.plot.addItem(maaiveld, ignoreBounds=True)
```
with:
```python
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
```

- [ ] **Step 4: Per-line `show_water` (segment mode).** Replace `show_water` with:
```python
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
```

- [ ] **Step 5: Rework `apply_settings`** for the per-line model + 5 legend positions +
white-bg default. Replace `apply_settings` with:
```python
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
```

- [ ] **Step 6: Full suite + import-smoke + commit.**
```
"$QGIS_PY" -m pytest
"$QGIS_PY" -c "import drainworks_plugin.sideview.sideview_widget as s; print('ok', hasattr(s.SideViewWidget,'_pen'))"
git add drainworks_plugin/sideview/sideview_widget.py
git commit -m "feat: side-view per-line pens + 5 legend positions + per-line water fill"
```

---

## Task 3: Dialog — per-line rows + Dutch

**Files:** Replace `drainworks_plugin/ui/sideview_settings_dialog.py`.

- [ ] **Step 1: Replace the dialog** with a per-line + Dutch version:
```python
"""Dialog to edit SideViewSettings."""

from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QWidget,
)

from drainworks_plugin.sideview.settings import LINE_DEFAULTS, SideViewSettings

# Stored value -> Dutch label, and the line keys -> Dutch labels.
_LEGEND = [("top-left", "Linksboven"), ("top-right", "Rechtsboven"),
           ("bottom-left", "Linksonder"), ("bottom-right", "Rechtsonder"),
           ("below", "Onder")]
_LINE_LABELS = {"bob": "BOB gemeten", "crown": "Bovenkant buis",
                "ideal": "BOB leiding (recht)", "maaiveld": "Maaiveld",
                "put": "Put-lijn", "water": "Waterpeil"}


class _LineRow(QWidget):
    """A colour button + width spin for one line."""

    def __init__(self, style, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._color = style.get("color", "#000000")
        self.btn_color = QPushButton(self._color)
        self.btn_color.clicked.connect(self._pick)
        self.spn_width = QSpinBox()
        self.spn_width.setRange(1, 8)
        self.spn_width.setValue(int(style.get("width", 1)))
        layout.addWidget(self.btn_color, 1)
        layout.addWidget(self.spn_width)

    def _pick(self):
        color = QColorDialog.getColor(QColor(self._color), self)
        if color.isValid():
            self._color = color.name()
            self.btn_color.setText(color.name())

    def value(self):
        return {"color": self._color, "width": self.spn_width.value()}


class SideViewSettingsDialog(QDialog):
    """Edit legend position/background, per-line colour/width, show putcodes."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Langsprofiel-instellingen")
        form = QFormLayout(self)

        self.cmb_legend = QComboBox()
        for value, label in _LEGEND:
            self.cmb_legend.addItem(label, value)
        idx = self.cmb_legend.findData(settings.legend_position)
        self.cmb_legend.setCurrentIndex(idx if idx >= 0 else 0)
        self.chk_white = QCheckBox()
        self.chk_white.setChecked(settings.legend_white_bg)
        self.chk_putcodes = QCheckBox()
        self.chk_putcodes.setChecked(settings.show_putcodes)
        form.addRow("Legenda-positie", self.cmb_legend)
        form.addRow("Witte legenda-achtergrond", self.chk_white)
        form.addRow("Toon putcodes", self.chk_putcodes)

        self.rows = {}
        for key in LINE_DEFAULTS:
            row = _LineRow(settings.line(key))
            self.rows[key] = row
            form.addRow(_LINE_LABELS[key], row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
        buttons.button(QDialogButtonBox.Cancel).setText("Annuleren")
        buttons.button(QDialogButtonBox.RestoreDefaults).setText("Standaardwaarden")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._reset)
        form.addRow(buttons)

    def _reset(self):
        defaults = SideViewSettings()
        self.cmb_legend.setCurrentIndex(self.cmb_legend.findData(defaults.legend_position))
        self.chk_white.setChecked(defaults.legend_white_bg)
        self.chk_putcodes.setChecked(defaults.show_putcodes)
        for key, row in self.rows.items():
            d = defaults.line(key)
            row._color = d["color"]
            row.btn_color.setText(d["color"])
            row.spn_width.setValue(d["width"])

    def values(self):
        """Return the edited SideViewSettings."""
        return SideViewSettings(
            legend_position=self.cmb_legend.currentData(),
            legend_white_bg=self.chk_white.isChecked(),
            show_putcodes=self.chk_putcodes.isChecked(),
            lines={key: row.value() for key, row in self.rows.items()})
```

- [ ] **Step 2: Full suite + import-smoke + commit.**
```
"$QGIS_PY" -m pytest
"$QGIS_PY" -c "import drainworks_plugin.ui.sideview_settings_dialog; print('ok')"
git add drainworks_plugin/ui/sideview_settings_dialog.py
git commit -m "feat: side-view settings dialog — per-line rows + Dutch labels/buttons"
```

---

## Task 4: Panel polish — gear next to the action button

**Files:** Modify `drainworks_plugin/ui/dock.py`.

- [ ] **Step 1: Card 1 — gear beside the button.** In `_build_ui`, the current card-1
block is:
```python
        gear1 = QHBoxLayout()
        gear1.addStretch()
        self.btn_enrich_settings = QToolButton()
        self.btn_enrich_settings.setIcon(_icon("gear.svg"))
        self.btn_enrich_settings.setIconSize(QSize(20, 20))
        self.btn_enrich_settings.setAutoRaise(True)
        self.btn_enrich_settings.setToolTip("Instellingen verrijken")
        self.btn_enrich_settings.clicked.connect(self._on_enrich_settings)
        gear1.addWidget(self.btn_enrich_settings)
        c1.addLayout(gear1)
        self.btn_enrich = QPushButton(_icon("lost_capacity.svg"), "Verrijk basisdata")
        self.btn_enrich.setToolTip(
            "Valideer, bereken hoogtes en bouw segmenten uit de basisdata")
        self.btn_enrich.clicked.connect(self._on_enrich)
        c1.addWidget(self.btn_enrich)
```
Replace with (button + gear on one row):
```python
        self.btn_enrich = QPushButton(_icon("lost_capacity.svg"), "Verrijk basisdata")
        self.btn_enrich.setToolTip(
            "Valideer, bereken hoogtes en bouw segmenten uit de basisdata")
        self.btn_enrich.clicked.connect(self._on_enrich)
        self.btn_enrich_settings = QToolButton()
        self.btn_enrich_settings.setIcon(_icon("gear.svg"))
        self.btn_enrich_settings.setIconSize(QSize(20, 20))
        self.btn_enrich_settings.setAutoRaise(True)
        self.btn_enrich_settings.setToolTip("Instellingen verrijken")
        self.btn_enrich_settings.clicked.connect(self._on_enrich_settings)
        row1 = QHBoxLayout()
        row1.addWidget(self.btn_enrich, 1)
        row1.addWidget(self.btn_enrich_settings)
        c1.addLayout(row1)
```

- [ ] **Step 2: Card 2 — gear beside the button.** The current card-2 block is:
```python
        gear2 = QHBoxLayout()
        gear2.addStretch()
        self.btn_loss_settings = QToolButton()
        self.btn_loss_settings.setIcon(_icon("gear.svg"))
        self.btn_loss_settings.setIconSize(QSize(20, 20))
        self.btn_loss_settings.setAutoRaise(True)
        self.btn_loss_settings.setToolTip("Instellingen verloren berging")
        self.btn_loss_settings.clicked.connect(self._on_loss_settings)
        gear2.addWidget(self.btn_loss_settings)
        c2.addLayout(gear2)
        c2.addWidget(QLabel("Sinks (uitstroompunten):"))
```
Replace with (move the gear off the top; it goes beside the button lower down):
```python
        c2.addWidget(QLabel("Sinks (uitstroompunten):"))
```
Then the current button line:
```python
        self.btn_loss = QPushButton(_icon("lost_capacity.svg"), "Bereken verloren berging")
        self.btn_loss.setToolTip(
            "Bereken de verloren berging op de segmenten met de gekozen sinks")
        self.btn_loss.clicked.connect(self._on_loss)
        c2.addWidget(self.btn_loss)
```
Replace with the button + gear on one row:
```python
        self.btn_loss = QPushButton(_icon("lost_capacity.svg"), "Bereken verloren berging")
        self.btn_loss.setToolTip(
            "Bereken de verloren berging op de segmenten met de gekozen sinks")
        self.btn_loss.clicked.connect(self._on_loss)
        self.btn_loss_settings = QToolButton()
        self.btn_loss_settings.setIcon(_icon("gear.svg"))
        self.btn_loss_settings.setIconSize(QSize(20, 20))
        self.btn_loss_settings.setAutoRaise(True)
        self.btn_loss_settings.setToolTip("Instellingen verloren berging")
        self.btn_loss_settings.clicked.connect(self._on_loss_settings)
        row2 = QHBoxLayout()
        row2.addWidget(self.btn_loss, 1)
        row2.addWidget(self.btn_loss_settings)
        c2.addLayout(row2)
```
(`btn_loss_settings` is now created after the sink table — that's fine; it's only
referenced in `_set_data_enabled`, which runs at the end of `_build_ui`.)

- [ ] **Step 3: Full suite + construction smoke + commit.**
```
"$QGIS_PY" -m pytest
export QT_QPA_PLATFORM=offscreen
"$QGIS_PY" -u -c "
from qgis.core import QgsApplication
app = QgsApplication([], True); app.initQgis()
from qgis.PyQt.QtWidgets import QMainWindow
mw = QMainWindow()
p = type('P', (), {'iface': type('I', (), {'mainWindow': lambda self: mw})()})()
from drainworks_plugin.ui.dock import DrainworksDock
dock = DrainworksDock(p)
print('DOCK OK', hasattr(dock,'btn_enrich_settings'), hasattr(dock,'btn_loss_settings'))
"
git add drainworks_plugin/ui/dock.py
git commit -m "feat: panel polish — step gear next to the action button"
```

---

## Task 5: Manual check + finish

- [ ] **Step 1: Full suite** — `"$QGIS_PY" -m pytest` → green.

- [ ] **Step 2: Manual QGIS check.** Open the langsprofiel-instellingen: each line
(BOB gemeten / Bovenkant buis / BOB leiding / Maaiveld / Put-lijn / Waterpeil) has its own
colour + width, and changing them re-renders the graph; the legend has a white background
by default and can be placed in any corner or below the graph (horizontal); the dialog is
Dutch (Annuleren / Standaardwaarden, Dutch positions). The two step ⚙ buttons sit next to
their action buttons and the panel is shorter.

- [ ] **Step 3: Finish.** REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch`.
Do NOT push.
