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
        """Keep the toolbar toggle in sync; deactivate the tool when hidden."""
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

        if self._import_task is not None:  # an import is already running
            self.iface.messageBar().pushInfo("Drainworks", "Er loopt al een import.")
            return
        dialog = ImportDialog(self.iface.mainWindow())
        if dialog.exec_() != QDialog.Accepted:
            return
        input_path, meas_path, gpkg_path = dialog.values()
        if not input_path:
            return
        # Opening an existing GeoPackage is cheap (no parsing) -> load directly. It still
        # reads the whole network/profile/segments, which is slow for a large gpkg, so
        # show a (main-thread) loading bar driven via processEvents.
        if input_path.lower().endswith(".gpkg"):
            from drainworks_plugin.io.geopackage_store import check_base_schema
            problem = check_base_schema(input_path)
            if problem:  # incompatible/foreign gpkg -> clear message, no cryptic crash
                self.iface.messageBar().pushCritical("Drainworks", problem)
                return
            from qgis.PyQt.QtWidgets import QApplication

            from drainworks_plugin.ui.busy import start_progress

            busy = start_progress(self.iface, "GeoPackage laden…")

            def report(frac, label):
                busy.set_progress(frac * 100)
                busy.set_text(label)
                QApplication.processEvents()  # repaint the bar during the blocking load

            QApplication.processEvents()
            try:
                self._load_and_show(input_path, on_progress=report)
            except Exception as exc:  # surface to the user, don't crash QGIS
                self.iface.messageBar().pushCritical("Drainworks", f"Importeren mislukt: {exc}")
            finally:
                busy.stop()
            return
        # Parse RIBX/SUFRIB off-thread (QgsTask, GUI stays responsive); the GeoPackage
        # write happens on the MAIN thread in the callback, because writing/finalising a
        # large GeoPackage in a worker thread crashes QGIS on Windows.
        from qgis.core import QgsApplication

        from drainworks_plugin.pipeline.tasks import ImportTask

        from drainworks_plugin.ui.busy import start_progress

        self._import_task = ImportTask(input_path, meas_path or None, gpkg_path,
                                       on_done=self._import_done)
        self._busy = start_progress(self.iface, "Importeren…")
        # Parse fills 0..60% of the bar; the main-thread write fills 60..100%.
        self._import_task.progress.connect(self._on_import_parse_progress)
        QgsApplication.taskManager().addTask(self._import_task)

    def _on_import_parse_progress(self, pct, label):
        """Map the parse task's 0..100% onto the first 60% of the import bar."""
        if self._busy is not None:
            self._busy.set_progress(pct * 0.6)
            if label:
                self._busy.set_text(label)

    def _import_done(self, task):
        """Main-thread callback after the parse task finishes.

        Defers the GeoPackage write + layer loading one event-loop tick out of the
        ``QgsTask.finished()`` call stack (mutating the message bar there can crash
        QGIS). The write runs here, on the main thread (Windows-safe).
        """
        from qgis.PyQt.QtCore import QTimer

        error = task.error
        result = None if error is not None else task.result   # parsed BuildResult
        gpkg = task.gpkg_path
        QTimer.singleShot(0, lambda: self._import_finalize(error, result, gpkg))

    def _import_finalize(self, error, result, gpkg):
        """Write the GeoPackage on the main thread, then load (or report the error)."""
        if error is not None:
            self._finish_import_busy()
            self.iface.messageBar().pushCritical("Drainworks", f"Importeren mislukt: {error}")
            return
        from qgis.PyQt.QtWidgets import QApplication

        from drainworks_plugin.io.import_controller import write_base_from_result

        busy = self._busy

        def report(frac, label):
            if busy is not None:
                busy.set_progress(60 + 40 * frac)   # write = 60..100% of the bar
                busy.set_text(label)
            QApplication.processEvents()             # repaint during the blocking write

        try:
            gpkg_out = write_base_from_result(gpkg, result, on_progress=report)
        except Exception as exc:
            self._finish_import_busy()
            self.iface.messageBar().pushCritical("Drainworks", f"Wegschrijven mislukt: {exc}")
            return
        self._finish_import_busy()
        try:
            self._load_and_show(str(gpkg_out))
        except Exception as exc:
            self.iface.messageBar().pushCritical("Drainworks", f"Laden mislukt: {exc}")

    def _finish_import_busy(self):
        """Stop the import busy bar and clear the running-import state."""
        if self._busy is not None:
            self._busy.stop()
        self._busy = None
        self._import_task = None

    def _load_and_show(self, gpkg_out, on_progress=None):
        """Load the GeoPackage layers, zoom, and hand them to the dock.

        ``on_progress(fraction, label)`` (0..1), if given, reports load progress
        (layers → zoom → reading the data in the dock) for a loading bar.
        """
        from drainworks_plugin.io.import_controller import load_pipeline_layers

        def _p(frac, label):
            if on_progress is not None:
                on_progress(frac, label)

        _p(0.05, "Lagen laden…")
        manhole_layer, pipe_layer, group, _segments = load_pipeline_layers(gpkg_out)
        self.manhole_layer = manhole_layer
        self.pipe_layer = pipe_layer
        self.layer_group = group
        self.gpkg_path = gpkg_out
        _p(0.30, "Inzoomen…")
        self._zoom_to_layers([pipe_layer, manhole_layer])
        if self.dock is not None:
            # The dock reads the network/profile/segments; map its 0..1 into 0.35..1.0.
            self.dock.set_data(manhole_layer, pipe_layer, self.gpkg_path,
                               on_progress=lambda f, l: _p(0.35 + 0.65 * f, l))
            self.dock.show()
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Geïmporteerd: {pipe_layer.featureCount()} leidingen, "
            f"{manhole_layer.featureCount()} putten.",
        )

    def _zoom_to_layers(self, layers):
        """Zoom the canvas to the combined extent of ``layers`` (CRS-aware)."""
        from qgis.core import QgsCoordinateTransform, QgsProject, QgsRectangle

        project = QgsProject.instance()
        dst_crs = project.crs()
        extent = None
        for layer in layers:
            if layer is None or layer.featureCount() == 0:
                continue
            layer_extent = layer.extent()
            if layer.crs() != dst_crs:
                xform = QgsCoordinateTransform(layer.crs(), dst_crs, project)
                layer_extent = xform.transformBoundingBox(layer_extent)
            if extent is None:
                extent = QgsRectangle(layer_extent)
            else:
                extent.combineExtentWith(layer_extent)
        if extent is None or extent.isNull() or extent.isEmpty():
            return
        extent.scale(1.1)  # small margin around the network
        canvas = self.iface.mapCanvas()
        canvas.setExtent(extent)
        canvas.refresh()

