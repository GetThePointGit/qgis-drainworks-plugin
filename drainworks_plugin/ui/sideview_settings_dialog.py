"""Dialog to edit SideViewSettings."""

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QPushButton,
    QSpinBox,
)

from drainworks_plugin.sideview.settings import SideViewSettings


class SideViewSettingsDialog(QDialog):
    """Edit legend position/background, line colour/width, show putcodes."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Langsprofiel-instellingen")
        self._settings = settings
        form = QFormLayout(self)

        self.cmb_legend = QComboBox()
        self.cmb_legend.addItems(["top-left", "top-right"])
        self.cmb_legend.setCurrentText(settings.legend_position)
        self.chk_white = QCheckBox(); self.chk_white.setChecked(settings.legend_white_bg)
        self.spn_width = QSpinBox(); self.spn_width.setRange(1, 8)
        self.spn_width.setValue(settings.line_width)
        self.chk_putcodes = QCheckBox(); self.chk_putcodes.setChecked(settings.show_putcodes)
        self._line_color = settings.line_color
        self.btn_color = QPushButton(settings.line_color)
        self.btn_color.clicked.connect(self._pick_color)

        form.addRow("Legenda-positie", self.cmb_legend)
        form.addRow("Witte legenda-achtergrond", self.chk_white)
        form.addRow("Lijnkleur", self.btn_color)
        form.addRow("Lijndikte", self.spn_width)
        form.addRow("Toon putcodes", self.chk_putcodes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._reset)
        form.addRow(buttons)

    def _pick_color(self):
        from qgis.PyQt.QtWidgets import QColorDialog
        from qgis.PyQt.QtGui import QColor
        color = QColorDialog.getColor(QColor(self._line_color), self)
        if color.isValid():
            self._line_color = color.name()
            self.btn_color.setText(color.name())

    def _reset(self):
        defaults = SideViewSettings()
        self.cmb_legend.setCurrentText(defaults.legend_position)
        self.chk_white.setChecked(defaults.legend_white_bg)
        self.spn_width.setValue(defaults.line_width)
        self.chk_putcodes.setChecked(defaults.show_putcodes)
        self._line_color = defaults.line_color
        self.btn_color.setText(defaults.line_color)

    def values(self):
        """Return the edited SideViewSettings."""
        return SideViewSettings(
            legend_position=self.cmb_legend.currentText(),
            legend_white_bg=self.chk_white.isChecked(),
            line_color=self._line_color,
            line_width=self.spn_width.value(),
            show_putcodes=self.chk_putcodes.isChecked())
