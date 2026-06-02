"""Import dialog: pick a RIBX or GeoPackage file and a target GeoPackage."""

import os

from qgis.PyQt.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class ImportDialog(QDialog):
    """Collect the input file and output GeoPackage path."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Drainworks — import sewer data")
        self.input_path = QLineEdit()
        self.output_path = QLineEdit()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("RIBX or GeoPackage to import:"))
        layout.addLayout(self._row(self.input_path, self._browse_input))
        layout.addWidget(QLabel("Target GeoPackage (created/overwritten):"))
        layout.addLayout(self._row(self.output_path, self._browse_output))

        buttons = QHBoxLayout()
        ok = QPushButton("Import")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _row(self, line_edit, handler):
        row = QHBoxLayout()
        browse = QPushButton("Browse…")
        browse.clicked.connect(handler)
        row.addWidget(line_edit)
        row.addWidget(browse)
        return row

    def _browse_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select RIBX or GeoPackage", "", "Sewer data (*.ribx *.xml *.gpkg)"
        )
        if path:
            self.input_path.setText(path)
            if not self.output_path.text():
                base = os.path.splitext(path)[0]
                self.output_path.setText(base + ".gpkg")

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Target GeoPackage", "", "GeoPackage (*.gpkg)")
        if path:
            self.output_path.setText(path)

    def values(self):
        """Return (input_path, output_gpkg_path) as strings."""
        return self.input_path.text(), self.output_path.text()
