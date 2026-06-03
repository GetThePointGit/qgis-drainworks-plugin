# Vendored third-party packages

Pure-Python dependencies that some QGIS installs do not bundle. They are added
to `sys.path` by `drainworks_plugin/__init__.py` **only when the package is not
already importable** — the same pattern the *legger* plugin uses.

## `pyqtgraph` 0.13.3
Required by the side-view panel. QGIS-LTR3's Python does not ship it
(QGIS-LTR2's does). Pure Python (no compiled extensions); works with the numpy
1.20.1 that QGIS 3.x LTR bundles. Committed to the repo (its bulky `examples/`
folder is git-ignored).

## `rgs_ribx`
Provided here too so the plugin is self-contained. Use the helper script:

```bash
# Development (default): live symlink to the sibling ../rgs-ribx checkout.
# Edits to the library take effect immediately. The symlink is git-ignored.
./scripts/vendor_rgs_ribx.sh --symlink

# Distribution: a real copy committed into external/ (for machines without the
# rgs-ribx checkout). Force-add it afterwards since external/rgs_ribx is ignored.
./scripts/vendor_rgs_ribx.sh --copy
git add -f drainworks_plugin/external/rgs_ribx
```

The loader checks `external/` before the sibling checkout, so whichever form is
present here wins.
