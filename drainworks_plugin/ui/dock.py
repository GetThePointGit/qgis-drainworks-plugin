"""The main Drainworks dock widget.

Hosts the action buttons (import / trajectory / lost capacity), a filterable
sink selector, the trajectory table (A, B, C … with manhole code, distance and a
delete button), and the embedded pyqtgraph side-view. It also owns the
trajectory state and draws the route + lettered markers on the canvas.
"""

import os
import string

from qgis.core import QgsPointXY
from qgis.PyQt.QtCore import Qt
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
        self._manholes_by_code = {}
        self.route_polyline = []  # [(cumulative_dist, QgsPointXY)] for graph<->map hover
        self.waypoints = []
        from drainworks_plugin.trajectory.history import WaypointHistory
        self.history = WaypointHistory()
        self.sinks = set()
        self.computed_sinks = None  # sinks at the last berging computation
        from drainworks_plugin.pipeline.state import PipelineState
        self.state = PipelineState()
        self.active_task = None  # the running QgsTask, if any
        self.map_tool = None
        self.graphics = None
        from drainworks_plugin.styling import views as _v
        self.style_modes = {
            "pipe_color": _v.PIPE_COLOR_DEFAULT, "pipe_width": _v.PIPE_WIDTH_DEFAULT,
            "pipe_label": _v.PIPE_LABEL_NONE, "manhole_color": _v.MANHOLE_COLOR_DEFAULT,
            "manhole_label": _v.MANHOLE_LABEL_NONE,
        }

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # Bottom dock: narrow controls on the left, longitudinal profile on the
        # right, split so the user can drag the divider.
        splitter = QSplitter(Qt.Horizontal)

        # --- Left column: controls (kept narrow). ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        actions = QHBoxLayout()
        self.btn_import = self._tool_button("Importeren", "import.svg", self._on_import)
        self.btn_traj = self._tool_button("Traject", "trajectory.svg", self._on_traj_toggled,
                                          checkable=True)
        self.btn_downstream = self._tool_button("Stroomafw.", "trajectory.svg",
                                                self._on_downstream)
        self.btn_style = self._tool_button("Opmaak", "lost_capacity.svg", self._on_style)
        actions.addWidget(self.btn_import)
        actions.addWidget(self.btn_traj)
        actions.addWidget(self.btn_downstream)
        actions.addWidget(self.btn_style)
        actions.addStretch()
        left_layout.addLayout(actions)

        # --- Pipeline step buttons (import -> enrich -> berging). ---
        steps = QHBoxLayout()
        self.btn_enrich = self._tool_button("Verrijk basisdata", "lost_capacity.svg",
                                            self._on_enrich)
        steps.addWidget(self.btn_enrich)
        steps.addStretch()
        left_layout.addLayout(steps)

        from qgis.PyQt.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox
        settings = QHBoxLayout()
        self.chk_correct_bob = QCheckBox("Corrigeer BOB")
        self.chk_correct_bob.setChecked(True)
        self.cmb_resolution = QComboBox()
        self.cmb_resolution.addItems(["nauwkeurig", "snel"])
        settings.addWidget(self.chk_correct_bob)
        settings.addWidget(QLabel("Resolutie:"))
        settings.addWidget(self.cmb_resolution)
        left_layout.addLayout(settings)

        seg_settings = QHBoxLayout()
        self.spn_min_segment = QDoubleSpinBox(); self.spn_min_segment.setRange(0.1, 50.0)
        self.spn_min_segment.setValue(1.0); self.spn_min_segment.setSuffix(" m")
        self.spn_bob_segment = QDoubleSpinBox(); self.spn_bob_segment.setRange(0.5, 100.0)
        self.spn_bob_segment.setValue(5.0); self.spn_bob_segment.setSuffix(" m")
        seg_settings.addWidget(QLabel("Segment:"))
        seg_settings.addWidget(self.spn_min_segment)
        seg_settings.addWidget(QLabel("BOB-seg:"))
        seg_settings.addWidget(self.spn_bob_segment)
        left_layout.addLayout(seg_settings)

        left_layout.addWidget(QLabel("Sinks (uitstroompunten):"))
        sink_row = QHBoxLayout()
        self.sink_combo = ExtendedCombo()
        add_sink = QToolButton()
        add_sink.setIcon(_icon("sink.svg"))
        add_sink.setToolTip("Voeg de geselecteerde put toe als sink")
        add_sink.clicked.connect(self._on_add_sink)
        self.btn_sink_map = QPushButton("Kaart")
        self.btn_sink_map.setCheckable(True)
        self.btn_sink_map.setToolTip("Kies een sink-put door deze op de kaart aan te klikken")
        self.btn_sink_map.clicked.connect(self._on_sink_map_toggled)
        clear_sink = QPushButton("Wis")
        clear_sink.clicked.connect(self._on_clear_sinks)
        sink_row.addWidget(self.sink_combo, 1)
        sink_row.addWidget(add_sink)
        sink_row.addWidget(self.btn_sink_map)
        sink_row.addWidget(clear_sink)
        left_layout.addLayout(sink_row)
        self.sink_label = QLabel("geen sinks gekozen")
        self.sink_label.setStyleSheet("color: #666;")
        self.sink_label.setWordWrap(True)
        left_layout.addWidget(self.sink_label)

        self.btn_loss = QPushButton(_icon("lost_capacity.svg"), "Bereken berging")
        self.btn_loss.clicked.connect(self._on_loss)
        left_layout.addWidget(self.btn_loss)

        left_layout.addWidget(QLabel("Traject (klik putten op de kaart):"))
        self.traj_bar = QWidget()
        traj_layout = QHBoxLayout(self.traj_bar)
        traj_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_traj_downstream = QPushButton("Stroomafw.")
        self.btn_traj_downstream.clicked.connect(self._on_downstream)
        self.btn_traj_delmode = QPushButton("Verwijdermodus")
        self.btn_traj_delmode.setCheckable(True)
        self.btn_traj_clear = QPushButton("Wis")
        self.btn_traj_clear.clicked.connect(self._on_reset)
        self.btn_traj_undo = QPushButton("↶")
        self.btn_traj_undo.clicked.connect(self._on_undo)
        self.btn_traj_redo = QPushButton("↷")
        self.btn_traj_redo.clicked.connect(self._on_redo)
        for b in (self.btn_traj_downstream, self.btn_traj_delmode, self.btn_traj_clear,
                  self.btn_traj_undo, self.btn_traj_redo):
            traj_layout.addWidget(b)
        self.traj_bar.setVisible(False)
        left_layout.addWidget(self.traj_bar)
        left_layout.addStretch(1)
        left.setMaximumWidth(340)

        # --- Right: longitudinal profile. ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)
        header = QHBoxLayout()
        header.addStretch()
        self.volume_label = QLabel("")
        self.volume_label.setStyleSheet("color: #2c7fb8; font-weight: bold;")
        header.addWidget(self.volume_label)
        right_layout.addLayout(header)
        self.side_view = SideViewWidget()
        self.side_view.hovered.connect(self._on_graph_hover)
        right_layout.addWidget(self.side_view, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 760])

        self.setWidget(splitter)
        self._set_data_enabled(False)

    def _tool_button(self, text, icon_name, slot, checkable=False):
        button = QToolButton()
        button.setText(text)
        button.setIcon(_icon(icon_name))
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setCheckable(checkable)
        button.setAutoRaise(True)
        button.clicked.connect(slot)
        return button

    def _set_data_enabled(self, enabled):
        for widget in (self.btn_traj, self.btn_downstream, self.btn_style, self.btn_loss,
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

        pipes = read_pipes(self.gpkg_path)
        self.pipes_by_code = {p.code: p for p in pipes}
        self.network = SewerNetwork(pipes)
        self.manhole_points = read_manhole_points(self.gpkg_path)
        self.measurements_by_pipe = self._read_profile_for_sideview()
        self.pipe_geoms = {f["code"]: f.geometry() for f in pipe_layer.getFeatures()}

        # Sink combo + existing sinks.
        manholes = read_manholes(self.gpkg_path)
        self._manholes_by_code = {m.code: m for m in manholes}
        self.sink_combo.clear()
        self.sink_combo.addItems(sorted(m.code for m in manholes))
        self.sinks = {m.code for m in manholes if m.is_sink}
        # Treat the loaded sinks as the baseline (not stale until they change).
        self.computed_sinks = set(self.sinks) if self.sinks else None
        self._update_sink_label()
        self._update_berging_button()

        if self.graphics is None:
            self.graphics = TrajectoryGraphics(self.iface.mapCanvas())
        self.waypoints = []
        self._update_sink_markers()
        self._rebuild()
        self._set_data_enabled(True)
        self.state.mark_imported()
        self._refresh_step_buttons()

    # ------------------------------------------------------------ actions
    def _on_import(self):
        self.plugin.on_import()

    def _read_profile_for_sideview(self):
        """Read the profile layer into {code: [dict(dist,bob,obb,flooded_pct,water_level)]}."""
        if not self.gpkg_path:
            return {}
        from drainworks_plugin.io.geopackage_store import read_profile
        out = {}
        for code, points in read_profile(self.gpkg_path).items():
            out[code] = [{"dist": p.dist, "bob": p.bob, "obb": p.obb,
                          "flooded_pct": None, "water_level": None} for p in points]
        return out

    def _reload_profile(self):
        self.measurements_by_pipe = self._read_profile_for_sideview()
        self._rebuild()

    def _on_enrich(self):
        """Step 2: enrich the (possibly edited) base data, off-thread."""
        if not self.gpkg_path:
            self.iface.messageBar().pushWarning("Drainworks", "Importeer eerst data.")
            return
        from drainworks_plugin.pipeline.tasks import EnrichTask

        task = EnrichTask(self.gpkg_path,
                          correct_bob=self.chk_correct_bob.isChecked(),
                          min_segment=self.spn_min_segment.value(),
                          bob_segment=self.spn_bob_segment.value(),
                          on_done=self._enrich_done)
        self._run_task(task)

    def _enrich_done(self, task):
        if task.error is not None:
            self.iface.messageBar().pushCritical("Drainworks", f"Verrijken mislukt: {task.error}")
            self.active_task = None
            self._refresh_step_buttons()  # re-enable so the user can retry
            return
        self.state.mark_enriched()
        s = task.result or {}
        self.plugin.reload_pipeline_layers()
        self._reload_profile()
        self._refresh_step_buttons()
        self.active_task = None
        self.iface.messageBar().pushSuccess(
            "Drainworks",
            f"Verrijkt: {s.get('n_segments', 0)} segmenten, "
            f"{s.get('n_pipes_with_issues', 0)} leidingen met problemen.")

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
        resolution = "accurate" if self.cmb_resolution.currentIndex() == 0 else "fast"
        task = BergingTask(self.gpkg_path, resolution=resolution, on_done=self._loss_done)
        self._run_task(task)

    def _loss_done(self, task):
        if task.error is not None:
            self.iface.messageBar().pushCritical("Drainworks", f"Berekening mislukt: {task.error}")
            self.active_task = None
            self._refresh_step_buttons()  # re-enable so the user can retry
            return
        self.state.mark_berging_computed()
        self.computed_sinks = set(self.sinks)
        self.plugin.reload_pipeline_layers()
        self._refresh_step_buttons()
        self._rebuild()
        self.active_task = None
        self.iface.messageBar().pushSuccess(
            "Drainworks", f"Verloren berging berekend ({task.result} segmenten).")

    def _run_task(self, task):
        """Submit a QgsTask to the task manager, disabling the step buttons."""
        from qgis.core import QgsApplication

        self.active_task = task
        for btn in (self.btn_enrich, self.btn_loss):
            btn.setEnabled(False)
        QgsApplication.taskManager().addTask(task)

    def _refresh_step_buttons(self):
        """Re-enable + relabel the step buttons from the PipelineState."""
        self.btn_enrich.setEnabled(self.gpkg_path is not None)
        self.btn_loss.setEnabled(self.gpkg_path is not None)
        self.btn_enrich.setText(self.state.enrich_label())
        self.btn_enrich.setStyleSheet(
            "color: #c54141; font-weight: bold;" if self.state.enrich_stale and self.state.enrich_ran else "")
        self.btn_loss.setText(self.state.berging_label())
        self.btn_loss.setStyleSheet(
            "color: #c54141; font-weight: bold;" if self.state.berging_stale and self.state.berging_ran else "")

    def _on_style(self):
        if self.pipe_layer is None or self.manhole_layer is None:
            self.iface.messageBar().pushWarning("Drainworks", "Importeer eerst data.")
            return
        from drainworks_plugin.styling.views import apply_manhole_style, apply_pipe_style
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
        self._commit_waypoints()

    def _on_traj_toggled(self, checked):
        self.traj_bar.setVisible(checked)
        if checked:
            self.btn_sink_map.setChecked(False)
            self._activate_tool(self._on_pick, self._on_reset)
            self._sync_traj_buttons()
        else:
            self.btn_traj_delmode.setChecked(False)
            self._clear_tool()

    def _on_sink_map_toggled(self, checked):
        if checked:
            self.btn_traj.setChecked(False)  # exclusive with trajectory
            self._activate_tool(self._on_sink_picked, on_reset=lambda: None)
        else:
            self._clear_tool()

    def _activate_tool(self, on_pick, on_reset):
        from drainworks_plugin.trajectory.map_tool import TrajectoryMapTool

        if self.manhole_layer is None:
            return
        canvas = self.iface.mapCanvas()
        if self.map_tool is not None:
            canvas.unsetMapTool(self.map_tool)
        self.map_tool = TrajectoryMapTool(canvas, self.manhole_layer, on_pick, on_reset,
                                          on_move=self._on_map_hover,
                                          on_ctrl_pick=self._on_ctrl_pick, on_drag=self._on_drag)
        canvas.setMapTool(self.map_tool)

    def _clear_tool(self):
        if self.map_tool is not None:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None

    # ------------------------------------------------------------- sinks
    def _on_add_sink(self):
        self._add_sink(self.sink_combo.currentText().strip())

    def _on_sink_picked(self, code):
        self._add_sink(code)
        # One-shot: turn the map-pick button off after each chosen sink.
        self.btn_sink_map.setChecked(False)
        self._clear_tool()

    def _add_sink(self, code):
        if code and code in self.manhole_points:
            self.sinks.add(code)
            self._apply_sinks()

    def _on_clear_sinks(self):
        self.sinks.clear()
        self._apply_sinks()

    def _apply_sinks(self):
        # Sinks are persisted to the GeoPackage only when the berging is computed
        # (see _on_loss), so changing them just updates the UI + staleness state.
        self._update_sink_label()
        self._update_sink_markers()
        self._update_berging_button()
        self.state.mark_sinks_changed()
        self._refresh_step_buttons()

    def _update_berging_button(self):
        """Reflect whether the berging is up to date with the current sinks."""
        if not hasattr(self, "btn_loss"):
            return
        if self.computed_sinks is not None and self.sinks != self.computed_sinks:
            self.btn_loss.setText("Herbereken berging")
            self.btn_loss.setStyleSheet("color: #c54141; font-weight: bold;")
        else:
            self.btn_loss.setText("Bereken berging")
            self.btn_loss.setStyleSheet("")

    def _update_sink_markers(self):
        if self.graphics is None:
            return
        points = [QgsPointXY(*self.manhole_points[c]) for c in self.sinks
                  if c in self.manhole_points]
        self.graphics.set_sink_markers(points)

    def _update_sink_label(self):
        if self.sinks:
            self.sink_label.setText("sinks: " + ", ".join(sorted(self.sinks)))
            self.sink_label.setStyleSheet("color: #0079c1;")
        else:
            self.sink_label.setText("geen sinks gekozen")
            self.sink_label.setStyleSheet("color: #666;")

    # -------------------------------------------------------- trajectory
    def _commit_waypoints(self, push=True):
        """Persist the current waypoints to history and rebuild everything."""
        if push:
            self.history.set(self.waypoints)
        self._sync_traj_buttons()
        self._rebuild()

    def _sync_traj_buttons(self):
        self.btn_traj_undo.setEnabled(self.history.can_undo())
        self.btn_traj_redo.setEnabled(self.history.can_redo())

    def _on_undo(self):
        self.waypoints = self.history.undo()
        self._commit_waypoints(push=False)

    def _on_redo(self):
        self.waypoints = self.history.redo()
        self._commit_waypoints(push=False)

    def _on_ctrl_pick(self, code):
        if code in self.waypoints:
            self.waypoints.remove(code)
            self._commit_waypoints()

    def _on_drag(self, from_code, to_code):
        if from_code in self.waypoints and to_code not in self.waypoints:
            self.waypoints[self.waypoints.index(from_code)] = to_code
            self._commit_waypoints()

    def _on_pick(self, code):
        if self.btn_traj_delmode.isChecked():
            if code in self.waypoints:
                self.waypoints.remove(code)
                self._commit_waypoints()
            return
        self._insert_waypoint(code)
        self._commit_waypoints()

    def _insert_waypoint(self, code):
        """Insert a put at the cheapest position: a tussenpunt mid-route, or
        extend at an end, whichever adds the least route length."""
        wps = self.waypoints
        if code in wps:
            return
        if len(wps) < 2:
            wps.append(code)
            return

        def leg(a, b):
            try:
                return self.network.shortest_path(a, b).total_length
            except ValueError:
                return float("inf")

        # Default: append at the end.
        best_cost = leg(wps[-1], code)
        best_pos = len(wps)
        # Prepend at the start.
        cost = leg(code, wps[0])
        if cost < best_cost:
            best_cost, best_pos = cost, 0
        # Insert between two existing waypoints.
        for i in range(len(wps) - 1):
            cost = leg(wps[i], code) + leg(code, wps[i + 1]) - leg(wps[i], wps[i + 1])
            if cost < best_cost:
                best_cost, best_pos = cost, i + 1
        wps.insert(best_pos, code)

    def _on_map_hover(self, point):
        """Highlight the nearest put and drive the graph cursor from the route."""
        if self.graphics is None:
            return
        mupp = self.iface.mapCanvas().mapUnitsPerPixel()
        px, py = point.x(), point.y()
        # Nearest manhole within ~18 px -> highlight (the pick target).
        tol = mupp * 18
        nearest = None
        for xy in self.manhole_points.values():
            d = ((xy[0] - px) ** 2 + (xy[1] - py) ** 2) ** 0.5
            if d <= tol:
                tol, nearest = d, xy
        self.graphics.set_hover(QgsPointXY(*nearest) if nearest else None)
        # Reverse hover: project onto the route -> show the graph cursor.
        if self.route_polyline:
            dist, offset = self._project_on_route(px, py)
            self.side_view.set_cursor(dist if offset <= mupp * 14 else None)
        else:
            self.side_view.set_cursor(None)

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
        self.waypoints = []
        self._commit_waypoints()

    def _rebuild(self):
        """Recompute route, refresh map graphics and side-view."""
        self._update_graphics()
        self._update_side_view()

    def _cumulative_distances(self):
        """Distance along the route at each chosen waypoint (A=0, B, C, …)."""
        cumulative = [0.0]
        if self.network is None:
            return cumulative * len(self.waypoints)
        total = 0.0
        for a, b in zip(self.waypoints, self.waypoints[1:]):
            try:
                total += self.network.shortest_path(a, b).total_length
            except ValueError:
                total = float("nan")
            cumulative.append(total)
        return cumulative[: len(self.waypoints)]

    def _update_graphics(self):
        if self.graphics is None:
            return
        labelled = []
        for i, code in enumerate(self.waypoints):
            xy = self.manhole_points.get(code)
            if xy is not None:
                letter = LETTERS[i] if i < len(LETTERS) else str(i + 1)
                labelled.append((letter, QgsPointXY(xy[0], xy[1])))
        self.graphics.set_markers(labelled)

        geoms = []
        if self.network is not None and len(self.waypoints) >= 2:
            try:
                route = self.network.route(self.waypoints)
                geoms = [self.pipe_geoms.get(c) for c in route.pipe_codes]
            except ValueError:
                geoms = []
        self.graphics.set_route(geoms)

        if self.waypoints:
            xy = self.manhole_points.get(self.waypoints[-1])
            self.graphics.set_active(QgsPointXY(*xy) if xy else None)
        else:
            self.graphics.set_active(None)

    def _update_side_view(self):
        if self.network is None or len(self.waypoints) < 2:
            self.side_view.clear()
            self.volume_label.setText("")
            self.route_polyline = []
            return
        try:
            route = self.network.route(self.waypoints)
        except ValueError as exc:
            self.iface.messageBar().pushWarning("Drainworks", str(exc))
            self.side_view.clear()
            self.volume_label.setText("")
            self.route_polyline = []
            return
        profile = build_profile(route, self.pipes_by_code, self.measurements_by_pipe,
                                manholes_by_code=self._manholes_by_code)
        self.side_view.show_profile(profile)
        self.route_polyline = self._build_route_polyline(route)
        from drainworks_plugin.sideview.berging import route_berging
        segments_by_pipe = self._read_segments_by_pipe()
        water, volume = route_berging(route, self.pipes_by_code, segments_by_pipe)
        self.side_view.show_water(water)
        self.volume_label.setText(f"Verloren berging: {volume:.2f} m³" if volume else "")

    def _read_segments_by_pipe(self):
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
        if self.map_tool is not None:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None
        self.btn_traj.setChecked(False)
        self.btn_sink_map.setChecked(False)

    def clear_graphics(self):
        if self.graphics is not None:
            self.graphics.clear()

    def teardown(self):
        """Release the map tool and remove all canvas items (for plugin unload)."""
        self.deactivate_tool()
        if self.graphics is not None:
            self.graphics.destroy()
            self.graphics = None
