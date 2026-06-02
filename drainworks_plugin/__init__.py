"""Drainworks QGIS plugin entry point."""

import os
import sys


def _ensure_rgs_ribx_on_path():
    """Make ``rgs_ribx`` importable without installing it into QGIS's Python.

    Tries a normal import first; if that fails, falls back to a sibling
    ``rgs-ribx`` checkout's ``src`` directory. Adjust the fallback path if your
    checkout lives elsewhere.
    """
    try:
        import rgs_ribx  # noqa: F401
        return
    except ImportError:
        pass
    candidates = [
        os.path.expanduser("~/Documents/GitHub/rgs-ribx/src"),
        os.path.join(os.path.dirname(__file__), "..", "..", "rgs-ribx", "src"),
    ]
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)
            return


_ensure_rgs_ribx_on_path()


def classFactory(iface):  # noqa: N802 (QGIS-required name)
    """Return the plugin instance. Called by QGIS when loading the plugin.

    Parameters
    ----------
    iface : qgis.gui.QgisInterface
        The running QGIS interface handed in by QGIS.
    """
    from drainworks_plugin.plugin import DrainworksPlugin

    return DrainworksPlugin(iface)
