#!/usr/bin/env bash
# Build a QGIS plugin ZIP for Drainworks.
#
# Produces dist/drainworks-<version>.zip containing a single top-level `drainworks_plugin/`
# directory, with the dev `external/rgs_ribx` symlink replaced by a real vendored copy and
# __pycache__/*.pyc stripped. The vendored pyqtgraph under external/ is kept.
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
plugin="$here/drainworks_plugin"
rgs_src="$here/../rgs-ribx/src/rgs_ribx"

version="$(sed -n 's/^version=//p' "$plugin/metadata.txt" | head -1)"
[ -n "$version" ] || { echo "could not read version from metadata.txt" >&2; exit 1; }
[ -d "$rgs_src" ] || { echo "rgs_ribx source not found at $rgs_src" >&2; exit 1; }

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
dest="$stage/drainworks_plugin"

# Copy the plugin, dereferencing symlinks (so external/rgs_ribx becomes a real copy).
rsync -aL \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' \
  --exclude='external/rgs_ribx' \
  "$plugin/" "$dest/"

# Vendor a clean copy of rgs_ribx (rsync -L on a symlinked dir can be finicky; do it explicitly).
rsync -a --exclude='__pycache__' --exclude='*.pyc' "$rgs_src/" "$dest/external/rgs_ribx/"

mkdir -p "$here/dist"
zip="$here/dist/drainworks-$version.zip"
rm -f "$zip"
( cd "$stage" && zip -rq "$zip" drainworks_plugin )

echo "built $zip"
echo "  rgs_ribx vendored: $([ -f "$dest/external/rgs_ribx/__init__.py" ] && echo yes || echo NO)"
echo "  metadata at top:   $([ -f "$dest/metadata.txt" ] && echo yes || echo NO)"
unzip -l "$zip" | grep -E "metadata.txt|external/rgs_ribx/__init__.py" | head
