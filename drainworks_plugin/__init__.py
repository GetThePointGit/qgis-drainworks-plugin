"""Drainworks QGIS plugin entry point.

Dependency bootstrap follows the pattern used by the *legger* plugin: each
extra package is tried first as a normal import, and only if that fails is a
fallback directory added to ``sys.path``. ``pyqtgraph`` is vendored in
``external/`` (QGIS-LTR3's Python does not bundle it); ``rgs_ribx`` is resolved
from ``external/`` if vendored there, otherwise from a sibling checkout.
"""

import os
import sys
from pathlib import Path

OUR_DIR = Path(__file__).parent
EXTERNAL_DIR = OUR_DIR / "external"


def _add_to_path(directory) -> bool:
    """Append an existing directory to ``sys.path`` (idempotent). Returns True if usable."""
    directory = os.path.abspath(str(directory))
    if os.path.isdir(directory):
        if directory not in sys.path:
            sys.path.append(directory)
        return True
    return False


def _ensure_dependencies() -> None:
    """Make vendored/sibling dependencies importable when QGIS doesn't provide them."""
    # Plugin Reloader reloads this plugin's own modules but leaves rgs_ribx cached
    # in sys.modules, so edits to the library would be ignored until QGIS restarts.
    # Drop the cached package (and submodules) so the latest version is re-imported.
    for name in [m for m in list(sys.modules) if m == "rgs_ribx" or m.startswith("rgs_ribx.")]:
        del sys.modules[name]

    # pyqtgraph: required by the side-view panel; vendored in external/.
    try:
        import pyqtgraph  # noqa: F401
    except ImportError:
        _add_to_path(EXTERNAL_DIR)

    # rgs_ribx: try installed, then vendored external/, then a sibling checkout's src.
    try:
        import rgs_ribx  # noqa: F401
    except ImportError:
        _add_to_path(EXTERNAL_DIR)
        for candidate in (
            os.path.expanduser("~/Documents/GitHub/rgs-ribx/src"),
            OUR_DIR / ".." / ".." / "rgs-ribx" / "src",
        ):
            if _add_to_path(candidate):
                break


_ensure_dependencies()


def classFactory(iface):  # noqa: N802 (QGIS-required name)
    """Return the plugin instance. Called by QGIS when loading the plugin.

    Parameters
    ----------
    iface : qgis.gui.QgisInterface
        The running QGIS interface handed in by QGIS.
    """
    from drainworks_plugin.plugin import DrainworksPlugin

    return DrainworksPlugin(iface)
