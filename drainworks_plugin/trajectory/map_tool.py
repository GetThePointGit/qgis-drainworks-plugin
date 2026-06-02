"""Map tool: click near manholes to build a trajectory and show its side-view."""

from qgis.core import QgsPointXY, QgsProject
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt

import rgs_ribx

from drainworks_plugin.io.geopackage_store import read_manholes, read_pipes
from drainworks_plugin.sideview.profile_builder import build_profile
from drainworks_plugin.trajectory.network import SewerNetwork


class TrajectoryMapTool(QgsMapTool):
    """Pick manholes on the canvas; show the longitudinal profile of the route."""

    def __init__(self, canvas, manhole_layer, gpkg_path, side_view_panel, message_bar):
        super().__init__(canvas)
        self.canvas = canvas
        self.manhole_layer = manhole_layer
        self.gpkg_path = gpkg_path
        self.side_view = side_view_panel
        self.message_bar = message_bar
        self.waypoints = []

        pipes = read_pipes(gpkg_path)
        self._pipes_by_code = {p.code: p for p in pipes}
        self._network = SewerNetwork(pipes)
        self._observations_by_pipe = self._load_observations(gpkg_path)

    def _load_observations(self, gpkg_path) -> dict:
        """Re-parse observations from the source if available.

        Observations are not stored in the GeoPackage in this version; return
        empty mapping. (Follow-up task can add an ``observations`` layer.)
        """
        return {}

    def canvasReleaseEvent(self, event):  # noqa: N802 (QGIS-required name)
        if event.button() == Qt.RightButton:
            self.waypoints = []
            self.message_bar.pushInfo("Drainworks", "Trajectory reset.")
            return

        point = self.toMapCoordinates(event.pos())
        code = self._nearest_manhole_code(point)
        if code is None:
            return
        if self.waypoints and self.waypoints[-1] == code:
            return
        self.waypoints.append(code)

        if len(self.waypoints) >= 2:
            self._update_side_view()

    def _nearest_manhole_code(self, point: QgsPointXY):
        """Return the code of the nearest manhole feature to ``point``."""
        nearest_code = None
        nearest_dist = float("inf")
        for feat in self.manhole_layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            d = geom.distance(self._point_geometry(point))
            if d < nearest_dist:
                nearest_dist = d
                nearest_code = feat["code"]
        return nearest_code

    @staticmethod
    def _point_geometry(point: QgsPointXY):
        from qgis.core import QgsGeometry

        return QgsGeometry.fromPointXY(point)

    def _update_side_view(self):
        try:
            route = self._network.route(self.waypoints)
        except ValueError as exc:
            self.message_bar.pushWarning("Drainworks", str(exc))
            return
        profile = build_profile(route, self._pipes_by_code, self._observations_by_pipe)
        self.side_view.show_profile(profile)
        self.side_view.show()
        self.message_bar.pushInfo(
            "Drainworks",
            f"Route: {' → '.join(route.manholes)} ({route.total_length:.1f} m)",
        )
