#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────
# cc-usage installer — sets up the Übersicht widget and the launchd
# snapshot agent against a Python interpreter you specify.
#
# Usage:
#   ./install.sh /absolute/path/to/python3
#
# Requirements (the caller is responsible for):
#   · Übersicht installed (brew install --cask ubersicht)
#   · The chosen python3 has `requests` installed
#   · The chosen python3 binary has macOS Full Disk Access
#     (System Settings → Privacy & Security → Full Disk Access)
# ────────────────────────────────────────────────────────────────────────
set -euo pipefail

PYTHON_BIN="${1:-}"
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
    echo "usage: $0 /absolute/path/to/python3" >&2
    echo "the python binary must exist and be executable." >&2
    exit 2
fi

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "→ repo root: $REPO_ROOT"
echo "→ python:    $PYTHON_BIN"

# Sanity: does this python have `requests`?
if ! "$PYTHON_BIN" -c 'import requests' 2>/dev/null; then
    echo "✗ $PYTHON_BIN cannot import requests. Install it first:" >&2
    echo "    $PYTHON_BIN -m pip install requests" >&2
    exit 1
fi

# ── 1. Ensure the data dir exists and the DB schema is initialized ──────
mkdir -p "$REPO_ROOT/data"
"$PYTHON_BIN" -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
import claude_usage_db as d
d.connect().close()
print('  · db initialized at $REPO_ROOT/data/claude_usage.db')
"

# ── 2. Install the Übersicht widget ─────────────────────────────────────
UBERSICHT_DIR="$HOME/Library/Application Support/Übersicht/widgets"
if [[ ! -d "$UBERSICHT_DIR" ]]; then
    echo "! Übersicht widget dir not found at: $UBERSICHT_DIR"
    echo "  Install Übersicht first:  brew install --cask ubersicht"
    echo "  Then re-run this script."
else
    WIDGET_DST="$UBERSICHT_DIR/cc-usage.jsx"
    # Copy (not symlink — Übersicht's FSEvents watcher ignores symlink targets)
    # and rewrite the two config constants in-place.
    sed \
        -e "s|^const PYTHON_BIN = .*|const PYTHON_BIN = \"$PYTHON_BIN\"|" \
        -e "s|^const REPO_ROOT  = .*|const REPO_ROOT  = \"$REPO_ROOT\"|" \
        "$REPO_ROOT/ubersicht/cc-usage.jsx" > "$WIDGET_DST"
    echo "  · widget installed to $WIDGET_DST"
fi

# ── 3. Install the launchd snapshot agent ───────────────────────────────
LAUNCHD_DST="$HOME/Library/LaunchAgents/com.cc-usage.snapshot.plist"
sed \
    -e "s|__PYTHON_BIN__|$PYTHON_BIN|g" \
    -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
    "$REPO_ROOT/launchd/com.cc-usage.snapshot.plist.template" > "$LAUNCHD_DST"
echo "  · launchd plist written to $LAUNCHD_DST"

# Unload any prior copy, then bootstrap the new one.
launchctl bootout "gui/$(id -u)/com.cc-usage.snapshot" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_DST"
echo "  · launchd agent loaded (fires every 15 min, RunAtLoad=true)"

# ── 4. Smoke test ───────────────────────────────────────────────────────
echo ""
echo "→ smoke test: cc-usage --widget-json"
"$PYTHON_BIN" "$REPO_ROOT/claude_code_usage.py" --widget-json | head -c 200
echo ""
echo ""
echo "✓ install complete. Add this to your shell rc for a CLI alias:"
echo "    alias cc-usage='$PYTHON_BIN $REPO_ROOT/claude_code_usage.py'"
