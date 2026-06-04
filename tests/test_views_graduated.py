def _qgis():
    from qgis.core import QgsApplication
    if QgsApplication.instance() is None:
        app = QgsApplication([], False)
        app.initQgis()


def test_pipe_color_by_bob_uses_graduated_renderer():
    _qgis()
    from qgis.core import QgsGraduatedSymbolRenderer, QgsVectorLayer
    from drainworks_plugin.styling.views import (
        PIPE_COLOR_BOB, PIPE_LABEL_NONE, PIPE_WIDTH_DEFAULT, apply_pipe_style)

    layer = QgsVectorLayer(
        "LineString?crs=EPSG:28992&field=bob_avg:double&field=slope:double&field=diameter:double",
        "pipes", "memory")
    from qgis.core import QgsFeature, QgsGeometry, QgsPointXY
    for v in (-2.0, -3.0, -4.0):
        f = QgsFeature(layer.fields())
        f.setAttribute("bob_avg", v)
        f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)]))
        layer.dataProvider().addFeature(f)
    layer.updateExtents()

    apply_pipe_style(layer, PIPE_COLOR_BOB, PIPE_WIDTH_DEFAULT, PIPE_LABEL_NONE)
    r = layer.renderer()
    assert isinstance(r, QgsGraduatedSymbolRenderer)
    assert r.classAttribute() == "bob_avg"
    assert len(r.ranges()) >= 3


def test_pipe_color_default_stays_single_symbol():
    _qgis()
    from qgis.core import QgsSingleSymbolRenderer, QgsVectorLayer
    from drainworks_plugin.styling.views import (
        PIPE_COLOR_DEFAULT, PIPE_LABEL_NONE, PIPE_WIDTH_DEFAULT, apply_pipe_style)

    layer = QgsVectorLayer(
        "LineString?crs=EPSG:28992&field=bob_avg:double&field=slope:double&field=diameter:double",
        "pipes", "memory")
    apply_pipe_style(layer, PIPE_COLOR_DEFAULT, PIPE_WIDTH_DEFAULT, PIPE_LABEL_NONE)
    assert isinstance(layer.renderer(), QgsSingleSymbolRenderer)
