#!/bin/bash
# Double-click in Finder. DMG does nothing by itself — this script runs the lookup.
#
# Optional env (otherwise auto-detect like run_simple.sh):
#   TERMS_FILE=/path/to/terms.txt
#   DICTIONARY_DIR=/path/to/dictionaries
#   OUTPUT_DIR=/path/to/output_folder

set -e
cd "$(dirname "$0")/../.."

echo "Project: $(pwd)"
echo "Mode:    auto paths unless TERMS_FILE / DICTIONARY_DIR / OUTPUT_DIR env vars are set"
echo ""

T="${TERMS_FILE:-}"
D="${DICTIONARY_DIR:-}"
O="${OUTPUT_DIR:-}"

bash ./run_simple.sh "$T" "$D" "$O"

echo ""
echo "See printed paths above for results_human.xlsx"
read -r -p "Press Enter to close..."
