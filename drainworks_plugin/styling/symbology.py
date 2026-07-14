"""Apply renderers to the sewer layers."""

from qgis.core import (
    QgsGraduatedSymbolRenderer,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsRendererRange,
    QgsSingleSymbolRenderer,
    QgsUnitTypes,
)
from qgis.PyQt.QtGui import QColor

from drainworks_plugin.styling.colors import (
    FLOODED_HIGH,
    FLOODED_LOW,
    MANHOLE_DEFAULT,
    PIPE_DEFAULT,
)


def style_pipes(layer) -> None:
    """Render pipes as blue lines, width 2.5 px.

    Width is in screen pixels (not millimetres) so it matches the pixel-based
    widths used by the switchable styling in ``views.apply_pipe_style`` and the
    line stays a constant thickness on screen at any map scale.
    """
    symbol = QgsLineSymbol.createSimple({"color": PIPE_DEFAULT, "width": "2.5"})
    symbol.setOutputUnit(QgsUnitTypes.RenderPixels)
    # Replace the whole renderer (not just the symbol) so the layer-tree legend
    # swatch updates to match the canvas instead of QGIS's random default color.
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.triggerRepaint()


def style_manholes(layer) -> None:
    """Render manholes as green circles with a thin white outline.

    Size and outline width are in screen pixels (not millimetres) so the marker
    stays a constant size on screen at any map scale, matching the pixel-based
    line widths of the pipe and segment layers.
    """
    symbol = QgsMarkerSymbol.createSimple(
        {
            "name": "circle",
            "color": MANHOLE_DEFAULT,
            "size": "9",
            "outline_color": "#ffffff",
            "outline_width": "0.75",
        }
    )
    symbol.setOutputUnit(QgsUnitTypes.RenderPixels)
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.triggerRepaint()


def style_segments(layer) -> None:
    """Graduated blue->red LINE renderer on the ``flooded_pct`` field (0..1).

    Uses a graduated renderer so the layer-tree legend shows the flood classes.
    Line widths are in screen pixels (not millimetres), matching the other
    layers, so the class thickness stays constant on screen at any map scale.
    """
    ranges = []
    steps = [
        (0.0, 0.25, FLOODED_LOW, "3"),
        (0.25, 0.5, "#7fcdbb", "5"),
        (0.5, 0.75, "#fec44f", "8"),
        (0.75, 1.01, FLOODED_HIGH, "11"),
    ]
    for lower, upper, hex_color, width in steps:
        symbol = QgsLineSymbol.createSimple({"color": hex_color, "width": width})
        symbol.setOutputUnit(QgsUnitTypes.RenderPixels)
        symbol.setColor(QColor(hex_color))
        label = f"{int(lower * 100)}–{int(min(upper, 1.0) * 100)}%"
        ranges.append(QgsRendererRange(lower, upper, symbol, label))
    renderer = QgsGraduatedSymbolRenderer("flooded_pct", ranges)
    layer.setRenderer(renderer)
    layer.triggerRepaint()
