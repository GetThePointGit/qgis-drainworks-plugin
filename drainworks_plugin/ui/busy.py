"""messageBar progress indicator.

:func:`start_progress` shows a determinate percentage bar (returning a
:class:`BusyIndicator` handle) that visibly fills in steps; :func:`bind_progress`
drives it from a task's ``progress(percent, label)`` signal. Used by all three
pipeline steps (import / enrich / lost storage).
"""

from qgis.core import Qgis
from qgis.PyQt.QtWidgets import QProgressBar


class BusyIndicator:
    """Handle to a messageBar progress item: update its text/percentage, then stop.

    Parameters
    ----------
    iface : qgis.gui.QgisInterface
        The QGIS interface owning the message bar.
    item : qgis.gui.QgsMessageBarItem
        The pushed message-bar item (used to update text and to remove it).
    bar : qgis.PyQt.QtWidgets.QProgressBar
        The embedded progress bar (determinate or indeterminate).
    """

    def __init__(self, iface, item, bar):
        self._iface = iface
        self._item = item
        self._bar = bar

    def set_text(self, text):
        """Update the message text (best-effort; no-op if the item is gone)."""
        try:
            self._item.setText(text)
        except (AttributeError, RuntimeError):
            pass

    def set_progress(self, pct):
        """Set the bar to ``pct`` (0–100). No visible effect on an indeterminate bar."""
        try:
            self._bar.setValue(int(pct))
        except (RuntimeError, ValueError, TypeError):
            pass

    def stop(self):
        """Remove the item from the message bar (idempotent)."""
        if self._item is not None:
            try:
                self._iface.messageBar().popWidget(self._item)
            except RuntimeError:
                pass
            self._item = None


def _push(iface, text, bar) -> BusyIndicator:
    """Embed ``bar`` in a Drainworks message and push it; return its handle."""
    msg = iface.messageBar().createMessage("Drainworks", text)
    bar.setMaximumWidth(200)
    msg.layout().addWidget(bar)
    item = iface.messageBar().pushWidget(msg, Qgis.Info)
    return BusyIndicator(iface, item, bar)


def start_progress(iface, text) -> BusyIndicator:
    """Show a determinate percentage bar at 0%; advance it via ``set_progress``."""
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setTextVisible(True)      # show the % so the steps are visible
    return _push(iface, text, bar)


def bind_progress(task, indicator: BusyIndicator) -> None:
    """Drive ``indicator`` from a task's ``progress(percent, label)`` signal."""
    def _on(pct, label):
        indicator.set_progress(pct)
        if label:
            indicator.set_text(label)
    task.progress.connect(_on)
