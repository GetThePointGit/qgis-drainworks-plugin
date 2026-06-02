"""Orchestrate import: RIBX or GeoPackage -> stored .gpkg -> loaded map layers."""

from pathlib import Path

from qgis.core import QgsProject, QgsVectorLayer

import rgs_ribx

from drainworks_plugin.io.geopackage_store import write_geopackage


def import_ribx(ribx_path, gpkg_path) -> "tuple[QgsVectorLayer, QgsVectorLayer]":
    """Parse a RIBX file, write a GeoPackage, and load its layers.

    Returns
    -------
    (manhole_layer, pipe_layer) : tuple of QgsVectorLayer
    """
    result = rgs_ribx.build_from_ribx(ribx_path)
    write_geopackage(gpkg_path, result.manholes, result.pipes, measurements=[])
    return load_geopackage_layers(gpkg_path)


def load_geopackage_layers(gpkg_path) -> "tuple[QgsVectorLayer, QgsVectorLayer]":
    """Load manholes + pipes layers from a GeoPackage into the QGIS project."""
    gpkg_path = Path(gpkg_path)
    pipe_layer = QgsVectorLayer(f"{gpkg_path}|layername=pipes", "Leidingen", "ogr")
    manhole_layer = QgsVectorLayer(f"{gpkg_path}|layername=manholes", "Putten", "ogr")
    if not pipe_layer.isValid() or not manhole_layer.isValid():
        raise RuntimeError(f"Could not load layers from {gpkg_path}")
    project = QgsProject.instance()
    project.addMapLayer(pipe_layer)
    project.addMapLayer(manhole_layer)

    from drainworks_plugin.styling.symbology import style_manholes, style_pipes

    style_pipes(pipe_layer)
    style_manholes(manhole_layer)
    return manhole_layer, pipe_layer
