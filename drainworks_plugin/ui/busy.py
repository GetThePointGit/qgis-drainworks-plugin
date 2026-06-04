"""A messageBar busy indicator with an animated (indeterminate) progress bar."""

from qgis.core import Qgis
from qgis.PyQt.QtWidgets import QProgressBar, QStyleFactory


def start_busy(iface, text):
    """Show a messageBar item with an animated (indeterminate) progress bar; returns it.

    The bar is forced to the Fusion style: the native macOS style renders a
    ``range(0, 0)`` bar as a static *full* bar (it looks stuck at 100%), whereas
    Fusion animates it so it reads as "working".
    """
    msg = iface.messageBar().createMessage("Drainworks", text)
    bar = QProgressBar()
    bar.setRange(0, 0)            # indeterminate / animated
    bar.setMaximumWidth(200)
    bar.setTextVisible(False)
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        # setStyle does not take ownership; keep a reference so it outlives the bar.
        bar._fusion_style = fusion
        bar.setStyle(fusion)
    msg.layout().addWidget(bar)
    return iface.messageBar().pushWidget(msg, Qgis.Info)


def set_busy_text(item, text):
    """Update the text of a busy item (best-effort; no-op if unsupported/None)."""
    if item is None:
        return
    try:
        item.setText(text)
    except (AttributeError, RuntimeError):
        pass


def stop_busy(iface, item):
    """Remove a busy item (no-op if None)."""
    if item is not None:
        iface.messageBar().popWidget(item)
