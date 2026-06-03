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
    QAbstractItemView,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
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
        self.waypoints = []
        self.sinks = set()
        self.map_tool = None
        self.graphics = None

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)

        # Action buttons.
        actions = QHBoxLayout()
        self.btn_import = self._tool_button("Importeren", "import.svg", self._on_import)
        self.btn_traj = self._tool_button("Traject", "trajectory.svg", self._on_traj_toggled,
                                          checkable=True)
        self.btn_loss = self._tool_button("Verloren berging", "lost_capacity.svg", self._on_loss)
        actions.addWidget(self.btn_import)
        actions.addWidget(self.btn_traj)
        actions.addWidget(self.btn_loss)
        actions.addStretch()
        layout.addLayout(actions)

        # Sink selector.
        layout.addWidget(QLabel("Sinks (uitstroompunten):"))
        sink_row = QHBoxLayout()
        self.sink_combo = ExtendedCombo()
        add_sink = QPushButton(_icon("sink.svg"), "Toevoegen")
        add_sink.clicked.connect(self._on_add_sink)
        clear_sink = QPushButton("Wis")
        clear_sink.clicked.connect(self._on_clear_sinks)
        sink_row.addWidget(self.sink_combo, 1)
        sink_row.addWidget(add_sink)
        sink_row.addWidget(clear_sink)
        layout.addLayout(sink_row)
        self.sink_label = QLabel("geen sinks gekozen")
        self.sink_label.setStyleSheet("color: #666;")
        layout.addWidget(self.sink_label)

        # Trajectory table.
        layout.addWidget(QLabel("Traject (klik putten op de kaart):"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "Put", "Afstand (m)", ""])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 28)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 32)
        self.table.setMaximumHeight(160)
        layout.addWidget(self.table)

        # Side-view.
        layout.addWidget(QLabel("Langsprofiel:"))
        self.side_view = SideViewWidget()
        layout.addWidget(self.side_view, 1)

        self.setWidget(container)
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
        for widget in (self.btn_traj, self.btn_loss, self.sink_combo):
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
        self.pipe_geoms = {f["code"]: f.geometry() for f in pipe_layer.getFeatures()}

        # Sink combo + existing sinks.
        manholes = read_manholes(self.gpkg_path)
        self.sink_combo.clear()
        self.sink_combo.addItems(sorted(m.code for m in manholes))
        self.sinks = {m.code for m in manholes if m.is_sink}
        self._update_sink_label()

        if self.graphics is None:
            self.graphics = TrajectoryGraphics(self.iface.mapCanvas())
        self.waypoints = []
        self._rebuild()
        self._set_data_enabled(True)

    # ------------------------------------------------------------ actions
    def _on_import(self):
        self.plugin.on_import()

    def _on_loss(self):
        if not self.sinks:
            self.iface.messageBar().pushWarning("Drainworks", "Kies eerst minimaal één sink.")
            return
        self.plugin.on_compute_loss()

    def _on_traj_toggled(self, checked):
        from drainworks_plugin.trajectory.map_tool import TrajectoryMapTool

        canvas = self.iface.mapCanvas()
        if checked and self.manhole_layer is not None:
            self.map_tool = TrajectoryMapTool(
                canvas, self.manhole_layer, self._on_pick, self._on_reset
            )
            canvas.setMapTool(self.map_tool)
        elif self.map_tool is not None:
            canvas.unsetMapTool(self.map_tool)
            self.map_tool = None

    # ------------------------------------------------------------- sinks
    def _on_add_sink(self):
        code = self.sink_combo.currentText().strip()
        if code and code in self.manhole_points:
            self.sinks.add(code)
            self._apply_sinks()

    def _on_clear_sinks(self):
        self.sinks.clear()
        self._apply_sinks()

    def _apply_sinks(self):
        from drainworks_plugin.io.geopackage_store import set_sinks

        if self.gpkg_path:
            set_sinks(self.gpkg_path, self.sinks)
        self._update_sink_label()

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
            return
        try:
            route = self.network.route(self.waypoints)
        except ValueError as exc:
            self.iface.messageBar().pushWarning("Drainworks", str(exc))
            self.side_view.clear()
            return
        profile = build_profile(route, self.pipes_by_code, {})
        self.side_view.show_profile(profile)

    # ------------------------------------------------------------ teardown
    def deactivate_tool(self):
        if self.map_tool is not None:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None
        self.btn_traj.setChecked(False)

    def clear_graphics(self):
        if self.graphics is not None:
            self.graphics.clear()
