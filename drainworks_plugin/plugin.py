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
        """Placeholder hook, replaced in Task 3."""
        self.iface.messageBar().pushInfo("Drainworks", "Import action (not wired yet).")
