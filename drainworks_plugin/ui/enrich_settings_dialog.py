"""Dialog for the 'Verrijk basisdata' step settings."""

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
)


class EnrichSettingsDialog(QDialog):
    """Edit Corrigeer BOB + segment lengths. ``values()`` returns a dict."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instellingen — basisdata verrijken")
        form = QFormLayout(self)
        self.chk_correct_bob = QCheckBox()
        self.chk_correct_bob.setChecked(bool(settings.get("correct_bob", True)))
        self.spn_min_segment = QDoubleSpinBox()
        self.spn_min_segment.setRange(0.1, 50.0)
        self.spn_min_segment.setSuffix(" m")
        self.spn_min_segment.setValue(float(settings.get("min_segment", 1.0)))
        self.spn_bob_segment = QDoubleSpinBox()
        self.spn_bob_segment.setRange(0.5, 100.0)
        self.spn_bob_segment.setSuffix(" m")
        self.spn_bob_segment.setValue(float(settings.get("bob_segment", 5.0)))
        form.addRow("Corrigeer BOB", self.chk_correct_bob)
        form.addRow("Segment (min.)", self.spn_min_segment)
        form.addRow("BOB-segment", self.spn_bob_segment)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        """Return ``{correct_bob, min_segment, bob_segment}``."""
        return {
            "correct_bob": self.chk_correct_bob.isChecked(),
            "min_segment": self.spn_min_segment.value(),
            "bob_segment": self.spn_bob_segment.value(),
        }
