# Vendored third-party packages

Pure-Python dependencies that some QGIS installs do not bundle. They are added
to `sys.path` by `drainworks_plugin/__init__.py` **only when the package is not
already importable** — the same pattern the *legger* plugin uses.

- `pyqtgraph` 0.13.3 — required by the side-view panel. QGIS-LTR3's Python does
  not ship it (QGIS-LTR2's does). This copy is pure Python (no compiled
  extensions) and works with the numpy 1.20.1 that QGIS 3.x LTR bundles.

`rgs_ribx` is **not** vendored here by default: on a dev machine it resolves
from the sibling `~/Documents/GitHub/rgs-ribx` checkout. To make the plugin
fully self-contained for distribution, copy `rgs-ribx/src/rgs_ribx` into this
folder — the loader checks `external/` before the sibling checkout.
