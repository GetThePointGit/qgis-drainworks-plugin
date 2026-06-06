"""Import dialog: pick a RIBX or GeoPackage file and a target GeoPackage.

The last-used directories are remembered in QGIS settings — separately for the
import file and the target GeoPackage — so the file dialogs reopen where you
left off.
"""

import os

from qgis.core import QgsSettings
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

# QgsSettings keys for the remembered start directories.
SETTINGS_INPUT_DIR = "drainworks/lastInputDir"
SETTINGS_TARGET_DIR = "drainworks/lastTargetDir"


def _remembered_dir(key: str) -> str:
    """Return the stored directory for ``key`` (empty string if none/invalid)."""
    value = QgsSettings().value(key, "", type=str)
    return value if value and os.path.isdir(value) else ""


def _remember_dir(key: str, file_path: str) -> None:
    """Store the directory of ``file_path`` under ``key``."""
    if file_path:
        QgsSettings().setValue(key, os.path.dirname(file_path))


class ImportDialog(QDialog):
    """Collect the input file and output GeoPackage path."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Drainworks — rioolgegevens importeren")
        self.input_path = QLineEdit()
        self.meas_path = QLineEdit()
        self.output_path = QLineEdit()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Bestand (RIBX / .rib / GeoPackage):"))
        layout.addLayout(self._row(self.input_path, self._browse_input))
        layout.addWidget(QLabel("Meetbestand (.hel / .rmb, alleen bij .rib — optioneel):"))
        layout.addLayout(self._row(self.meas_path, self._browse_meas))
        layout.addWidget(QLabel("Doel-GeoPackage (wordt aangemaakt/overschreven):"))
        layout.addLayout(self._row(self.output_path, self._browse_output))

        buttons = QHBoxLayout()
        ok = QPushButton("Importeren")
        cancel = QPushButton("Annuleren")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _row(self, line_edit, handler):
        """Build a line-edit + "Bladeren…" button row wired to ``handler``."""
        row = QHBoxLayout()
        browse = QPushButton("Bladeren…")
        browse.clicked.connect(handler)
        row.addWidget(line_edit)
        row.addWidget(browse)
        return row

    def _browse_input(self):
        """Pick the input file; remember its dir and suggest an output path."""
        start_dir = _remembered_dir(SETTINGS_INPUT_DIR)
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecteer bestand", start_dir,
            "Rioolgegevens (*.ribx *.xml *.rib *.hel *.gpkg)",
        )
        if path:
            self.input_path.setText(path)
            _remember_dir(SETTINGS_INPUT_DIR, path)
            if not self.output_path.text():
                base = os.path.splitext(path)[0]
                self.output_path.setText(base + ".gpkg")

    def _browse_meas(self):
        """Pick the optional measurement file (.hel / .rmb)."""
        start_dir = _remembered_dir(SETTINGS_INPUT_DIR)
        if not start_dir and self.input_path.text():
            start_dir = os.path.dirname(self.input_path.text())
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecteer meetbestand", start_dir, "Meetbestand (*.hel *.rmb)"
        )
        if path:
            self.meas_path.setText(path)

    def _browse_output(self):
        """Pick the target GeoPackage path and remember its directory."""
        # Prefer the remembered target dir; fall back to the chosen input's dir.
        start_dir = _remembered_dir(SETTINGS_TARGET_DIR)
        if not start_dir and self.input_path.text():
            start_dir = os.path.dirname(self.input_path.text())
        path, _ = QFileDialog.getSaveFileName(self, "Doel-GeoPackage", start_dir, "GeoPackage (*.gpkg)")
        if path:
            self.output_path.setText(path)
            _remember_dir(SETTINGS_TARGET_DIR, path)

    def values(self):
        """Return (input_path, measurement_path, output_gpkg_path)."""
        return (self.input_path.text(), self.meas_path.text(),
                self.output_path.text())
