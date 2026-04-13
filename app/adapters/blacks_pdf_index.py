"""Index Black's Law Dictionary PDFs: per-page text, BM25 over chunks, fuzzy helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from app.nlp.normalize import tokenize


@dataclass
class DictChunk:
    chunk_id: str
    source_file: str
    page: int
    text: str


def _split_pages_pdf(path: Path) -> list[tuple[int, str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    out: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        t = t.replace("\r\n", "\n").replace("\r", "\n")
        if t.strip():
            out.append((i, t))
    return out


def _page_to_subchunks(page_num: int, page_text: str, source: str, max_chars: int) -> list[DictChunk]:
    """Split a long page into retrieval chunks (dictionary pages can be huge)."""
    text = re.sub(r"[ \t]+", " ", page_text).strip()
    if not text:
        return []
    if len(text) <= max_chars:
        cid = f"{Path(source).name}::p{page_num}::0"
        return [DictChunk(chunk_id=cid, source_file=source, page=page_num, text=text)]
    chunks: list[DictChunk] = []
    start = 0
    idx = 0
    n = len(text)
    overlap = min(400, max_chars // 5)
    while start < n:
        end = min(start + max_chars, n)
        piece = text[start:end].strip()
        if piece:
            cid = f"{Path(source).name}::p{page_num}::{idx}"
            chunks.append(DictChunk(chunk_id=cid, source_file=source, page=page_num, text=piece))
            idx += 1
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks


class BlacksPdfIndex:
    """BM25 retrieval over dictionary PDF chunks."""

    def __init__(self, chunks: list[DictChunk], tokenized_corpus: list[list[str]]):
        self.chunks = chunks
        self._tokenized = tokenized_corpus
        self._bm25 = BM25Okapi(tokenized_corpus)

    @classmethod
    def from_dict_chunks(cls, chunks: list[DictChunk]) -> BlacksPdfIndex:
        tokenized = [tokenize(c.text) for c in chunks]
        tokenized = [t if t else ["__empty__"] for t in tokenized]
        return cls(chunks, tokenized)

    @classmethod
    def build(cls, pdf_paths: list[Path], *, max_chars_per_chunk: int = 2800) -> BlacksPdfIndex:
        all_chunks: list[DictChunk] = []
        for p in pdf_paths:
            resolved = str(p.resolve())
            for page_num, page_text in _split_pages_pdf(p):
                all_chunks.extend(
                    _page_to_subchunks(page_num, page_text, resolved, max_chars_per_chunk)
                )
        return cls.from_dict_chunks(all_chunks)

    def bm25_top(self, query_tokens: list[str], k: int) -> list[tuple[DictChunk, float]]:
        if not query_tokens:
            return []
        scores = self._bm25.get_scores(query_tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
        out: list[tuple[DictChunk, float]] = []
        for idx, sc in ranked:
            if sc > 0:
                out.append((self.chunks[idx], float(sc)))
        return out

    def contains_exact_ci(self, phrase: str) -> list[DictChunk]:
        pl = phrase.lower().strip()
        if not pl:
            return []
        is_single = len(pl.split()) == 1
        pattern = re.compile(rf"\b{re.escape(pl)}\b", flags=re.IGNORECASE) if is_single else None
        hits: list[DictChunk] = []
        for c in self.chunks:
            if is_single:
                if pattern and pattern.search(c.text):
                    hits.append(c)
            elif pl in c.text.lower():
                hits.append(c)
        return hits

    def contains_all_tokens_ci(self, tokens: list[str]) -> list[DictChunk]:
        if not tokens:
            return []
        hits: list[DictChunk] = []
        tls = [t.lower().strip() for t in tokens if t.strip()]
        if not tls:
            return []
        patterns = [re.compile(rf"\b{re.escape(t)}\b", flags=re.IGNORECASE) for t in tls]
        for c in self.chunks:
            if all(p.search(c.text) for p in patterns):
                hits.append(c)
        return hits

    def to_serializable_meta(self) -> dict[str, Any]:
        return {
            "num_chunks": len(self.chunks),
            "sources": sorted({Path(c.source_file).name for c in self.chunks}),
        }
