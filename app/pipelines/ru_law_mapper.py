"""Optional Phase-2: translate term to Russian and retrieve snippets from a local RU law corpus."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from rank_bm25 import BM25Okapi

from app.nlp.normalize import clean_text
from app.schemas.term import PipelineConfig, RuLawHit, TermLookupResult, TermWithRuMapping


@dataclass
class RuChunk:
    chunk_id: str
    source_file: str
    text: str


def tokenize_ru(s: str) -> list[str]:
    """Whitespace tokenizer keeping Cyrillic/Latin letters (Unicode word chars)."""
    s = s.lower()
    s = re.sub(r"[^\w\s\-]", " ", s, flags=re.UNICODE)
    return [p for p in s.split() if len(p) > 2]


def _load_txt_corpus(paths: list[Path], *, max_chars: int = 2000) -> list[RuChunk]:
    chunks: list[RuChunk] = []
    for p in paths:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        text = clean_text(text)
        if not text:
            continue
        stem = p.name
        i = 0
        start = 0
        n = len(text)
        overlap = 300
        while start < n:
            end = min(start + max_chars, n)
            piece = text[start:end].strip()
            if piece:
                chunks.append(
                    RuChunk(chunk_id=f"{stem}::ru::{i}", source_file=str(p.resolve()), text=piece)
                )
                i += 1
            if end >= n:
                break
            start = max(0, end - overlap)
    return chunks


class RuLawMiniIndex:
    def __init__(self, chunks: list[RuChunk]):
        self.chunks = chunks
        tok = [tokenize_ru(c.text) for c in chunks]
        self._tok = [t if t else ["__empty__"] for t in tok]
        self._bm25 = BM25Okapi(self._tok)

    def top(self, query_tokens: list[str], k: int) -> list[tuple[RuChunk, float]]:
        if not query_tokens or not self.chunks:
            return []
        scores = self._bm25.get_scores(query_tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
        return [(self.chunks[i], float(s)) for i, s in ranked if s > 0]


def _llm_translate_phrase(phrase: str, cfg: PipelineConfig) -> str:
    llm = ChatOpenAI(
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key,
        model=cfg.llm_model,
        temperature=min(cfg.llm_temperature, 0.3),
    )
    msg = llm.invoke(
        [
            SystemMessage(
                content="You translate English legal terms to concise Russian legal wording. "
                "Return a single line: Russian term only, no quotes."
            ),
            HumanMessage(content=f"Term:\n{phrase}\n\nRussian:"),
        ]
    )
    content = msg.content if isinstance(msg.content, str) else str(msg.content)
    return clean_text(content.splitlines()[0][:500])


def _guess_article_from_context(text: str) -> str:
    m = re.search(r"(ст\.\s*\d+|статья\s+\d+)", text, flags=re.IGNORECASE)
    return m.group(1) if m else ""


def _guess_law_name(text: str) -> str:
    # Heuristic: line starting with Федеральный / Кодекс
    for line in text.splitlines()[:8]:
        line = line.strip()
        if "Федеральный" in line or "Кодекс" in line or "Закон" in line:
            return line[:240]
    return ""


def map_term_to_ru_law(
    base: TermLookupResult,
    cfg: PipelineConfig,
    ru_corpus_paths: list[str],
    *,
    top_k: int = 3,
) -> TermWithRuMapping:
    phrase = base.term_original
    ru_hit = RuLawHit(
        translation_candidate="",
        law_name="",
        article="",
        context_quote="",
        confidence=0.0,
        manual_review=True,
    )

    try:
        ru_hit.translation_candidate = _llm_translate_phrase(phrase, cfg)
    except Exception:
        ru_hit.translation_candidate = ""

    paths = [Path(p) for p in ru_corpus_paths if p]
    txt_paths = [p for p in paths if p.suffix.lower() == ".txt" and p.is_file()]
    chunks = _load_txt_corpus(txt_paths)
    if chunks:
        idx = RuLawMiniIndex(chunks)
        qtok = tokenize_ru(ru_hit.translation_candidate or phrase)
        ranked = idx.top(qtok, top_k)
        if ranked:
            best, score = ranked[0]
            ru_hit.context_quote = best.text[:2000]
            ru_hit.article = _guess_article_from_context(best.text)
            ru_hit.law_name = _guess_law_name(best.text) or Path(best.source_file).stem
            ru_hit.confidence = min(0.85, 0.35 + score / 25.0)
            ru_hit.manual_review = ru_hit.confidence < 0.55
    else:
        ru_hit.context_quote = (
            "RU corpus not configured: place .txt files and pass --ru-corpus paths "
            "to enable statutory snippet retrieval."
        )

    return TermWithRuMapping(**base.model_dump(), ru_mapping=ru_hit)


def map_results_optional(
    results: list[TermLookupResult],
    cfg: PipelineConfig,
    ru_corpus_paths: list[str],
) -> list[TermWithRuMapping]:
    out: list[TermWithRuMapping] = []
    for r in results:
        out.append(map_term_to_ru_law(r, cfg, ru_corpus_paths))
    return out
