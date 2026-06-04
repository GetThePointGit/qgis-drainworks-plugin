"""Switchable map styling for the pipe and manhole layers.

Each setting (colour / width / label) maps to a data-defined symbol property or
labeling configuration, so combinations can be applied independently.
"""

from qgis.core import (
    QgsGraduatedSymbolRenderer,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsProperty,
    QgsRendererRange,
    QgsSingleSymbolRenderer,
    QgsSymbolLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtGui import QColor

from drainworks_plugin.styling.colors import MANHOLE_DEFAULT, PIPE_DEFAULT

# Pipe colour modes.
PIPE_COLOR_DEFAULT = "default"
PIPE_COLOR_BOB = "bob"        # hoogteligging (gemiddelde BOB)
PIPE_COLOR_SLOPE = "slope"    # verhang
# Pipe width modes.
PIPE_WIDTH_DEFAULT = "default"
PIPE_WIDTH_DIAMETER = "diameter"
# Pipe label modes.
PIPE_LABEL_NONE = "none"
PIPE_LABEL_CODE = "code"
PIPE_LABEL_BOB = "bob"
PIPE_LABEL_DIAMETER = "diameter"

# Manhole colour modes.
MANHOLE_COLOR_DEFAULT = "default"
MANHOLE_COLOR_BOTTOM = "bottom"   # bodemhoogte
MANHOLE_COLOR_GROUND = "ground"   # maaiveld
# Manhole label modes.
MANHOLE_LABEL_NONE = "none"
MANHOLE_LABEL_CODE = "code"
MANHOLE_LABEL_BOTTOM = "bottom"
MANHOLE_LABEL_GROUND = "ground"


def _minmax(layer, field):
    idx = layer.fields().indexOf(field)
    if idx < 0:
        return 0.0, 1.0
    mn = layer.minimumValue(idx)
    mx = layer.maximumValue(idx)
    if mn is None or mx is None:
        return 0.0, 1.0
    if mn == mx:
        return mn, mn + 1.0
    return mn, mx


def _ramp_expr(field, mn, mx, ramp="Spectral"):
    # Spectral: low -> red, high -> blue; invert so deeper (lower) reads cool.
    return f"ramp_color('{ramp}', scale_linear(\"{field}\", {mn}, {mx}, 1, 0))"


def _graduated(field, mn, mx, make_symbol, classes=5):
    """Build a QgsGraduatedSymbolRenderer over ``field`` (mn..mx), blue->red."""
    colors = ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"]
    ranges = []
    step = (mx - mn) / classes if mx > mn else 1.0
    for i in range(classes):
        lo = mn + i * step
        hi = mn + (i + 1) * step if i < classes - 1 else mx + 1e-9
        symbol = make_symbol(colors[i])
        ranges.append(QgsRendererRange(lo, hi, symbol, f"{lo:.2f}–{hi:.2f}"))
    return QgsGraduatedSymbolRenderer(field, ranges)


def _apply_label(layer, expression):
    if expression is None:
        layer.setLabelsEnabled(False)
        layer.setLabeling(None)
        layer.triggerRepaint()
        return
    from qgis.core import QgsWkbTypes
    settings = QgsPalLayerSettings()
    settings.fieldName = expression
    settings.isExpression = True
    if layer.geometryType() == QgsWkbTypes.LineGeometry:
        settings.placement = QgsPalLayerSettings.Line  # parallel to the pipe
    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def apply_pipe_style(layer, color_mode, width_mode, label_mode):
    def _line(color):
        s = QgsLineSymbol.createSimple({"color": PIPE_DEFAULT, "width": "0.66"})
        s.setColor(QColor(color))
        if width_mode == PIPE_WIDTH_DIAMETER:
            mn, mx = _minmax(layer, "diameter")
            expr = f'scale_linear("diameter", {mn}, {mx}, 0.4, 3.0)'
            s.symbolLayer(0).setDataDefinedProperty(
                QgsSymbolLayer.PropertyStrokeWidth, QgsProperty.fromExpression(expr))
        return s

    if color_mode == PIPE_COLOR_BOB:
        mn, mx = _minmax(layer, "bob_avg")
        layer.setRenderer(_graduated("bob_avg", mn, mx, _line))
    elif color_mode == PIPE_COLOR_SLOPE:
        mn, mx = _minmax(layer, "slope")
        layer.setRenderer(_graduated("slope", mn, mx, _line))
    else:
        layer.setRenderer(QgsSingleSymbolRenderer(_line(PIPE_DEFAULT)))

    label_expr = {
        PIPE_LABEL_NONE: None,
        PIPE_LABEL_CODE: '"code"',
        PIPE_LABEL_BOB: 'format_number("bob1", 2) || \' / \' || format_number("bob2", 2)',
        PIPE_LABEL_DIAMETER: 'format_number("diameter", 2)',
    }.get(label_mode)
    _apply_label(layer, label_expr)
    layer.triggerRepaint()


def apply_manhole_style(layer, color_mode, label_mode):
    def _marker(color):
        return QgsMarkerSymbol.createSimple(
            {"name": "circle", "color": color, "size": "2.4",
             "outline_color": "#ffffff", "outline_width": "0.2"})

    if color_mode == MANHOLE_COLOR_BOTTOM:
        mn, mx = _minmax(layer, "bottom_level")
        layer.setRenderer(_graduated("bottom_level", mn, mx, _marker))
    elif color_mode == MANHOLE_COLOR_GROUND:
        mn, mx = _minmax(layer, "ground_level")
        layer.setRenderer(_graduated("ground_level", mn, mx, _marker))
    else:
        layer.setRenderer(QgsSingleSymbolRenderer(_marker(MANHOLE_DEFAULT)))

    label_expr = {
        MANHOLE_LABEL_NONE: None,
        MANHOLE_LABEL_CODE: '"code"',
        MANHOLE_LABEL_BOTTOM: 'format_number("bottom_level", 2)',
        MANHOLE_LABEL_GROUND: 'format_number("ground_level", 2)',
    }.get(label_mode)
    _apply_label(layer, label_expr)
    layer.triggerRepaint()


# Segment colour modes.
SEGMENT_COLOR_FLOODED = "flooded"   # vullingsgraad
SEGMENT_COLOR_WATER = "water"       # waterhoogte
SEGMENT_COLOR_DEPTH = "depth"       # max. waterdiepte


def apply_segment_style(layer, color_mode):
    """Colour the segments layer by flooded_pct, water_level, or water_depth_max."""
    field = {SEGMENT_COLOR_WATER: "water_level",
             SEGMENT_COLOR_DEPTH: "water_depth_max"}.get(color_mode)
    if field is None:
        from drainworks_plugin.styling.symbology import style_segments
        style_segments(layer)   # default graduated flooded_pct look
        return
    mn, mx = _minmax(layer, field)

    def _seg_line(color):
        return QgsLineSymbol.createSimple({"color": color, "width": "1.6"})

    layer.setRenderer(_graduated(field, mn, mx, _seg_line))
    layer.triggerRepaint()
