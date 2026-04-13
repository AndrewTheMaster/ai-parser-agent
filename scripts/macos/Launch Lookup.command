#!/bin/bash
# Double-click in Finder to run (opens Terminal).
# Edit TERMS_FILE and DICTIONARY_DIR below if needed.

set -e
cd "$(dirname "$0")/../.."

TERMS_FILE="${TERMS_FILE:-./data/sample_terms.txt}"
DICTIONARY_DIR="${DICTIONARY_DIR:-./dictionaries}"
OUTPUT_DIR="${OUTPUT_DIR:-./output_simple}"

echo "Project: $(pwd)"
echo "Terms:   $TERMS_FILE"
echo "Dicts:   $DICTIONARY_DIR"
echo "Output:  $OUTPUT_DIR"
echo ""

if [[ ! -f "$TERMS_FILE" ]]; then
  echo "ERROR: Terms file not found: $TERMS_FILE"
  read -r -p "Press Enter to close..."
  exit 1
fi

if [[ ! -d "$DICTIONARY_DIR" ]]; then
  echo "ERROR: Dictionary folder not found: $DICTIONARY_DIR"
  echo "Create it and put PDF dictionaries inside."
  read -r -p "Press Enter to close..."
  exit 1
fi

bash ./run_simple.sh "$TERMS_FILE" "$DICTIONARY_DIR" "$OUTPUT_DIR"

echo ""
echo "Done. Open: $OUTPUT_DIR/results_human.xlsx"
read -r -p "Press Enter to close..."
