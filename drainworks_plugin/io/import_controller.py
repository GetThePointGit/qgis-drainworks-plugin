"""Orchestrate import: RIBX or GeoPackage -> stored .gpkg -> loaded map layers."""

from pathlib import Path

from qgis.core import QgsProject, QgsVectorLayer

import rgs_ribx

from drainworks_plugin.io.geopackage_store import write_geopackage


def import_ribx(ribx_path, gpkg_path):
    """Parse a RIBX file, write a GeoPackage, and load its layers.

    Returns
    -------
    (manhole_layer, pipe_layer, group) : (QgsVectorLayer, QgsVectorLayer, QgsLayerTreeGroup)
    """
    result = rgs_ribx.build_from_ribx(ribx_path)
    write_geopackage(gpkg_path, result.manholes, result.pipes, measurements=[])
    return load_geopackage_layers(gpkg_path)


def load_geopackage_layers(gpkg_path):
    """Load manholes + pipes into a named layer group in the QGIS project.

    The group is named after the GeoPackage file so multiple imports stay
    visually separated. Returns ``(manhole_layer, pipe_layer, group)``.
    """
    gpkg_path = Path(gpkg_path)
    pipe_layer = QgsVectorLayer(f"{gpkg_path}|layername=pipes", "Leidingen", "ogr")
    manhole_layer = QgsVectorLayer(f"{gpkg_path}|layername=manholes", "Putten", "ogr")
    if not pipe_layer.isValid() or not manhole_layer.isValid():
        raise RuntimeError(f"Could not load layers from {gpkg_path}")

    from drainworks_plugin.styling.symbology import style_manholes, style_pipes

    style_pipes(pipe_layer)
    style_manholes(manhole_layer)

    project = QgsProject.instance()
    group = project.layerTreeRoot().insertGroup(0, gpkg_path.stem)
    # Add layers without auto-inserting at the tree root, then place them in the
    # group with manholes (points) above pipes (lines) so nodes draw on top.
    for layer in (manhole_layer, pipe_layer):
        project.addMapLayer(layer, False)
        group.addLayer(layer)
    return manhole_layer, pipe_layer, group


def add_layer_to_group(layer, group, on_top=True):
    """Add an already-created layer into ``group`` (or the root if group is None)."""
    project = QgsProject.instance()
    project.addMapLayer(layer, False)
    if group is not None:
        if on_top:
            group.insertLayer(0, layer)
        else:
            group.addLayer(layer)
    else:
        project.layerTreeRoot().insertLayer(0, layer)
