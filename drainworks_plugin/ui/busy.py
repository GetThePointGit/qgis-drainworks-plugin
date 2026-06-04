"""A messageBar busy indicator with an indeterminate progress bar."""

from qgis.core import Qgis
from qgis.PyQt.QtWidgets import QProgressBar


def start_busy(iface, text):
    """Show a messageBar item with an animated (indeterminate) progress bar; returns it."""
    msg = iface.messageBar().createMessage("Drainworks", text)
    bar = QProgressBar()
    bar.setRange(0, 0)            # indeterminate / animated
    bar.setMaximumWidth(200)
    bar.setTextVisible(False)
    msg.layout().addWidget(bar)
    return iface.messageBar().pushWidget(msg, Qgis.Info)


def stop_busy(iface, item):
    """Remove a busy item (no-op if None)."""
    if item is not None:
        iface.messageBar().popWidget(item)
