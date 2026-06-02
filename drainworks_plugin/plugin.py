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
        self.manhole_layer = None
        self.pipe_layer = None
        self.gpkg_path = None
        self.side_view = None
        self.map_tool = None

    def initGui(self):  # noqa: N802 (QGIS-required name)
        """Create toolbar/menu actions. Called by QGIS on plugin load."""
        icon = QIcon(os.path.join(PLUGIN_DIR, "resources", "icon.svg"))
        action = QAction(icon, "Import sewer data…", self.iface.mainWindow())
        action.triggered.connect(self.on_import)
        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)

        traj = QAction(icon, "Pick trajectory (side-view)", self.iface.mainWindow())
        traj.triggered.connect(self.on_pick_trajectory)
        self.iface.addToolBarIcon(traj)
        self.iface.addPluginToMenu(self.menu, traj)
        self.actions.append(traj)

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
