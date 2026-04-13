# Legal Terms Agent (LangGraph)

Local pipeline to:

1. Extract English legal/regulatory terms from `.docx`/`.pdf` study pages (via an OpenAI-compatible LLM such as **LM Studio**), **or** consume a plain bullet/line list.
2. Look up definitions in **Black's Law Dictionary** PDF volumes using a **BM25 + cascade** matcher (`EXACT` → `NORMALIZED` → `COMPONENT`).
3. Optionally map terms to **Russian** wording + retrieve snippets from your own `.txt` corpus of Russian legislation (mini-RAG).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edit .env for LM Studio: LLM_BASE_URL / LLM_MODEL
```

Place dictionary PDFs in any folder. You can point to that folder with `--dictionary-dir`.

## Mac: full setup from scratch + DMG

See [docs/MAC_SETUP.md](docs/MAC_SETUP.md).

## CLI

```bash
# 1) Extract terms from a textbook (needs running LLM server)
legal-agent run-extract -i ./18-33.docx --out-json terms.json

# 2) Lookup a fixed list against Black's PDFs
legal-agent run-lookup \
  --terms ./data/sample_terms.txt \
  --dictionary-dir . \
  --dictionary-glob '*.pdf' \
  --output ./output

# 3) Full graph (uses --terms if provided, otherwise LLM extraction from --input)
legal-agent run-all -i ./18-33.docx --dictionary-dir . --dictionary-glob '*.pdf' --output ./output

# Optional RU mini-RAG (corpus is your local .txt files)
legal-agent run-lookup \
  --terms ./data/sample_terms.txt \
  --dictionary-dir . \
  --dictionary-glob '*.pdf' \
  --output ./output_ru \
  --enable-ru \
  --ru-corpus ./data/sample_ru_corpus.txt

# 4) Super-simple mode (for non-technical users)
legal-agent run-simple \
  --terms ./data/sample_terms.txt \
  --dictionary-dir ./dictionaries \
  --output ./output_simple
```

## Non-technical quick start

1. Put dictionary PDF files into `./dictionaries`.
2. Put your terms (one per line) into `./data/sample_terms.txt` (or any `.txt` file).
3. Run one command:

```bash
bash ./run_simple.sh ./data/sample_terms.txt ./dictionaries ./output_simple
```

Result file: `./output_simple/results_human.xlsx`

Notes:
- You do **not** need to create `.venv` manually. The script creates it automatically on first run.
- If the executable bit is missing after copying project files, use `bash ./run_simple.sh ...` (works without `chmod +x`).

Outputs:

- `results.json` — structured `TermWithRuMapping` records
- `results.xlsx` — flattened columns for review
- `results_human.xlsx` — simplified table: word / status / confidence / definition
- `run_meta.json` — which inputs/dictionaries were used

## Index cache

First PDF index build can take several minutes for large volumes. Reuse cache:

```bash
legal-agent run-lookup --terms data/sample_terms.txt --index-cache .cache/blacks_index.pkl
```

Skip cache with `--no-index-cache`.

## Architecture

LangGraph nodes live in `app/graphs/legal_terms_graph.py`:

`load_input` → `extract_terms` → `normalize_terms` → `lookup_definitions` → `validate_output` → `optional_ru` → `export_report`

## Evaluation notes

See [docs/EVALUATION.md](docs/EVALUATION.md).

## Limitations

- PDF retrieval uses page/chunk windows; quotes may start mid-entry if a dictionary page is split.
- `FOUND_COMPONENT` matches can be noisy for very generic words—review `manual_review` rows.
- LM Studio must expose an OpenAI-compatible `/v1/chat/completions` endpoint for extraction/RU translation steps.
