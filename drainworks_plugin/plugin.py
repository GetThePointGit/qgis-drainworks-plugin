"""Main plugin object: builds a dedicated Drainworks toolbar and menu."""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

PLUGIN_DIR = os.path.dirname(__file__)
LOGO_PATH = os.path.join(PLUGIN_DIR, "resources", "logo.png")


class DrainworksPlugin:
    """Wires the plugin into the QGIS GUI."""

    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.menu = "&Drainworks"
        self.toolbar = None
        self.manhole_layer = None
        self.pipe_layer = None
        self.gpkg_path = None
        self.side_view = None
        self.map_tool = None

    def initGui(self):  # noqa: N802 (QGIS-required name)
        """Create the Drainworks toolbar, its buttons, and matching menu entries."""
        self.toolbar = self.iface.addToolBar("Drainworks")
        self.toolbar.setObjectName("DrainworksToolbar")
        # Show each button's label next to the logo so the buttons are legible.
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self._add_action("Importeren", self.on_import,
                         tooltip="Importeer riooldata (RIBX of GeoPackage)")
        self._add_action("Traject (side-view)", self.on_pick_trajectory,
                         tooltip="Kies een traject langs de riolering en toon het langsprofiel")
        self._add_action("Verloren berging", self.on_compute_loss,
                         tooltip="Bereken en toon de verloren berging")

    def _add_action(self, text, callback, tooltip=None):
        """Create an action with the Drainworks logo and register it on toolbar + menu."""
        action = QAction(QIcon(LOGO_PATH), text, self.iface.mainWindow())
        action.triggered.connect(callback)
        action.setToolTip(tooltip or text)
        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def unload(self):
        """Remove the toolbar, its actions, and menu entries. Called on unload."""
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
        self.actions = []
        if self.toolbar is not None:
            del self.toolbar
            self.toolbar = None

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
        self.manhole_layer = manhole_layer
        self.pipe_layer = pipe_layer
        self.gpkg_path = input_path if input_path.lower().endswith(".gpkg") else gpkg_path
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Imported {pipe_layer.featureCount()} pipes, "
            f"{manhole_layer.featureCount()} manholes.",
        )

    def on_pick_trajectory(self):
        """Activate the trajectory map tool and ensure the side-view dock exists."""
        if self.manhole_layer is None or self.gpkg_path is None:
            self.iface.messageBar().pushWarning("Drainworks", "Import data first.")
            return

        from qgis.PyQt.QtCore import Qt

        from drainworks_plugin.sideview.sideview_panel import SideViewPanel
        from drainworks_plugin.trajectory.map_tool import TrajectoryMapTool

        if self.side_view is None:
            self.side_view = SideViewPanel(self.iface.mainWindow())
            self.iface.mainWindow().addDockWidget(Qt.BottomDockWidgetArea, self.side_view)

        self.map_tool = TrajectoryMapTool(
            self.iface.mapCanvas(),
            self.manhole_layer,
            self.gpkg_path,
            self.side_view,
            self.iface.messageBar(),
        )
        self.iface.mapCanvas().setMapTool(self.map_tool)
        self.iface.messageBar().pushInfo(
            "Drainworks", "Click manholes to build a route. Right-click to reset."
        )

    def on_compute_loss(self):
        """Compute lost capacity and load the styled measurements layer."""
        if self.gpkg_path is None:
            self.iface.messageBar().pushWarning("Drainworks", "Import data first.")
            return
        from qgis.core import QgsProject, QgsVectorLayer

        from drainworks_plugin.lostcapacity.runner import compute_and_store
        from drainworks_plugin.styling.symbology import style_measurements_by_flooded

        try:
            n = compute_and_store(self.gpkg_path)
        except Exception as exc:
            self.iface.messageBar().pushCritical("Drainworks", f"Computation failed: {exc}")
            return

        layer = QgsVectorLayer(f"{self.gpkg_path}|layername=measurements", "Verloren berging", "ogr")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            style_measurements_by_flooded(layer)
        self.iface.messageBar().pushSuccess("Drainworks", f"Lost capacity computed for {n} points.")
