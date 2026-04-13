#!/usr/bin/env bash
# Build an unsigned DMG for distribution on macOS.
# Requirements: bash, hdiutil (built into macOS)
#
# Usage (from repo root on a Mac):
#   bash scripts/macos/build_dmg.sh
#
# Output: dist/LegalTermsAgent-<VERSION>.dmg

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: DMG can only be built on macOS (needs hdiutil)."
  echo "You are on: $(uname -s). Run this script on a Mac, or zip the project folder instead."
  exit 1
fi

if ! command -v hdiutil >/dev/null 2>&1; then
  echo "ERROR: hdiutil not found. This tool is part of macOS."
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGE="$ROOT/dist/stage"
DMG_NAME="LegalTermsAgent"
VERSION="${VERSION:-0.1.0}"

rm -rf "$STAGE"
mkdir -p "$STAGE/$DMG_NAME"

# Copy project files (exclude heavy/local-only paths)
rsync -a \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '.cache' \
  --exclude 'output' \
  --exclude 'output_*' \
  --exclude 'output_simple' \
  --exclude 'output_fda*' \
  --exclude 'dictionaries' \
  --exclude '*.pdf' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  "$ROOT/" "$STAGE/$DMG_NAME/"

# Launcher must be executable
chmod +x "$STAGE/$DMG_NAME/scripts/macos/Launch Lookup.command" 2>/dev/null || true
chmod +x "$STAGE/$DMG_NAME/run_simple.sh" 2>/dev/null || true

# Short readme on the DMG volume
cat > "$STAGE/$DMG_NAME/START_HERE.txt" <<EOF
Legal Terms Agent (macOS)

Where to put dictionaries (choose one):

  A) Inside this app folder:  dictionaries/*.pdf
  B) Next to this folder on disk:  ../dictionaries/*.pdf
     (if you copied the folder to Desktop/MyAgent, use Desktop/dictionaries)
  C) Next to the .dmg file on your Mac:
       Desktop/LegalTermsAgent-0.1.0.dmg
       Desktop/dictionaries/*.pdf

Terms (one phrase per line), pick one:
  - Same folder as the .dmg: terms.txt  (recommended), or words.txt / sample_terms.txt / my_terms.txt
  - Or inside the app: data/sample_terms.txt
  - Or env TERMS_FILE=/path/to/file.txt

Run: double-click scripts/macos/Launch Lookup.command

First run needs internet once (pip install).

If the DMG is read-only: venv + cache live under ~/Library/Application Support/LegalTermsAgent/
Results (Excel) are written next to the .dmg when possible:
  <same folder as your .dmg>/output_simple/results_human.xlsx
If that folder is not writable, results fall back to:
  ~/Library/Application Support/LegalTermsAgent/output_simple/results_human.xlsx

Version: $VERSION
EOF

mkdir -p "$ROOT/dist"
DMG_PATH="$ROOT/dist/${DMG_NAME}-${VERSION}.dmg"
rm -f "$DMG_PATH"

hdiutil create -volname "$DMG_NAME" -srcfolder "$STAGE/$DMG_NAME" -ov -format UDZO "$DMG_PATH"

echo ""
echo "Created: $DMG_PATH"
echo "Users can open the DMG and double-click Launch Lookup.command after adding dictionaries/"
