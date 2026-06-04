from drainworks_plugin.styling.symbology import style_segments


def test_style_segments_applies_graduated_renderer():
    from qgis.core import QgsApplication, QgsGraduatedSymbolRenderer, QgsVectorLayer

    if QgsApplication.instance() is None:
        app = QgsApplication([], False)
        app.initQgis()

    layer = QgsVectorLayer(
        "LineString?crs=EPSG:28992&field=flooded_pct:double", "segments", "memory")
    assert layer.isValid()
    style_segments(layer)
    renderer = layer.renderer()
    assert isinstance(renderer, QgsGraduatedSymbolRenderer)
    assert renderer.classAttribute() == "flooded_pct"
    assert len(renderer.ranges()) >= 4
