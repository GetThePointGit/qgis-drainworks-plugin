"""The main Drainworks dock widget.

Hosts the three pipeline step buttons (import / enrich / lost storage), a sink
selector with a per-row-delete table, a contextual trajectory edit bar, and the
embedded pyqtgraph side-view. It also owns the trajectory state and draws the
route + lettered markers on the canvas.
"""

import os
import string

from qgis.core import QgsPointXY
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from drainworks_plugin.sideview.profile_builder import build_profile
from drainworks_plugin.sideview.sideview_widget import SideViewWidget
from drainworks_plugin.ui.extended_combo import ExtendedCombo

RESOURCES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources")
ICONS = os.path.join(RESOURCES, "icons")
LETTERS = string.ascii_uppercase


def _icon(name):
    """Return a QIcon for an SVG/PNG in the plugin's icons resource folder."""
    return QIcon(os.path.join(ICONS, name))


class DrainworksDock(QDockWidget):
    """Main control panel; docked on the right."""

    def __init__(self, plugin):
        super().__init__("Drainworks", plugin.iface.mainWindow())
        self.setObjectName("DrainworksDock")
        self.plugin = plugin
        self.iface = plugin.iface

        # Data / trajectory state.
        self.manhole_layer = None
        self.pipe_layer = None
        self.gpkg_path = None
        self.network = None
        self.pipes_by_code = {}
        self.pipe_geoms = {}
        self.manhole_points = {}
        self.measurements_by_pipe = {}
        self._segments_by_pipe = {}     # cached; refreshed on load + after each step
        self._last_hover_code = None    # avoid re-rendering the preview every pixel
        self._canvas_move_connected = False
        self._manholes_by_code = {}
        self.route_polyline = []  # [(cumulative_dist, QgsPointXY)] for graph<->map hover
        self.waypoints = []
        self.active_code = None
        from drainworks_plugin.trajectory.history import WaypointHistory
        self.history = WaypointHistory()
        self.sinks = set()
        from drainworks_plugin.pipeline.state import PipelineState
        self.state = PipelineState()
        self.active_task = None  # the running QgsTask, if any
        self._busy = None        # the messageBar busy item, if any
        self.map_tool = None
        self.graphics = None
        from drainworks_plugin.styling import views as _v
        self.style_modes = {
            "pipe_color": _v.PIPE_COLOR_DEFAULT, "pipe_width": _v.PIPE_WIDTH_DEFAULT,
            "pipe_label": _v.PIPE_LABEL_NONE, "manhole_color": _v.MANHOLE_COLOR_DEFAULT,
            "manhole_label": _v.MANHOLE_LABEL_NONE,
            "segment_color": _v.SEGMENT_COLOR_FLOODED,
        }

        self._build_ui()
        self.side_view.apply_settings(self._load_sideview_settings())

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        """Build the dock layout: toolbar, step cards, sink table, trajectory bar, side-view."""
        from qgis.gui import QgsCollapsibleGroupBox

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # --- Main toolbar. ---
        actions = QHBoxLayout()
        self.btn_import = self._tool_button("Importeren", "import.svg", self._on_import)
        self.btn_import.setToolTip("Importeer RIBX/SUFRIB of een bestaande GeoPackage")
        self.btn_traj = self._tool_button("Traject", "trajectory.svg", self._on_traj_toggled,
                                          checkable=True)
        self.btn_traj.setToolTip("Stel een traject samen door putten op de kaart te klikken")
        self.btn_style = self._tool_button("Opmaak", "brush.svg", self._on_style)
        self.btn_style.setToolTip("Pas de kaartopmaak van leidingen en putten aan")
        self.btn_settings = self._tool_button("Zijaanzicht", "gear.svg",
                                              self._on_sideview_settings)
        self.btn_settings.setToolTip("Instellingen voor het zijaanzicht (langsprofiel)")
        for b in (self.btn_import, self.btn_traj, self.btn_style, self.btn_settings):
            actions.addWidget(b)
        actions.addStretch()
        left_layout.addLayout(actions)

        # --- File info. ---
        self.file_label = QLabel("Geen data geladen")
        self.file_label.setStyleSheet("color: #666;")
        self.file_label.setWordWrap(True)
        left_layout.addWidget(self.file_label)

        # --- Card 1: enrich. ---
        card1 = QgsCollapsibleGroupBox("1. Basisdata verrijken")
        c1 = QVBoxLayout(card1)
        self.btn_enrich = QPushButton(_icon("lost_capacity.svg"), "Verrijk basisdata")
        self.btn_enrich.setToolTip(
            "Valideer, bereken hoogtes en bouw segmenten uit de basisdata")
        self.btn_enrich.clicked.connect(self._on_enrich)
        self.btn_enrich_settings = QToolButton()
        self.btn_enrich_settings.setIcon(_icon("gear.svg"))
        self.btn_enrich_settings.setIconSize(QSize(20, 20))
        self.btn_enrich_settings.setAutoRaise(True)
        self.btn_enrich_settings.setToolTip("Instellingen verrijken")
        self.btn_enrich_settings.clicked.connect(self._on_enrich_settings)
        row1 = QHBoxLayout()
        row1.addWidget(self.btn_enrich, 1)
        row1.addWidget(self.btn_enrich_settings)
        c1.addLayout(row1)
        self.enrich_status = QLabel("")
        c1.addWidget(self.enrich_status)
        self.enrich_summary = QLabel("")
        self.enrich_summary.setStyleSheet("color: #666;")
        self.enrich_summary.setWordWrap(True)
        c1.addWidget(self.enrich_summary)
        left_layout.addWidget(card1)

        # --- Card 2: berging. ---
        card2 = QgsCollapsibleGroupBox("2. Verloren berging")
        c2 = QVBoxLayout(card2)
        c2.addWidget(QLabel("Sinks (uitstroompunten):"))
        sink_row = QHBoxLayout()
        self.sink_combo = ExtendedCombo()
        add_sink = QToolButton()
        add_sink.setText("+")
        add_sink.setToolTip("Voeg de geselecteerde put toe als sink")
        add_sink.clicked.connect(self._on_add_sink)
        self.btn_sink_map = QPushButton("Kaart")
        self.btn_sink_map.setCheckable(True)
        self.btn_sink_map.setToolTip("Kies een sink-put door deze op de kaart aan te klikken")
        self.btn_sink_map.clicked.connect(self._on_sink_map_toggled)
        sink_row.addWidget(self.sink_combo, 1)
        sink_row.addWidget(add_sink)
        sink_row.addWidget(self.btn_sink_map)
        c2.addLayout(sink_row)
        self.sink_table = QTableWidget(0, 3)
        self.sink_table.setHorizontalHeaderLabels(["Sink", "bodem (m)", ""])
        self.sink_table.verticalHeader().setVisible(False)
        self.sink_table.setColumnWidth(1, 70)
        self.sink_table.setColumnWidth(2, 30)
        self.sink_table.setMaximumHeight(120)
        c2.addWidget(self.sink_table)
        self.btn_loss = QPushButton(_icon("lost_capacity.svg"), "Bereken verloren berging")
        self.btn_loss.setToolTip(
            "Bereken de verloren berging op de segmenten met de gekozen sinks")
        self.btn_loss.clicked.connect(self._on_loss)
        self.btn_loss_settings = QToolButton()
        self.btn_loss_settings.setIcon(_icon("gear.svg"))
        self.btn_loss_settings.setIconSize(QSize(20, 20))
        self.btn_loss_settings.setAutoRaise(True)
        self.btn_loss_settings.setToolTip("Instellingen verloren berging")
        self.btn_loss_settings.clicked.connect(self._on_loss_settings)
        row2 = QHBoxLayout()
        row2.addWidget(self.btn_loss, 1)
        row2.addWidget(self.btn_loss_settings)
        c2.addLayout(row2)
        self.loss_status = QLabel("")
        c2.addWidget(self.loss_status)
        self.loss_total = QLabel("")
        self.loss_total.setStyleSheet("color: #2c7fb8; font-weight: bold;")
        c2.addWidget(self.loss_total)
        left_layout.addWidget(card2)

        left_layout.addStretch(1)
        left.setMaximumWidth(360)

        # --- Right: trajectory bar (above) + longitudinal profile. ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self.traj_bar = QWidget()
        traj_layout = QHBoxLayout(self.traj_bar)
        traj_layout.setContentsMargins(0, 0, 0, 0)
        traj_layout.addWidget(QLabel("Traject:"))
        self.btn_traj_downstream = self._text_tool_button(
            "Stroomafw.", "downstream.svg", self._on_downstream,
            "Verleng het traject stroomafwaarts vanaf het laatste punt")
        self.btn_traj_delmode = self._text_tool_button(
            "Verwijdermodus", "delete_mode.svg", None,
            "Klik daarna één put aan om die uit het traject te verwijderen", checkable=True)
        self.btn_traj_clear = self._text_tool_button(
            "Wis", "clear.svg", self._on_reset, "Wis het hele traject")
        self.btn_traj_undo = self._text_tool_button(
            "Ongedaan", "undo.svg", self._on_undo, "Maak de laatste wijziging ongedaan")
        self.btn_traj_redo = self._text_tool_button(
            "Opnieuw", "redo.svg", self._on_redo, "Voer de ongedane wijziging opnieuw uit")
        self.btn_traj_done = self._text_tool_button(
            "Klaar", "check.svg", self._on_traj_done, "Sluit de trajectkeuze af")
        for b in (self.btn_traj_downstream, self.btn_traj_delmode, self.btn_traj_clear,
                  self.btn_traj_undo, self.btn_traj_redo, self.btn_traj_done):
            traj_layout.addWidget(b)
        traj_layout.addStretch()
        self.volume_label = QLabel("")
        self.volume_label.setStyleSheet("color: #2c7fb8; font-weight: bold;")
        traj_layout.addWidget(self.volume_label)
        self.traj_bar.setVisible(False)
        right_layout.addWidget(self.traj_bar)

        self.side_view = SideViewWidget()
        self.side_view.hovered.connect(self._on_graph_hover)
        right_layout.addWidget(self.side_view, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 760])
        self.setWidget(splitter)
        self._set_data_enabled(False)

    SV_SETTINGS_KEY = "drainworks/sideview"

    def _load_sideview_settings(self):
        """Load the side-view settings from QgsSettings as a SideViewSettings object."""
        import json
        from qgis.core import QgsSettings
        from drainworks_plugin.sideview.settings import SideViewSettings
        raw = QgsSettings().value(self.SV_SETTINGS_KEY, "", type=str)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        return SideViewSettings.from_dict(data)

    def _on_sideview_settings(self):
        """Open the side-view settings dialog and persist + apply the result on accept."""
        import json
        from qgis.core import QgsSettings
        from qgis.PyQt.QtWidgets import QDialog
        from drainworks_plugin.ui.sideview_settings_dialog import SideViewSettingsDialog
        current = self._load_sideview_settings()
        dialog = SideViewSettingsDialog(current, self.iface.mainWindow())
        if dialog.exec_() != QDialog.Accepted:
            return
        new = dialog.values()
        QgsSettings().setValue(self.SV_SETTINGS_KEY, json.dumps(new.to_dict()))
        self.side_view.apply_settings(new)

    ENRICH_SETTINGS_KEY = "drainworks/enrich"
    BERGING_SETTINGS_KEY = "drainworks/berging"
    ENRICH_DEFAULTS = {"correct_bob": True, "min_segment": 1.0, "bob_segment": 5.0}
    BERGING_DEFAULTS = {"resolution": "accurate"}

    def _load_json_settings(self, key, defaults):
        """Load a JSON settings dict from QgsSettings, merged onto ``defaults``.

        Parameters
        ----------
        key : str
            The QgsSettings key holding the JSON blob.
        defaults : dict
            Default values; only keys present here are taken from storage.

        Returns
        -------
        dict
            ``defaults`` updated with the stored (whitelisted) values.
        """
        import json
        from qgis.core import QgsSettings
        raw = QgsSettings().value(key, "", type=str)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        merged = dict(defaults)
        merged.update({k: v for k, v in data.items() if k in defaults})
        return merged

    def _save_json_settings(self, key, values):
        """Store ``values`` as a JSON blob under ``key`` in QgsSettings."""
        import json
        from qgis.core import QgsSettings
        QgsSettings().setValue(key, json.dumps(values))

    def _on_enrich_settings(self):
        """Open the enrich settings dialog and persist the result on accept."""
        from qgis.PyQt.QtWidgets import QDialog
        from drainworks_plugin.ui.enrich_settings_dialog import EnrichSettingsDialog
        current = self._load_json_settings(self.ENRICH_SETTINGS_KEY, self.ENRICH_DEFAULTS)
        dialog = EnrichSettingsDialog(current, self.iface.mainWindow())
        if dialog.exec_() == QDialog.Accepted:
            self._save_json_settings(self.ENRICH_SETTINGS_KEY, dialog.values())

    def _on_loss_settings(self):
        """Open the lost-storage (berging) settings dialog and persist on accept."""
        from qgis.PyQt.QtWidgets import QDialog
        from drainworks_plugin.ui.berging_settings_dialog import BergingSettingsDialog
        current = self._load_json_settings(self.BERGING_SETTINGS_KEY, self.BERGING_DEFAULTS)
        dialog = BergingSettingsDialog(current, self.iface.mainWindow())
        if dialog.exec_() == QDialog.Accepted:
            self._save_json_settings(self.BERGING_SETTINGS_KEY, dialog.values())

    def _tool_button(self, text, icon_name, slot, checkable=False):
        """Build a main-toolbar QToolButton with the icon above the text."""
        button = QToolButton()
        button.setText(text)
        button.setIcon(_icon(icon_name))
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setCheckable(checkable)
        button.setAutoRaise(True)
        button.clicked.connect(slot)
        return button

    def _text_tool_button(self, text, icon_name, slot, tooltip, checkable=False):
        """A QToolButton with the icon left of the text (trajectory bar style)."""
        button = QToolButton()
        button.setText(text)
        button.setIcon(_icon(icon_name))
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        button.setCheckable(checkable)
        button.setToolTip(tooltip)
        if slot is not None:
            button.clicked.connect(slot)
        return button

    def _set_data_enabled(self, enabled):
        """Enable/disable the data-dependent buttons and sink controls."""
        for widget in (self.btn_traj, self.btn_style, self.btn_loss, self.btn_enrich,
                       self.btn_enrich_settings, self.btn_loss_settings,
                       self.sink_combo, self.btn_sink_map):
            widget.setEnabled(enabled)

    # --------------------------------------------------------------- data
    def set_data(self, manhole_layer, pipe_layer, gpkg_path):
        """Called after an import: load the network and reset trajectory state."""
        from drainworks_plugin.io.geopackage_store import (
            read_manhole_points,
            read_manholes,
            read_pipes,
        )
        from drainworks_plugin.trajectory.graphics import TrajectoryGraphics
        from drainworks_plugin.trajectory.network import SewerNetwork

        self.manhole_layer = manhole_layer
        self.pipe_layer = pipe_layer
        self.gpkg_path = str(gpkg_path)

        from drainworks_plugin.io.geopackage_store import layer_counts
        counts = layer_counts(self.gpkg_path)
        self.file_label.setText(
            f"Bestand: {os.path.basename(self.gpkg_path)}\n"
            f"Putten {counts['manholes']} · Leidingen {counts['pipes']} · "
            f"Metingen {counts['measurements']}")

        pipes = read_pipes(self.gpkg_path)
        self.pipes_by_code = {p.code: p for p in pipes}
        self.network = SewerNetwork(pipes)
        self.manhole_points = read_manhole_points(self.gpkg_path)
        self.measurements_by_pipe = self._read_profile_for_sideview()
        self._segments_by_pipe = self._read_segments_by_pipe()
        self.pipe_geoms = {f["code"]: f.geometry() for f in pipe_layer.getFeatures()}

        # Sink combo + existing sinks.
        manholes = read_manholes(self.gpkg_path)
        self._manholes_by_code = {m.code: m for m in manholes}
        self.sink_combo.clear()
        self.sink_combo.addItems(sorted(m.code for m in manholes))
        self.sinks = {m.code for m in manholes if m.is_sink}
        self._update_sink_table()

        for lyr in (pipe_layer, manhole_layer):
            try:
                lyr.afterCommitChanges.connect(self._on_base_edited)
            except (AttributeError, TypeError):
                pass

        if self.graphics is None:
            self.graphics = TrajectoryGraphics(self.iface.mapCanvas())
        if not self._canvas_move_connected:
            self.iface.mapCanvas().xyCoordinates.connect(self._on_canvas_move)
            self._canvas_move_connected = True
        self.waypoints = []
        self._update_sink_markers()
        self._rebuild()
        self._set_data_enabled(True)
        self._restore_pipeline_state()

    def _restore_pipeline_state(self):
        """Set step state + summaries + settings from the gpkg's dw_meta + fingerprint."""
        from drainworks_plugin.io.geopackage_store import (
            base_fingerprint, berging_fingerprint, read_meta)

        meta = read_meta(self.gpkg_path)
        enriched = bool(self._segments_by_pipe)   # already read in set_data
        # The fingerprint reads all measurements, so only compute it when there is a
        # stored enrich fingerprint to compare against (i.e. the gpkg was enriched).
        enrich_fresh = (
            enriched and bool(meta.get("enrich_fingerprint"))
            and meta["enrich_fingerprint"] == base_fingerprint(self.gpkg_path))
        berging_ran = "berging_total" in meta
        berging_fresh = (
            berging_ran and enrich_fresh
            and meta.get("berging_fingerprint")
            == berging_fingerprint(meta.get("enrich_fingerprint"), self.sinks))
        self.state.restore(enrich_ran=enriched, enrich_fresh=enrich_fresh,
                           berging_ran=berging_ran, berging_fresh=berging_fresh)

        s = meta.get("enrich_summary") or {}
        if enriched and enrich_fresh:
            self.enrich_summary.setText(
                f"{s.get('n_segments', 0)} segmenten · {s.get('n_errors', 0)} fouten · "
                f"{s.get('n_warnings', 0)} waarschuwingen")
        else:
            self.enrich_summary.setText("")
        if berging_fresh:
            self.loss_total.setText(
                f"Totaal verloren berging: {meta.get('berging_total', 0.0):.2f} m³")
        else:
            self.loss_total.setText("")

        if meta.get("enrich_settings"):
            self._save_json_settings(self.ENRICH_SETTINGS_KEY, meta["enrich_settings"])
        if meta.get("berging_settings"):
            self._save_json_settings(self.BERGING_SETTINGS_KEY, meta["berging_settings"])
        self._refresh_step_buttons()

    # ------------------------------------------------------------ actions
    def _on_import(self):
        """Handle the Import button: delegate to the plugin's import flow."""
        self.plugin.on_import()

    def _on_base_edited(self):
        """Layer edits committed: mark enrich/berging stale."""
        self.state.mark_base_edited()
        self._refresh_step_buttons()

    def _read_profile_for_sideview(self):
        """Read the profile layer into {code: [dict(dist,bob,obb,flooded_pct,water_level)]}."""
        if not self.gpkg_path:
            return {}
        from drainworks_plugin.io.geopackage_store import read_profile
        out = {}
        for code, points in read_profile(self.gpkg_path).items():
            out[code] = [{"dist": p.dist, "bob": p.bob, "obb": p.obb,
                          "flooded_pct": p.flooded_pct, "water_level": p.water_level}
                         for p in points]
        return out

    def _reload_profile(self):
        """Re-read the profile layer for the side-view and rebuild the route + graphics."""
        self.measurements_by_pipe = self._read_profile_for_sideview()
        self._rebuild()

    def _on_enrich(self):
        """Step 2: enrich the (possibly edited) base data, off-thread."""
        if not self.gpkg_path:
            self.iface.messageBar().pushWarning("Drainworks", "Importeer eerst data.")
            return
        from drainworks_plugin.pipeline.tasks import EnrichTask

        s = self._load_json_settings(self.ENRICH_SETTINGS_KEY, self.ENRICH_DEFAULTS)
        task = EnrichTask(self.gpkg_path,
                          correct_bob=s["correct_bob"],
                          min_segment=s["min_segment"],
                          bob_segment=s["bob_segment"],
                          on_done=self._enrich_done)
        self._run_task(task)

    def _enrich_done(self, task):
        """Enrich task callback: clear busy, report errors, refresh summary and layers."""
        from drainworks_plugin.ui.busy import stop_busy
        stop_busy(self.iface, self._busy)
        self._busy = None
        if task.error is not None:
            self.iface.messageBar().pushCritical("Drainworks", f"Verrijken mislukt: {task.error}")
            self.active_task = None
            self._refresh_step_buttons()
            return
        self.state.mark_enriched()
        s = task.result or {}
        self.enrich_summary.setText(
            f"{s.get('n_segments', 0)} segmenten · {s.get('n_errors', 0)} fouten · "
            f"{s.get('n_warnings', 0)} waarschuwingen")
        self.plugin.reload_pipeline_layers()
        self._reload_profile()
        self._segments_by_pipe = self._read_segments_by_pipe()
        self._refresh_step_buttons()
        self.active_task = None
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Verrijkt: {s.get('n_segments', 0)} segmenten, "
            f"{s.get('n_errors', 0)} fouten, {s.get('n_warnings', 0)} waarschuwingen.")

    def _on_loss(self):
        """Step 3: compute lost storage with the chosen sinks, off-thread."""
        if not self.gpkg_path:
            self.iface.messageBar().pushWarning("Drainworks", "Importeer eerst data.")
            return
        if not self.sinks:
            self.iface.messageBar().pushWarning("Drainworks", "Kies eerst minimaal één sink.")
            return
        if self.state.enrich_stale:
            self.iface.messageBar().pushWarning(
                "Drainworks", "Verrijk eerst de basisdata (stap 2).")
            return
        from drainworks_plugin.io.geopackage_store import set_sinks
        from drainworks_plugin.pipeline.tasks import BergingTask

        set_sinks(self.gpkg_path, self.sinks)
        resolution = self._load_json_settings(self.BERGING_SETTINGS_KEY,
                                              self.BERGING_DEFAULTS)["resolution"]
        task = BergingTask(self.gpkg_path, resolution=resolution, on_done=self._loss_done)
        self._run_task(task)

    def _loss_done(self, task):
        """Berging task callback: clear busy, report errors, show total and refresh."""
        from drainworks_plugin.ui.busy import stop_busy
        stop_busy(self.iface, self._busy)
        self._busy = None
        if task.error is not None:
            self.iface.messageBar().pushCritical("Drainworks", f"Berekening mislukt: {task.error}")
            self.active_task = None
            self._refresh_step_buttons()
            return
        from drainworks_plugin.io.geopackage_store import total_lost_volume
        self.state.mark_berging_computed()
        self.loss_total.setText(
            f"Totaal verloren berging: {total_lost_volume(self.gpkg_path):.2f} m³")
        self.plugin.reload_pipeline_layers()
        self._segments_by_pipe = self._read_segments_by_pipe()
        self._refresh_step_buttons()
        self._rebuild()
        self.active_task = None
        self.iface.messageBar().pushSuccess(
            "Drainworks", f"Verloren berging berekend ({task.result} segmenten).")

    def _run_task(self, task):
        """Submit a QgsTask to the task manager, disabling the step buttons."""
        from qgis.core import QgsApplication

        from drainworks_plugin.ui.busy import start_busy

        self.active_task = task
        self._busy = start_busy(self.iface, task.description() + "…")
        for btn in (self.btn_enrich, self.btn_loss):
            btn.setEnabled(False)
        QgsApplication.taskManager().addTask(task)

    def _refresh_step_buttons(self):
        """Re-enable + relabel the step buttons and status labels from PipelineState."""
        has = self.gpkg_path is not None
        self.btn_enrich.setEnabled(has)
        self.btn_loss.setEnabled(has)
        self.btn_enrich.setText(self.state.enrich_label())
        self.btn_enrich.setStyleSheet(
            "color: #c54141; font-weight: bold;"
            if self.state.enrich_stale and self.state.enrich_ran else "")
        self.btn_loss.setText(self.state.berging_label())
        self.btn_loss.setStyleSheet(
            "color: #c54141; font-weight: bold;"
            if self.state.berging_stale and self.state.berging_ran else "")
        self._set_status(self.enrich_status, self.state.enrich_ran,
                         self.state.enrich_stale, "verrijk opnieuw")
        self._set_status(self.loss_status, self.state.berging_ran,
                         self.state.berging_stale, "herbereken")

    def _set_status(self, label, ran, stale, action):
        """Update an up-to-date indicator label."""
        if not ran:
            label.setText("nog niet uitgevoerd")
            label.setStyleSheet("color: #666;")
        elif stale:
            label.setText(f"⚠ verouderd — {action}")
            label.setStyleSheet("color: #c5841f; font-weight: bold;")
        else:
            label.setText("✓ actueel")
            label.setStyleSheet("color: #2e7d32;")

    def _on_style(self):
        """Handle the Opmaak button: open the style dialog and apply the chosen styles."""
        if self.pipe_layer is None or self.manhole_layer is None:
            self.iface.messageBar().pushWarning("Drainworks", "Importeer eerst data.")
            return
        from drainworks_plugin.styling.views import (
            apply_manhole_style, apply_pipe_style, apply_segment_style)
        from drainworks_plugin.ui.style_dialog import StyleDialog
        from qgis.PyQt.QtWidgets import QDialog

        dialog = StyleDialog(self.style_modes, self.iface.mainWindow())
        if dialog.exec_() != QDialog.Accepted:
            return
        self.style_modes = dialog.values()
        apply_pipe_style(self.pipe_layer, self.style_modes["pipe_color"],
                         self.style_modes["pipe_width"], self.style_modes["pipe_label"])
        apply_manhole_style(self.manhole_layer, self.style_modes["manhole_color"],
                            self.style_modes["manhole_label"])
        from qgis.core import QgsProject
        for seg_layer in QgsProject.instance().mapLayersByName("Segmenten"):
            apply_segment_style(seg_layer, self.style_modes["segment_color"])
            self.iface.layerTreeView().refreshLayerSymbology(seg_layer.id())
        self.iface.mapCanvas().refresh()
        self.iface.layerTreeView().refreshLayerSymbology(self.pipe_layer.id())
        self.iface.layerTreeView().refreshLayerSymbology(self.manhole_layer.id())

    def _on_downstream(self):
        """Extend the trajectory downstream from the last chosen put."""
        if self.network is None:
            return
        if not self.waypoints:
            self.iface.messageBar().pushInfo(
                "Drainworks", "Kies eerst een startput (Traject) om stroomafwaarts te lopen."
            )
            return
        path = self.network.downstream_path(self.waypoints[-1])
        if len(path) < 2:
            self.iface.messageBar().pushInfo(
                "Drainworks", "Geen aflopende leiding gevonden vanaf deze put."
            )
            return
        for code in path[1:]:
            self.waypoints.append(code)
        self.active_code = self.waypoints[-1]
        self._commit_waypoints()

    def _on_traj_done(self):
        """Finish trajectory editing: turn the Traject tool off."""
        self.btn_traj.setChecked(False)
        self._on_traj_toggled(False)

    def _on_traj_toggled(self, checked):
        """Toggle the trajectory tool: show/hide the bar and (de)activate the map tool."""
        self.traj_bar.setVisible(checked)
        canvas = self.iface.mapCanvas()
        if checked:
            self.btn_sink_map.setChecked(False)
            self._activate_tool(self._on_pick, self._on_reset, editing=True)
            self._sync_traj_buttons()
            canvas.viewport().installEventFilter(self)
        else:
            self.btn_traj_delmode.setChecked(False)
            self._clear_tool()
            canvas.viewport().removeEventFilter(self)
            if self.graphics is not None:
                self.graphics.set_hover(None)
            self._last_hover_code = None
        self._update_side_view()
        self._update_graphics()

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        """Revert the live preview to the committed trajectory when the mouse leaves the canvas."""
        from qgis.PyQt.QtCore import QEvent
        if event.type() == QEvent.Leave and self.btn_traj.isChecked():
            if self.graphics is not None:
                self.graphics.set_hover(None)
            self._update_side_view()   # revert graph to the committed trajectory
            self._update_graphics()    # revert map to the committed trajectory
        return super().eventFilter(obj, event)

    def _on_sink_map_toggled(self, checked):
        """Toggle map-based sink picking; mutually exclusive with the trajectory tool."""
        if checked:
            self.btn_traj.setChecked(False)  # exclusive with trajectory
            self._activate_tool(self._on_sink_picked, on_reset=lambda: None)
        else:
            self._clear_tool()

    def _activate_tool(self, on_pick, on_reset, editing=False):
        """Set a TrajectoryMapTool on the canvas with the given pick/reset callbacks.

        Parameters
        ----------
        on_pick : callable
            Called with a manhole code when a put is clicked.
        on_reset : callable
            Called when the tool is reset (right/double click).
        editing : bool, optional
            When True, enables ctrl/right-click delete (trajectory editing only).
        """
        from drainworks_plugin.trajectory.map_tool import TrajectoryMapTool

        if self.manhole_layer is None:
            return
        canvas = self.iface.mapCanvas()
        if self.map_tool is not None:
            canvas.unsetMapTool(self.map_tool)
        # ctrl/right-click delete only applies to trajectory editing, not sink-pick.
        # (Moving a point is done via the placement model: select it, then click.)
        ctrl_pick = self._on_ctrl_pick if editing else None
        self.map_tool = TrajectoryMapTool(canvas, self.manhole_layer, on_pick, on_reset,
                                          on_move=self._on_map_hover,
                                          on_ctrl_pick=ctrl_pick)
        canvas.setMapTool(self.map_tool)

    def _clear_tool(self):
        """Unset and drop the active canvas map tool, if any."""
        if self.map_tool is not None:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None

    # ------------------------------------------------------------- sinks
    def _on_add_sink(self):
        """Add the put currently selected in the combo box as a sink."""
        self._add_sink(self.sink_combo.currentText().strip())

    def _on_sink_picked(self, code):
        """Add a map-clicked put as a sink, then turn the one-shot map-pick mode off."""
        self._add_sink(code)
        # One-shot: turn the map-pick button off after each chosen sink.
        self.btn_sink_map.setChecked(False)
        self._clear_tool()

    def _add_sink(self, code):
        """Add ``code`` to the sink set (if it is a known put) and apply the change."""
        if code and code in self.manhole_points:
            self.sinks.add(code)
            self._apply_sinks()

    def _update_sink_table(self):
        """Rebuild the sink table rows (code, bottom level, delete button) from ``self.sinks``."""
        from drainworks_plugin.io.geopackage_store import read_manhole_bottom_levels
        levels = read_manhole_bottom_levels(self.gpkg_path) if self.gpkg_path else {}
        codes = sorted(self.sinks)
        self.sink_table.setRowCount(len(codes))
        for i, code in enumerate(codes):
            self.sink_table.setItem(i, 0, QTableWidgetItem(code))
            bottom = levels.get(code)
            self.sink_table.setItem(i, 1, QTableWidgetItem(
                f"{bottom:.2f}" if bottom is not None else "—"))
            btn = QPushButton("✕")
            btn.setFixedWidth(28)
            btn.setToolTip("Verwijder deze sink")
            btn.clicked.connect(lambda _c, c=code: self._remove_sink(c))
            self.sink_table.setCellWidget(i, 2, btn)

    def _remove_sink(self, code):
        """Remove ``code`` from the sink set and apply the change."""
        self.sinks.discard(code)
        self._apply_sinks()

    def _apply_sinks(self):
        """Refresh the sink table + markers and mark the berging stale after a sink change."""
        # Sinks are persisted to the GeoPackage only when the berging is computed
        # (see _on_loss), so changing them just updates the UI + staleness state.
        self._update_sink_table()
        self._update_sink_markers()
        self.state.mark_sinks_changed()
        self._refresh_step_buttons()

    def _update_sink_markers(self):
        """Draw the sink markers on the canvas at each sink put's location."""
        if self.graphics is None:
            return
        points = [QgsPointXY(*self.manhole_points[c]) for c in self.sinks
                  if c in self.manhole_points]
        self.graphics.set_sink_markers(points)

    # -------------------------------------------------------- trajectory
    def _commit_waypoints(self, push=True):
        """Persist the current waypoints to history and rebuild everything."""
        if push:
            self.history.set(self.waypoints)
        self._sync_traj_buttons()
        self._rebuild()

    def _sync_traj_buttons(self):
        """Enable/disable the trajectory undo and redo buttons from the history state."""
        self.btn_traj_undo.setEnabled(self.history.can_undo())
        self.btn_traj_redo.setEnabled(self.history.can_redo())

    def _on_undo(self):
        """Undo the last trajectory change and rebuild from the restored waypoints."""
        self.waypoints = self.history.undo()
        self.active_code = self.waypoints[-1] if self.waypoints else None
        self._commit_waypoints(push=False)

    def _on_redo(self):
        """Redo the previously undone trajectory change and rebuild."""
        self.waypoints = self.history.redo()
        self.active_code = self.waypoints[-1] if self.waypoints else None
        self._commit_waypoints(push=False)

    def _on_ctrl_pick(self, code):
        """Ctrl/right-click on a put: remove it from the trajectory if present."""
        if code in self.waypoints:
            self.waypoints.remove(code)
            self.active_code = self.waypoints[-1] if self.waypoints else None
            self._commit_waypoints()

    def _on_pick(self, code):
        """Trajectory click on a put: delete it in delete-mode, otherwise place it."""
        if self.btn_traj_delmode.isChecked():
            if code in self.waypoints:
                self.waypoints.remove(code)
                self.active_code = self.waypoints[-1] if self.waypoints else None
                self.btn_traj_delmode.setChecked(False)
                self._commit_waypoints()
            return
        self._place(code)

    def _place(self, code):
        """Apply the placement model (select/insert/extend/move) for clicking `code`."""
        from drainworks_plugin.trajectory.placement import place_waypoint
        result = place_waypoint(self.network, self.waypoints, self.active_code, code)
        if result is None:
            self.iface.messageBar().pushWarning(
                "Drainworks", "Punt niet bereikbaar vanaf het traject.")
            return
        new_wps, new_active = result
        changed = new_wps != self.waypoints
        self.waypoints = new_wps
        self.active_code = new_active
        self._commit_waypoints(push=changed)

    def _preview(self, code):
        """Live preview (graph + map) of the trajectory as it would become with `code`."""
        if self.network is None:
            return
        preview, active = self.waypoints, self.active_code
        if code is not None:
            from drainworks_plugin.trajectory.placement import place_waypoint
            placed = place_waypoint(self.network, self.waypoints, self.active_code, code)
            if placed is not None:
                preview, active = placed
        self._render_side_view(preview)
        self._render_graphics(preview, active)

    def _on_map_hover(self, point):
        """Highlight the nearest put and drive the graph cursor from the route."""
        if self.graphics is None:
            return
        mupp = self.iface.mapCanvas().mapUnitsPerPixel()
        px, py = point.x(), point.y()
        # Nearest manhole within ~18 px -> highlight (the pick target).
        tol = mupp * 18
        nearest = None
        nearest_code = None
        for code, xy in self.manhole_points.items():
            d = ((xy[0] - px) ** 2 + (xy[1] - py) ** 2) ** 0.5
            if d <= tol:
                tol, nearest, nearest_code = d, xy, code
        self.graphics.set_hover(QgsPointXY(*nearest) if nearest else None)
        # While building a trajectory, live-preview it — but only when the nearest put
        # changes, so moving within/around the same put doesn't re-render.
        if self.btn_traj.isChecked() and nearest_code != self._last_hover_code:
            self._last_hover_code = nearest_code
            self._preview(nearest_code)

    def _on_canvas_move(self, point):
        """Any map mouse move: drive the graph cursor from the route (editing or not)."""
        if not self.route_polyline:
            self.side_view.set_cursor(None)
            return
        mupp = self.iface.mapCanvas().mapUnitsPerPixel()
        dist, offset = self._project_on_route(point.x(), point.y())
        self.side_view.set_cursor(dist if offset <= mupp * 14 else None)

    def _project_on_route(self, px, py):
        """Return (cumulative_dist, perpendicular_offset) of the nearest route point."""
        best_dist, best_off = 0.0, float("inf")
        for (c0, p0), (c1, p1) in zip(self.route_polyline, self.route_polyline[1:]):
            ax, ay, bx, by = p0.x(), p0.y(), p1.x(), p1.y()
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
            projx, projy = ax + dx * t, ay + dy * t
            off = ((px - projx) ** 2 + (py - projy) ** 2) ** 0.5
            if off < best_off:
                best_off = off
                best_dist = c0 + (c1 - c0) * t
        return best_dist, best_off

    def _on_reset(self):
        """Clear the whole trajectory and rebuild."""
        self.waypoints = []
        self.active_code = None
        self._commit_waypoints()

    def _rebuild(self):
        """Recompute route, refresh map graphics and side-view."""
        self._update_graphics()
        self._update_side_view()

    def _update_graphics(self):
        """Render the canvas graphics for the committed waypoints and active put."""
        self._render_graphics(self.waypoints, self.active_code)

    def _render_graphics(self, waypoints, active_code):
        """Draw lettered markers, the route geometry and the active-put highlight.

        Parameters
        ----------
        waypoints : list of str
            The ordered put codes to draw as lettered markers and route.
        active_code : str or None
            The currently active put to highlight, if it is in ``waypoints``.
        """
        if self.graphics is None:
            return
        labelled = []
        for i, code in enumerate(waypoints):
            xy = self.manhole_points.get(code)
            if xy is not None:
                letter = LETTERS[i] if i < len(LETTERS) else str(i + 1)
                labelled.append((letter, QgsPointXY(xy[0], xy[1])))
        self.graphics.set_markers(labelled)

        geoms = []
        if self.network is not None and len(waypoints) >= 2:
            try:
                route = self.network.route(waypoints)
                geoms = [self.pipe_geoms.get(c) for c in route.pipe_codes]
            except ValueError:
                geoms = []
        self.graphics.set_route(geoms)

        active = active_code if active_code in waypoints else None
        xy = self.manhole_points.get(active) if active else None
        self.graphics.set_active(QgsPointXY(*xy) if xy else None)

    def _update_side_view(self):
        """Render the side-view longitudinal profile for the committed waypoints."""
        self._render_side_view(self.waypoints)

    def _render_side_view(self, waypoints):
        """Rebuild the longitudinal profile, water overlay and volume label for a route.

        Parameters
        ----------
        waypoints : list of str
            The route to draw; may be a live preview differing from the committed
            ``self.waypoints``, in which case only committed pipes show measured
            water and contribute to the berging volume.
        """
        if self.network is None or len(waypoints) < 2:
            self.side_view.clear()
            self.volume_label.setText("")
            self.route_polyline = []
            return
        try:
            route = self.network.route(waypoints)
        except ValueError as exc:
            self.iface.messageBar().pushWarning("Drainworks", str(exc))
            self.side_view.clear()
            self.volume_label.setText("")
            self.route_polyline = []
            return
        # Pipes of the committed trajectory show the measured invert + water; pipes that
        # exist only in the live preview fall back to the straight BOB line (no water).
        committed_route = None
        committed_codes = set()
        if waypoints == self.waypoints:
            committed_route = route                 # common case: not a preview
            committed_codes = set(route.pipe_codes)
        elif len(self.waypoints) >= 2:
            try:
                committed_route = self.network.route(self.waypoints)
                committed_codes = set(committed_route.pipe_codes)
            except ValueError:
                committed_route = None
        measurements = {c: m for c, m in self.measurements_by_pipe.items() if c in committed_codes}
        profile = build_profile(route, self.pipes_by_code, measurements,
                                manholes_by_code=self._manholes_by_code)
        self.side_view.show_profile(profile)
        self.route_polyline = self._build_route_polyline(route)
        if committed_route is None:
            self.volume_label.setText("")
            return
        from drainworks_plugin.sideview.berging import route_berging
        water, volume = route_berging(committed_route, self.pipes_by_code, self._segments_by_pipe)
        # Accurate berging carries per-point water on the profile (show_profile draws
        # it); only draw the segment overlay when there is no per-point water (fast).
        if not any(v.water_level is not None for v in profile.vertices):
            self.side_view.show_water(water)
        self.volume_label.setText(f"Verloren berging: {volume:.2f} m³" if volume else "")

    def _read_segments_by_pipe(self):
        """Read the segments layer into ``{pipe_code: [segment_dict, ...]}``."""
        if not self.gpkg_path:
            return {}
        from drainworks_plugin.io.geopackage_store import read_segments
        by_pipe = {}
        for seg in read_segments(self.gpkg_path):
            by_pipe.setdefault(seg["pipe_code"], []).append(seg)
        return by_pipe

    def _build_route_polyline(self, route):
        """Return [(cumulative_dist, QgsPointXY)] along the oriented route geometry."""
        poly = []
        cumulative = 0.0
        prev = None
        for pipe_code, from_node in zip(route.pipe_codes, route.manholes):
            geom = self.pipe_geoms.get(pipe_code)
            pipe = self.pipes_by_code.get(pipe_code)
            if geom is None or pipe is None:
                continue
            pts = geom.asPolyline()
            if not pts:
                continue
            if pipe.manhole1 != from_node:
                pts = list(reversed(pts))
            for p in pts:
                if prev is not None:
                    cumulative += (((p.x() - prev.x()) ** 2 + (p.y() - prev.y()) ** 2) ** 0.5)
                poly.append((cumulative, p))
                prev = p
        return poly

    def _on_graph_hover(self, dist):
        """Show the map point matching the cursor distance on the graph."""
        if self.graphics is None:
            return
        if dist < 0 or not self.route_polyline:
            self.graphics.set_hover(None)
            return
        self.graphics.set_hover(self._point_at_distance(dist))

    def _point_at_distance(self, dist):
        """Return the map QgsPointXY at cumulative ``dist`` along the route polyline."""
        poly = self.route_polyline
        if not poly:
            return None
        if dist <= poly[0][0]:
            return poly[0][1]
        for (c0, p0), (c1, p1) in zip(poly, poly[1:]):
            if c0 <= dist <= c1:
                seg = c1 - c0
                t = 0.0 if seg == 0 else (dist - c0) / seg
                return QgsPointXY(p0.x() + (p1.x() - p0.x()) * t,
                                  p0.y() + (p1.y() - p0.y()) * t)
        return poly[-1][1]

    # ------------------------------------------------------------ teardown
    def deactivate_tool(self):
        """Unset the map tool, untoggle the traject/sink buttons and clear the hover."""
        if self.map_tool is not None:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None
        self.btn_traj.setChecked(False)
        self.btn_sink_map.setChecked(False)
        if self.graphics is not None:
            self.graphics.set_hover(None)
        self._last_hover_code = None

    def teardown(self):
        """Release the map tool and remove all canvas items (for plugin unload)."""
        self.deactivate_tool()
        if self._canvas_move_connected:
            try:
                self.iface.mapCanvas().xyCoordinates.disconnect(self._on_canvas_move)
            except (TypeError, RuntimeError):
                pass
            self._canvas_move_connected = False
        if self.graphics is not None:
            self.graphics.destroy()
            self.graphics = None
