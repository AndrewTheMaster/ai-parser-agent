"""Export lookup results to JSON and Excel (technical + human-friendly views)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.schemas.term import TermWithRuMapping


def results_to_records(results: list[TermWithRuMapping]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in results:
        defs = [
            {
                "source_file": d.source_file,
                "page": d.page,
                "chunk_id": d.chunk_id,
                "score": d.score,
                "quote": d.quote,
            }
            for d in r.definitions
        ]
        ru = r.ru_mapping
        rows.append(
            {
                "term_original": r.term_original,
                "term_normalized": r.term_normalized,
                "dictionary_status": r.dictionary_status.value,
                "matched_headwords_hint": "; ".join(r.matched_headwords_hint),
                "searched_forms": "; ".join(r.searched_forms),
                "definitions_json": json.dumps(defs, ensure_ascii=False),
                "definitions_count": len(defs),
                "notes": r.notes,
                "manual_review": r.manual_review,
                "confidence": r.confidence,
                "ru_translation": ru.translation_candidate if ru else "",
                "ru_law_name": ru.law_name if ru else "",
                "ru_article": ru.article if ru else "",
                "ru_context_quote": ru.context_quote if ru else "",
                "ru_confidence": ru.confidence if ru else "",
                "ru_manual_review": ru.manual_review if ru else "",
            }
        )
    return rows


def export_json(results: list[TermWithRuMapping], path: Path) -> None:
    payload = [r.model_dump(mode="json") for r in results]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_xlsx(results: list[TermWithRuMapping], path: Path) -> None:
    rows = results_to_records(results)
    df = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def export_human_xlsx(results: list[TermWithRuMapping], path: Path) -> None:
    """
    Non-technical report for end users:
    word | status | confidence | definition
    """
    rows: list[dict[str, Any]] = []
    for r in results:
        first_def = r.definitions[0].quote.strip() if r.definitions else ""
        rows.append(
            {
                "word": r.term_original,
                "status": r.dictionary_status.value,
                "confidence": round(float(r.confidence), 3),
                "definition": first_def,
            }
        )
    df = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)
