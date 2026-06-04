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
