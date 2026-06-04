"""Orchestrate import: RIBX or GeoPackage -> stored .gpkg -> loaded map layers."""

from pathlib import Path

from qgis.core import QgsProject, QgsVectorLayer

import rgs_ribx

from drainworks_plugin.io.geopackage_store import (
    MeasurementRow,
    point_along_wkt,
    write_base,
    write_geopackage,
)


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


def import_ribx(ribx_path, gpkg_path, correct_bob=False):
    """Parse a RIBX file, write a GeoPackage, and load its layers."""
    return _store_and_load(rgs_ribx.build_from_ribx(ribx_path), gpkg_path, correct_bob)


def import_sufrib(network_path, measurement_path, gpkg_path, correct_bob=False):
    """Parse classic SUFRIB files (.rib + .hel/.rmb), write a GeoPackage, load it.

    ``measurement_path`` may be None (network only). Returns the same tuple as
    :func:`import_ribx`.
    """
    paths = [network_path] + ([measurement_path] if measurement_path else [])
    return _store_and_load(rgs_ribx.build_from_sufrib(paths), gpkg_path, correct_bob)


def _store_and_load(result, gpkg_path, correct_bob):
    """Write a BuildResult (manholes/pipes + measured profile) to gpkg and load it.

    With ``correct_bob`` the measured profile is de-trended onto the pipe's known
    BOBs at import time. Returns (manhole_layer, pipe_layer, group).
    """
    pipes_by_code = {p.code: p for p in result.pipes}
    rows = []
    for code, points in (result.measurements or {}).items():
        pipe = pipes_by_code.get(code)
        if pipe is None:
            continue
        if correct_bob and pipe.bob1 is not None and pipe.bob2 is not None:
            rgs_ribx.correct_profile_to_bobs(points, pipe.bob1, pipe.bob2, pipe.length)
        for mp in points:
            rows.append(
                MeasurementRow(
                    pipe_code=code,
                    dist=mp.dist,
                    bob=mp.bob,
                    obb=mp.obb,
                    geometry_wkt=point_along_wkt(pipe.geometry_wkt, mp.dist),
                )
            )
    write_geopackage(gpkg_path, result.manholes, result.pipes, rows)
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
