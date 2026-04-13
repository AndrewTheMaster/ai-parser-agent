#!/usr/bin/env bash
set -euo pipefail

# One-click launcher for non-technical use.
# Usage:
#   ./run_simple.sh [terms_file] [dictionary_dir] [output_dir]

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

TERMS_FILE="${1:-$PROJECT_DIR/data/sample_terms.txt}"
DICTIONARY_DIR="${2:-$PROJECT_DIR}"
OUTPUT_DIR="${3:-$PROJECT_DIR/output_simple}"

if [[ ! -f "$TERMS_FILE" ]]; then
  echo "Terms file not found: $TERMS_FILE"
  exit 1
fi

if [[ ! -d "$DICTIONARY_DIR" ]]; then
  echo "Dictionary directory not found: $DICTIONARY_DIR"
  exit 1
fi

if [[ ! -d "$PROJECT_DIR/.venv" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "$PROJECT_DIR/.venv"
  "$PROJECT_DIR/.venv/bin/pip" install -e "$PROJECT_DIR"
fi

echo "Running lookup..."
"$PROJECT_DIR/.venv/bin/legal-agent" run-simple \
  --terms "$TERMS_FILE" \
  --dictionary-dir "$DICTIONARY_DIR" \
  --dictionary-glob "*.pdf" \
  --output "$OUTPUT_DIR"

echo ""
echo "Done: $OUTPUT_DIR/results_human.xlsx"
