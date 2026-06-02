"""Apply renderers to the sewer layers."""

from qgis.core import (
    QgsGraduatedSymbolRenderer,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsRendererRange,
)
from qgis.PyQt.QtGui import QColor

from drainworks_plugin.styling.colors import (
    FLOODED_HIGH,
    FLOODED_LOW,
    MANHOLE_DEFAULT,
    PIPE_DEFAULT,
)


def style_pipes(layer) -> None:
    """Render pipes as white lines, width 0.6 mm."""
    symbol = QgsLineSymbol.createSimple({"color": PIPE_DEFAULT, "width": "0.6"})
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def style_manholes(layer) -> None:
    """Render manholes as green circles, size 2.4 mm."""
    symbol = QgsMarkerSymbol.createSimple(
        {"name": "circle", "color": MANHOLE_DEFAULT, "size": "2.4"}
    )
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def style_measurements_by_flooded(layer) -> None:
    """Graduated blue->red renderer on the ``flooded_pct`` field (0..1)."""
    ranges = []
    steps = [
        (0.0, 0.25, FLOODED_LOW),
        (0.25, 0.5, "#7fcdbb"),
        (0.5, 0.75, "#fec44f"),
        (0.75, 1.01, FLOODED_HIGH),
    ]
    for lower, upper, hex_color in steps:
        symbol = QgsMarkerSymbol.createSimple(
            {"name": "circle", "color": hex_color, "size": "2.6"}
        )
        symbol.setColor(QColor(hex_color))
        label = f"{int(lower * 100)}–{int(min(upper, 1.0) * 100)}%"
        ranges.append(QgsRendererRange(lower, upper, symbol, label))
    renderer = QgsGraduatedSymbolRenderer("flooded_pct", ranges)
    layer.setRenderer(renderer)
    layer.triggerRepaint()
