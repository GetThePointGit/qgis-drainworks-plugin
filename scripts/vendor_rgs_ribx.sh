#!/bin/bash
# Place rgs_ribx under drainworks_plugin/external/ so the plugin is self-contained.
#
#   ./scripts/vendor_rgs_ribx.sh            # dev: relative symlink to the sibling checkout (live edits)
#   ./scripts/vendor_rgs_ribx.sh --symlink  # same as above (explicit)
#   ./scripts/vendor_rgs_ribx.sh --copy     # distribution: a real copy committed into external/
#
# The dev symlink is git-ignored (a committed symlink to a sibling path breaks on
# a fresh clone). The --copy form produces real files you can commit for release.
set -euo pipefail

MODE="${1:---symlink}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXTERNAL="$REPO_ROOT/drainworks_plugin/external"
DEST="$EXTERNAL/rgs_ribx"
# Default source: sibling checkout's package dir.
SRC="${2:-$REPO_ROOT/../rgs-ribx/src/rgs_ribx}"

mkdir -p "$EXTERNAL"

case "$MODE" in
  --symlink)
    # Relative target so it resolves wherever both repos sit side by side.
    rm -rf "$DEST"
    ln -snf ../../../rgs-ribx/src/rgs_ribx "$DEST"
    echo "symlink: $DEST -> ../../../rgs-ribx/src/rgs_ribx"
    ;;
  --copy)
    if [ ! -d "$SRC" ]; then
      echo "source package not found: $SRC" >&2
      exit 1
    fi
    rm -rf "$DEST"
    cp -R "$SRC" "$DEST"
    find "$DEST" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
    echo "copied real package: $SRC -> $DEST"
    echo "Remember: 'git add -f drainworks_plugin/external/rgs_ribx' to commit it for distribution"
    echo "(it is git-ignored by default to keep the dev symlink out of the repo)."
    ;;
  *)
    echo "usage: $0 [--symlink|--copy] [SRC_PACKAGE_DIR]" >&2
    exit 2
    ;;
esac

# Verify the result imports (uses whichever python is on PATH; pass a QGIS python if you like).
PYTHONPATH="$EXTERNAL" python3 -c "import rgs_ribx; print('OK rgs_ribx', rgs_ribx.__version__)" 2>/dev/null \
  || echo "note: could not verify import with 'python3' on PATH (fine; QGIS will use its own)."
