#!/usr/bin/env bash
set -euo pipefail

# One-click launcher for non-technical use.
#
# Usage:
#   ./run_simple.sh [terms_file] [dictionary_dir] [output_dir]
#
# Omit args (or pass "") to auto-detect:
#   Terms (.txt):
#     - Next to the .dmg on Mac: terms.txt, words.txt, sample_terms.txt, my_terms.txt
#     - Else: ./data/sample_terms.txt, ../terms.txt, etc. (see resolve_paths.py)
#   Dictionaries (*.pdf):
#     - ./dictionaries, ../dictionaries, or same folder as .dmg/dictionaries (Mac)
#
# Read-only DMG → venv, cache, default output under:
#   ~/Library/Application Support/LegalTermsAgent/

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

RESOLVE_PY="$PROJECT_DIR/scripts/macos/resolve_paths.py"

TERMS_OVERRIDE="${1:-}"
DICTIONARY_OVERRIDE="${2:-}"
OUTPUT_OVERRIDE="${3:-}"

if [[ -n "$TERMS_OVERRIDE" ]]; then
  TERMS_FILE="$TERMS_OVERRIDE"
elif TERMS_FILE="$(python3 "$RESOLVE_PY" terms "$PROJECT_DIR" 2>/dev/null)"; then
  :
elif [[ -f "$PROJECT_DIR/data/sample_terms.txt" ]]; then
  TERMS_FILE="$PROJECT_DIR/data/sample_terms.txt"
else
  echo ""
  echo "ERROR: No terms file found."
  echo "Add one of:"
  echo "  - data/sample_terms.txt inside the app folder, or"
  echo "  - Next to the .dmg on Mac: terms.txt (or words.txt / sample_terms.txt / my_terms.txt), or"
  echo "  - Next to the project folder: ../terms.txt"
  echo "Or pass the path as the first argument to this script."
  exit 1
fi

if [[ ! -f "$TERMS_FILE" ]]; then
  echo "Terms file not found: $TERMS_FILE"
  exit 1
fi

WORKROOT="$(python3 "$RESOLVE_PY" workroot "$PROJECT_DIR")"
mkdir -p "$WORKROOT/.cache"

if [[ -z "$OUTPUT_OVERRIDE" ]]; then
  OUTPUT_DIR="$WORKROOT/output_simple"
else
  OUTPUT_DIR="$OUTPUT_OVERRIDE"
fi

if [[ -n "$DICTIONARY_OVERRIDE" ]]; then
  DICTIONARY_DIR="$DICTIONARY_OVERRIDE"
else
  if ! DICTIONARY_DIR="$(python3 "$RESOLVE_PY" dictionary "$PROJECT_DIR")"; then
    echo ""
    echo "ERROR: No folder with dictionary PDFs found."
    echo "Put PDFs in one of these places:"
    echo "  1) $PROJECT_DIR/dictionaries/"
    echo "  2) $PROJECT_DIR/../dictionaries/"
    echo "  3) On Mac with DMG: same folder as the .dmg file → dictionaries/*.pdf"
    exit 1
  fi
fi

if [[ ! -d "$DICTIONARY_DIR" ]]; then
  echo "Dictionary directory not found: $DICTIONARY_DIR"
  exit 1
fi

VENV_DIR="$WORKROOT/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment in $VENV_DIR ..."
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install -e "$PROJECT_DIR"
fi

INDEX_CACHE="$WORKROOT/.cache/dictionary_index.pkl"

echo "Project:      $PROJECT_DIR"
echo "Work/cache:   $WORKROOT"
echo "Terms:        $TERMS_FILE"
echo "Dictionaries: $DICTIONARY_DIR"
echo "Output:       $OUTPUT_DIR"
echo ""

echo "Running lookup..."
"$VENV_DIR/bin/legal-agent" run-simple \
  --terms "$TERMS_FILE" \
  --dictionary-dir "$DICTIONARY_DIR" \
  --dictionary-glob "*.pdf" \
  --output "$OUTPUT_DIR" \
  --index-cache "$INDEX_CACHE"

echo ""
echo "Done: $OUTPUT_DIR/results_human.xlsx"
