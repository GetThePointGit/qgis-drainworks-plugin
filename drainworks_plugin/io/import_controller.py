"""Orchestrate import: RIBX or GeoPackage -> stored .gpkg -> loaded map layers."""

from pathlib import Path

from qgis.core import QgsProject, QgsVectorLayer

import rgs_ribx

from drainworks_plugin.io.geopackage_store import write_base


def import_to_base(input_path, measurement_path, gpkg_path):
    """Parse RIBX/SUFRIB and write the step-1 base GeoPackage. Returns the path.

    Dispatches by extension: ``.rib``/``.hel`` -> SUFRIB (with optional
    ``measurement_path``), otherwise RIBX. No height integration, no segments —
    those are produced by step 2 (enrich).
    """
    lower = input_path.lower()
    if lower.endswith((".rib", ".hel")):
        paths = [input_path] + ([measurement_path] if measurement_path else [])
        result = rgs_ribx.build_from_sufrib(paths)
    else:
        result = rgs_ribx.build_from_ribx(input_path)
    return write_base(gpkg_path, result.manholes, result.pipes, result.raw_measurements)


def load_pipeline_layers(gpkg_path):
    """Load manholes/pipes (+ profile/segments if present) into a styled group.

    Returns ``(manhole_layer, pipe_layer, group, segments_layer_or_None)``.
    """
    from drainworks_plugin.styling.symbology import (
        style_manholes,
        style_pipes,
        style_profile,
        style_segments,
    )

    gpkg_path = Path(gpkg_path)
    pipe_layer = QgsVectorLayer(f"{gpkg_path}|layername=pipes", "Leidingen", "ogr")
    manhole_layer = QgsVectorLayer(f"{gpkg_path}|layername=manholes", "Putten", "ogr")
    if not pipe_layer.isValid() or not manhole_layer.isValid():
        raise RuntimeError(f"Could not load layers from {gpkg_path}")
    style_pipes(pipe_layer)
    style_manholes(manhole_layer)

    project = QgsProject.instance()
    root = project.layerTreeRoot()
    existing = root.findGroup(gpkg_path.stem)
    if existing is not None:
        for child in list(existing.findLayers()):
            project.removeMapLayer(child.layerId())
        root.removeChildNode(existing)
    group = root.insertGroup(0, gpkg_path.stem)

    segments_layer = QgsVectorLayer(f"{gpkg_path}|layername=segments", "Segmenten", "ogr")
    profile_layer = QgsVectorLayer(f"{gpkg_path}|layername=profile", "Profielpunten", "ogr")
    if segments_layer.isValid():
        style_segments(segments_layer)
    if profile_layer.isValid():
        style_profile(profile_layer)

    # Draw order top->bottom: manholes, pipes, segments, profile.
    ordered = [manhole_layer, pipe_layer]
    if segments_layer.isValid():
        ordered.append(segments_layer)
    if profile_layer.isValid():
        ordered.append(profile_layer)
    for layer in ordered:
        project.addMapLayer(layer, False)
        group.addLayer(layer)
    return manhole_layer, pipe_layer, group, (segments_layer if segments_layer.isValid() else None)
