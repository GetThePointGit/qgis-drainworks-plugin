"""The main Drainworks dock widget.

Hosts the action buttons (import / trajectory / lost capacity), a filterable
sink selector, the trajectory table (A, B, C … with manhole code, distance and a
delete button), and the embedded pyqtgraph side-view. It also owns the
trajectory state and draws the route + lettered markers on the canvas.
"""

import math
import os
import string

from qgis.core import QgsPointXY
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
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


def _flooded_area(point):
    """Flooded cross-section area (m²) of a measurement point (circular pipe)."""
    pct = point.get("flooded_pct") or 0.0
    diameter = (point["obb"] - point["bob"])
    return pct * math.pi * (diameter / 2.0) ** 2


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
        self.route_polyline = []  # [(cumulative_dist, QgsPointXY)] for graph<->map hover
        self.waypoints = []
        self.sinks = set()
        self.computed_sinks = None  # sinks at the last berging computation
        self.map_tool = None
        self.graphics = None

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
        actions.addWidget(self.btn_import)
        actions.addWidget(self.btn_traj)
        actions.addWidget(self.btn_downstream)
        actions.addStretch()
        left_layout.addLayout(actions)

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
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "Put", "Afst. (m)", ""])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 24)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 30)
        left_layout.addWidget(self.table, 1)
        clear_traj = QPushButton("Wis traject")
        clear_traj.setToolTip("Verwijder alle gekozen punten")
        clear_traj.clicked.connect(self._on_reset)
        left_layout.addWidget(clear_traj)
        left.setMaximumWidth(340)

        # --- Right: longitudinal profile. ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)
        header = QHBoxLayout()
        header.addWidget(QLabel("Langsprofiel:"))
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
        for widget in (self.btn_traj, self.btn_downstream, self.btn_loss,
                       self.sink_combo, self.btn_sink_map):
            widget.setEnabled(enabled)

    # --------------------------------------------------------------- data
    def set_data(self, manhole_layer, pipe_layer, gpkg_path):
        """Called after an import: load the network and reset trajectory state."""
        from drainworks_plugin.io.geopackage_store import (
            read_manhole_points,
            read_manholes,
            read_measurements,
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
        self.measurements_by_pipe = read_measurements(self.gpkg_path)
        self.pipe_geoms = {f["code"]: f.geometry() for f in pipe_layer.getFeatures()}

        # Sink combo + existing sinks.
        manholes = read_manholes(self.gpkg_path)
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

    # ------------------------------------------------------------ actions
    def _on_import(self):
        self.plugin.on_import()

    def _on_loss(self):
        if not self.sinks:
            self.iface.messageBar().pushWarning("Drainworks", "Kies eerst minimaal één sink.")
            return
        from drainworks_plugin.io.geopackage_store import read_measurements, set_sinks

        # Persist the chosen sinks only now (at computation time), then compute.
        if self.gpkg_path:
            set_sinks(self.gpkg_path, self.sinks)
        self.plugin.on_compute_loss()
        self.computed_sinks = set(self.sinks)
        if self.gpkg_path:
            self.measurements_by_pipe = read_measurements(self.gpkg_path)
        self._update_berging_button()
        self._rebuild()

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
        self._rebuild()

    def _on_traj_toggled(self, checked):
        if checked:
            self.btn_sink_map.setChecked(False)  # exclusive with sink-pick
            self._activate_tool(self._on_pick, self._on_reset)
        else:
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
        self.map_tool = TrajectoryMapTool(canvas, self.manhole_layer, on_pick, on_reset)
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
    def _on_pick(self, code):
        if self.waypoints and self.waypoints[-1] == code:
            return
        self.waypoints.append(code)
        self._rebuild()

    def _on_reset(self):
        self.waypoints = []
        self._rebuild()

    def _delete_waypoint(self, index):
        if 0 <= index < len(self.waypoints):
            del self.waypoints[index]
            self._rebuild()

    def _rebuild(self):
        """Recompute route, refresh table, map graphics and side-view."""
        cumulative = self._cumulative_distances()
        self._update_table(cumulative)
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

    def _update_table(self, cumulative):
        self.table.setRowCount(len(self.waypoints))
        for i, code in enumerate(self.waypoints):
            letter = LETTERS[i] if i < len(LETTERS) else str(i + 1)
            dist = cumulative[i] if i < len(cumulative) else float("nan")
            dist_text = "—" if dist != dist else f"{dist:.0f}"  # NaN check
            self.table.setItem(i, 0, QTableWidgetItem(letter))
            self.table.setItem(i, 1, QTableWidgetItem(code))
            self.table.setItem(i, 2, QTableWidgetItem(dist_text))
            delete = QPushButton("✕")
            delete.setFixedWidth(28)
            delete.clicked.connect(lambda _checked, idx=i: self._delete_waypoint(idx))
            self.table.setCellWidget(i, 3, delete)

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
        profile = build_profile(route, self.pipes_by_code, self.measurements_by_pipe)
        self.side_view.show_profile(profile)
        self.route_polyline = self._build_route_polyline(route)
        self._update_volume(route)

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

    def _update_volume(self, route):
        """Show the lost-storage volume integrated along the route."""
        volume = self._route_lost_volume(route)
        if volume is None:
            self.volume_label.setText("")
        else:
            self.volume_label.setText(f"Verloren berging: {volume:.2f} m³")

    def _route_lost_volume(self, route):
        """Integrate flooded cross-section area over the route (m³), or None."""
        any_flood = False
        total = 0.0
        for code in route.pipe_codes:
            points = self.measurements_by_pipe.get(code) or []
            for a, b in zip(points, points[1:]):
                seg = b["dist"] - a["dist"]
                if seg <= 0:
                    continue
                area_a = _flooded_area(a)
                area_b = _flooded_area(b)
                if a.get("flooded_pct") is not None or b.get("flooded_pct") is not None:
                    any_flood = True
                total += 0.5 * (area_a + area_b) * seg
        return total if any_flood else None

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
