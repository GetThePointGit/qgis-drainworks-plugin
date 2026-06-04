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
        self._import_task = None  # keeps the running ImportTask alive
        self._busy = None         # the messageBar busy item, if any

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
            try:
                self.dock.visibilityChanged.disconnect(self._on_dock_visibility)
            except (TypeError, RuntimeError):
                pass
            self.dock.teardown()
            self.iface.removeDockWidget(self.dock)
            self.dock.setParent(None)
            self.dock.deleteLater()
            self.dock = None
        if self.action is not None:
            self.iface.removePluginMenu(self.menu, self.action)
            self.action = None
        if self.toolbar is not None:
            del self.toolbar
            self.toolbar = None

    # ------------------------------------------------------------- actions
    def reload_pipeline_layers(self):
        """Reload + restyle the GeoPackage layers (after enrich/berging)."""
        if not self.gpkg_path:
            return
        from drainworks_plugin.io.import_controller import load_pipeline_layers
        manhole_layer, pipe_layer, group, _segments = load_pipeline_layers(self.gpkg_path)
        self.manhole_layer = manhole_layer
        self.pipe_layer = pipe_layer
        self.layer_group = group
        if self.dock is not None:
            self.dock.manhole_layer = manhole_layer
            self.dock.pipe_layer = pipe_layer
        self.iface.mapCanvas().refresh()

    def on_import(self):
        """Open the import dialog, import the file, and feed the dock."""
        from qgis.PyQt.QtWidgets import QDialog

        from drainworks_plugin.ui.import_dialog import ImportDialog

        dialog = ImportDialog(self.iface.mainWindow())
        if dialog.exec_() != QDialog.Accepted:
            return
        input_path, meas_path, gpkg_path = dialog.values()
        if not input_path:
            return
        # Opening an existing GeoPackage is cheap (no parsing) -> load directly.
        if input_path.lower().endswith(".gpkg"):
            try:
                self._load_and_show(input_path)
            except Exception as exc:  # surface to the user, don't crash QGIS
                self.iface.messageBar().pushCritical("Drainworks", f"Importeren mislukt: {exc}")
            return
        # Parsing RIBX/SUFRIB + writing the base GeoPackage is heavy -> run it in a
        # QgsTask (progress bar, no GUI freeze); load the layers in the callback.
        from qgis.core import QgsApplication

        from drainworks_plugin.pipeline.tasks import ImportTask

        from drainworks_plugin.ui.busy import start_busy

        self._import_task = ImportTask(input_path, meas_path or None, gpkg_path,
                                       on_done=self._import_done)
        self._busy = start_busy(self.iface, "Importeren…")
        QgsApplication.taskManager().addTask(self._import_task)

    def _import_done(self, task):
        """Main-thread callback after the import task finishes."""
        from drainworks_plugin.ui.busy import stop_busy
        stop_busy(self.iface, self._busy)
        self._busy = None
        self._import_task = None
        if task.error is not None:
            self.iface.messageBar().pushCritical("Drainworks", f"Importeren mislukt: {task.error}")
            return
        try:
            self._load_and_show(str(task.result))
        except Exception as exc:
            self.iface.messageBar().pushCritical("Drainworks", f"Laden mislukt: {exc}")

    def _load_and_show(self, gpkg_out):
        """Load the GeoPackage layers, zoom, and hand them to the dock."""
        from drainworks_plugin.io.import_controller import load_pipeline_layers

        manhole_layer, pipe_layer, group, _segments = load_pipeline_layers(gpkg_out)
        self.manhole_layer = manhole_layer
        self.pipe_layer = pipe_layer
        self.layer_group = group
        self.gpkg_path = gpkg_out
        self._zoom_to_layers([pipe_layer, manhole_layer])
        if self.dock is not None:
            self.dock.set_data(manhole_layer, pipe_layer, self.gpkg_path)
            self.dock.show()
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Geïmporteerd: {pipe_layer.featureCount()} leidingen, "
            f"{manhole_layer.featureCount()} putten.",
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

