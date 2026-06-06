"""Dialog for the 'Bereken verloren berging' step settings."""

from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
)

# UI label <-> stored value.
_RES_LABELS = {"accurate": "nauwkeurig", "fast": "snel"}
_RES_VALUES = {v: k for k, v in _RES_LABELS.items()}


class BergingSettingsDialog(QDialog):
    """Edit the flood-fill resolution. ``values()`` returns a dict."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instellingen — verloren berging")
        form = QFormLayout(self)
        self.cmb_resolution = QComboBox()
        self.cmb_resolution.addItems(["nauwkeurig", "snel"])
        current = _RES_LABELS.get(settings.get("resolution", "accurate"), "nauwkeurig")
        self.cmb_resolution.setCurrentText(current)
        form.addRow("Resolutie", self.cmb_resolution)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        """Return ``{resolution: 'accurate'|'fast'}``."""
        return {"resolution": _RES_VALUES.get(self.cmb_resolution.currentText(), "accurate")}
