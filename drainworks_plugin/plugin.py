"""Main plugin object: a logo toolbar button that toggles the Drainworks dock."""

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
        self.action = None
        self.toolbar = None
        self.menu = "&Drainworks"
        self.dock = None
        self.manhole_layer = None
        self.pipe_layer = None
        self.layer_group = None
        self.gpkg_path = None

    def initGui(self):  # noqa: N802 (QGIS-required name)
        """Create the toolbar toggle and the (hidden) dock. Called on load."""
        from drainworks_plugin.ui.dock import DrainworksDock

        self.dock = DrainworksDock(self)
        self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.dock)
        self.dock.hide()

        self.toolbar = self.iface.addToolBar("Drainworks")
        self.toolbar.setObjectName("DrainworksToolbar")
        self.action = QAction(QIcon(LOGO_PATH), "Drainworks", self.iface.mainWindow())
        self.action.setToolTip("Open/sluit het Drainworks-paneel")
        self.action.setCheckable(True)
        self.action.toggled.connect(self.dock.setVisible)
        self.dock.visibilityChanged.connect(self._on_dock_visibility)
        self.toolbar.addAction(self.action)
        self.iface.addPluginToMenu(self.menu, self.action)

    def _on_dock_visibility(self, visible):
        self.action.setChecked(visible)
        if not visible:
            self.dock.deactivate_tool()

    def unload(self):
        """Remove the dock, toolbar and menu entry. Called on unload."""
        if self.dock is not None:
            self.dock.deactivate_tool()
            self.dock.clear_graphics()
            self.iface.removeDockWidget(self.dock)
            self.dock = None
        if self.action is not None:
            self.iface.removePluginMenu(self.menu, self.action)
        if self.toolbar is not None:
            del self.toolbar
            self.toolbar = None

    # ------------------------------------------------------------- actions
    def on_import(self):
        """Open the import dialog, import the file, and feed the dock."""
        from qgis.PyQt.QtWidgets import QDialog

        from drainworks_plugin.io.import_controller import (
            import_ribx,
            load_geopackage_layers,
        )
        from drainworks_plugin.ui.import_dialog import ImportDialog

        dialog = ImportDialog(self.iface.mainWindow())
        if dialog.exec_() != QDialog.Accepted:
            return
        input_path, gpkg_path, correct_bob = dialog.values()
        if not input_path:
            return
        try:
            if input_path.lower().endswith(".gpkg"):
                manhole_layer, pipe_layer, group = load_geopackage_layers(input_path)
            else:
                manhole_layer, pipe_layer, group = import_ribx(
                    input_path, gpkg_path, correct_bob=correct_bob
                )
        except Exception as exc:  # surface to the user, don't crash QGIS
            self.iface.messageBar().pushCritical("Drainworks", f"Import failed: {exc}")
            return
        self.manhole_layer = manhole_layer
        self.pipe_layer = pipe_layer
        self.layer_group = group
        self.gpkg_path = input_path if input_path.lower().endswith(".gpkg") else gpkg_path
        self._zoom_to_layers([pipe_layer, manhole_layer])
        if self.dock is not None:
            self.dock.set_data(manhole_layer, pipe_layer, self.gpkg_path)
            self.dock.show()
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Imported {pipe_layer.featureCount()} pipes, "
            f"{manhole_layer.featureCount()} manholes.",
        )

    def _zoom_to_layers(self, layers):
        """Zoom the canvas to the combined extent of ``layers`` (CRS-aware)."""
        from qgis.core import QgsCoordinateTransform, QgsProject, QgsRectangle

        extent = QgsRectangle()
        extent.setMinimal()
        project = QgsProject.instance()
        dst_crs = project.crs()
        for layer in layers:
            if layer is None or layer.featureCount() == 0:
                continue
            layer_extent = layer.extent()
            if layer.crs() != dst_crs:
                xform = QgsCoordinateTransform(layer.crs(), dst_crs, project)
                layer_extent = xform.transformBoundingBox(layer_extent)
            extent.combineExtentWith(layer_extent)
        if extent.isNull() or extent.isEmpty():
            return
        extent.scale(1.1)  # small margin around the network
        canvas = self.iface.mapCanvas()
        canvas.setExtent(extent)
        canvas.refresh()

    def on_compute_loss(self, correct_bob=False):
        """Compute lost capacity and load the styled measurements layer."""
        if self.gpkg_path is None:
            self.iface.messageBar().pushWarning("Drainworks", "Import data first.")
            return
        from qgis.core import QgsVectorLayer

        from drainworks_plugin.io.import_controller import add_layer_to_group
        from drainworks_plugin.lostcapacity.runner import compute_and_store
        from drainworks_plugin.styling.symbology import style_berging_lines

        try:
            n = compute_and_store(self.gpkg_path, correct_bob=correct_bob)
        except Exception as exc:
            self.iface.messageBar().pushCritical("Drainworks", f"Computation failed: {exc}")
            return

        # Replace any previous berging layer, then load the aggregated lines.
        from qgis.core import QgsProject

        for lyr in QgsProject.instance().mapLayersByName("Verloren berging"):
            QgsProject.instance().removeMapLayer(lyr.id())
        layer = QgsVectorLayer(f"{self.gpkg_path}|layername=berging", "Verloren berging", "ogr")
        if layer.isValid():
            style_berging_lines(layer)
            add_layer_to_group(layer, self.layer_group, on_top=True)
        self.iface.messageBar().pushSuccess("Drainworks", f"Verloren berging berekend ({n} punten).")
