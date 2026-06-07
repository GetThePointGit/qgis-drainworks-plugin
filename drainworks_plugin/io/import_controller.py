"""Orchestrate import: RIBX or GeoPackage -> stored .gpkg -> loaded map layers."""

from pathlib import Path

from qgis.core import QgsProject, QgsVectorLayer

import rgs_ribx

from drainworks_plugin.io.geopackage_store import write_base


def parse_input(input_path, measurement_path, on_progress=None):
    """Parse RIBX/SUFRIB into a ``BuildResult`` — **no** GeoPackage write.

    Dispatches by extension: ``.rib``/``.hel`` -> SUFRIB (with optional
    ``measurement_path``), otherwise RIBX. Pure Python (lxml/pandas, no GDAL), so it
    is safe to run in a ``QgsTask`` worker thread; the GeoPackage write
    (:func:`write_base_from_result`) must run on the main thread (Windows crash).

    ``on_progress(fraction, label)`` (0..1), if given, reports parse progress.
    """
    def _report(frac, label):
        if on_progress is not None:
            try:
                on_progress(frac, label)
            except Exception:  # progress feedback must never break the import
                pass

    is_sufrib = input_path.lower().endswith((".rib", ".hel"))
    read_label = "SUFRIB inlezen…" if is_sufrib else "RIBX inlezen…"

    def _parse_progress(frac):
        _report(0.02 + 0.96 * frac, read_label)

    _report(0.02, read_label)
    if is_sufrib:
        paths = [input_path] + ([measurement_path] if measurement_path else [])
        return rgs_ribx.build_from_sufrib(paths, progress=_parse_progress)
    return rgs_ribx.build_from_ribx(input_path, progress=_parse_progress)


def write_base_from_result(gpkg_path, result, on_progress=None):
    """Write a parsed ``BuildResult`` to the base GeoPackage (run on the main thread)."""
    return write_base(gpkg_path, result.manholes, result.pipes, result.raw_measurements,
                      on_progress=on_progress)


def import_to_base(input_path, measurement_path, gpkg_path, on_progress=None):
    """Parse + write the step-1 base GeoPackage in one call. Returns the path.

    Convenience for synchronous/test use; the plugin instead parses off-thread
    (:func:`parse_input`) and writes on the main thread (:func:`write_base_from_result`).
    Parsing maps to 0..0.6 of the progress, writing to 0.6..1.0.
    """
    result = parse_input(input_path, measurement_path,
                         lambda f, l: on_progress(0.6 * f, l) if on_progress else None)
    return write_base_from_result(
        gpkg_path, result,
        lambda f, l: on_progress(0.6 + 0.4 * f, l) if on_progress else None)


def load_pipeline_layers(gpkg_path):
    """Load manholes/pipes (+ profile/segments if present) into a styled group.

    Returns ``(manhole_layer, pipe_layer, group, segments_layer_or_None)``.
    """
    from drainworks_plugin.styling.symbology import (
        style_manholes,
        style_pipes,
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
    if segments_layer.isValid():
        style_segments(segments_layer)

    # Draw order top->bottom: manholes, segments, pipes (segments draw on top of the
    # pipes). The profile points feed the side-view (read from the gpkg) and are
    # intentionally not added to the map.
    ordered = [manhole_layer]
    if segments_layer.isValid():
        ordered.append(segments_layer)
    ordered.append(pipe_layer)
    for layer in ordered:
        project.addMapLayer(layer, False)
        group.addLayer(layer)
    return manhole_layer, pipe_layer, group, (segments_layer if segments_layer.isValid() else None)
