# Evaluation / quality checks

## Automated

```bash
cd /path/to/ai-parser-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Smoke test on real Black's PDFs (slow first run)

1. Start LM Studio server only for `run-extract` / LLM extraction paths.
2. Run lookup on the bundled sample list (indexes ~3 PDF volumes):

```bash
legal-agent run-lookup \
  --terms data/sample_terms.txt \
  --dictionary-glob '*Black*.pdf' \
  --output output_smoke \
  --index-cache .cache/blacks_index.pkl
```

3. Inspect `output_smoke/results.xlsx`:
   - `FOUND_COMPONENT` rows: expect higher manual review noise.
   - Acronyms / statute titles: often `NOT_FOUND` in Black's (expected).

## Tuning knobs

- Tighten component noise: edit `important_tokens()` / `STOPWORDS` in `app/nlp/normalize.py`.
- Retrieval granularity: `BlacksPdfIndex.build(max_chars_per_chunk=...)` in `app/adapters/blacks_pdf_index.py`.
- Quote length: `PipelineConfig.min_quote_chars` / `max_quote_chars`.

## Optional RU law mini-RAG

```bash
legal-agent run-lookup \
  --terms data/sample_terms.txt \
  --dictionary-glob '*Black*.pdf' \
  --output output_ru \
  --enable-ru \
  --ru-corpus data/sample_ru_corpus.txt \
  --no-index-cache
```

Note: translation still uses the local LLM; statutory snippets come only from your `--ru-corpus` text files.
