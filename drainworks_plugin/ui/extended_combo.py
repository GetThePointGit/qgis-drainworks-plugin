"""A filterable, searchable combo box.

Adapted from the legger plugin's ExtendedCombo
(views/legger_network_widget.py): an editable QComboBox whose completer filters
the list as you type, case-insensitively.
"""

from qgis.PyQt.QtCore import Qt, QSortFilterProxyModel
from qgis.PyQt.QtWidgets import QComboBox, QCompleter


class ExtendedCombo(QComboBox):
    """Editable combo with type-to-filter completion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

        self.completer = QCompleter(self)
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.pFilterModel = QSortFilterProxyModel(self)
        self.pFilterModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setPopup(self.view())
        self.setCompleter(self.completer)

        self.lineEdit().textEdited.connect(self.pFilterModel.setFilterFixedString)
        self.completer.activated.connect(self._on_completer_activated)

    def setModel(self, model):  # noqa: N802 (Qt override)
        """Set the combo model and wire it through the filter and completer."""
        super().setModel(model)
        self.pFilterModel.setSourceModel(model)
        self.completer.setModel(self.pFilterModel)

    def setModelColumn(self, column):  # noqa: N802 (Qt override)
        """Set which column the completer and filter operate on."""
        self.completer.setCompletionColumn(column)
        self.pFilterModel.setFilterKeyColumn(column)
        super().setModelColumn(column)

    def view(self):
        """Return the completer's popup list view."""
        return self.completer.popup()

    def _on_completer_activated(self, text):
        """Select the matching combo item when a completion is chosen."""
        if text:
            index = self.findText(text)
            if index >= 0:
                self.setCurrentIndex(index)
