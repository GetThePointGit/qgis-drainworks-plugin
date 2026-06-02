"""Main plugin object: registers a toolbar button and menu entry."""

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

PLUGIN_DIR = os.path.dirname(__file__)


class DrainworksPlugin:
    """Wires the plugin into the QGIS GUI."""

    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.menu = "&Drainworks"

    def initGui(self):  # noqa: N802 (QGIS-required name)
        """Create toolbar/menu actions. Called by QGIS on plugin load."""
        icon = QIcon(os.path.join(PLUGIN_DIR, "resources", "icon.svg"))
        action = QAction(icon, "Import sewer data…", self.iface.mainWindow())
        action.triggered.connect(self.on_import)
        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)

    def unload(self):
        """Remove actions. Called by QGIS on plugin unload."""
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        self.actions = []

    def on_import(self):
        """Open the import dialog and import the selected file."""
        from qgis.PyQt.QtWidgets import QDialog

        from drainworks_plugin.io.import_controller import (
            import_ribx,
            load_geopackage_layers,
        )
        from drainworks_plugin.ui.import_dialog import ImportDialog

        dialog = ImportDialog(self.iface.mainWindow())
        if dialog.exec_() != QDialog.Accepted:
            return
        input_path, gpkg_path = dialog.values()
        if not input_path:
            return
        try:
            if input_path.lower().endswith(".gpkg"):
                manhole_layer, pipe_layer = load_geopackage_layers(input_path)
            else:
                manhole_layer, pipe_layer = import_ribx(input_path, gpkg_path)
        except Exception as exc:  # surface to the user, don't crash QGIS
            self.iface.messageBar().pushCritical("Drainworks", f"Import failed: {exc}")
            return
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Imported {pipe_layer.featureCount()} pipes, "
            f"{manhole_layer.featureCount()} manholes.",
        )
