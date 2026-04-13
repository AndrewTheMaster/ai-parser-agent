"""Cascade dictionary lookup: EXACT -> NORMALIZED -> COMPONENT over indexed PDF chunks."""

from __future__ import annotations

import re
from pathlib import Path

from app.adapters.blacks_pdf_index import BlacksPdfIndex, DictChunk
from app.nlp.normalize import expand_variants, important_tokens, normalize_phrase, tokenize
from app.schemas.term import DefinitionHit, DictionaryStatus, PipelineConfig, TermCandidate, TermLookupResult


def _contains_word_ci(text: str, token: str) -> bool:
    return bool(re.search(rf"\b{re.escape(token.lower())}\b", text.lower()))


def _token_coverage_ratio(text: str, tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    matched = sum(1 for t in tokens if _contains_word_ci(text, t))
    return matched / len(tokens)


def _token_matches_count(text: str, tokens: list[str]) -> int:
    return sum(1 for t in tokens if _contains_word_ci(text, t))


def _phrase_ngrams(tokens: list[str], n: int) -> list[str]:
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _contains_phrase_ci(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


def _ordered_tokens_match(text: str, tokens: list[str], *, max_gap_words: int = 4) -> bool:
    """
    Check whether tokens appear in order with limited gaps between them.
    This is robust to punctuation/extra words and helps avoid random BM25 matches.
    """
    if not tokens:
        return False
    pattern = r"\b" + re.escape(tokens[0]) + r"\b"
    for tok in tokens[1:]:
        pattern += r"(?:\W+\w+){0," + str(max_gap_words) + r"}\W+\b" + re.escape(tok) + r"\b"
    return bool(re.search(pattern, text.lower(), flags=re.IGNORECASE))


def _extract_quote_window(
    chunk_text: str,
    needle: str | None,
    *,
    min_chars: int,
    max_chars: int,
) -> str:
    """Return a verbatim substring of chunk_text, preferring a window around needle."""
    text = chunk_text
    if not text:
        return ""
    if needle:
        low = text.lower()
        idx = low.find(needle.lower())
        if idx >= 0:
            half = max_chars // 2
            start = max(0, idx - half)
            end = min(len(text), idx + len(needle) + half)
            window = text[start:end]
            if len(window) >= min_chars:
                return window.strip()
    # fallback: beginning of chunk trimmed
    t = text.strip()
    return t[:max_chars] if len(t) > max_chars else t


def _best_present_needle(text: str, tokens: list[str], fallback: str | None = None) -> str | None:
    for tok in tokens:
        if _contains_word_ci(text, tok):
            return tok
    return fallback


def _best_anchor_phrase(text: str, tokens: list[str]) -> str | None:
    """
    Prefer a multiword anchor that appears in text; fallback to first present token.
    """
    anchors = _phrase_ngrams(tokens, 3) + _phrase_ngrams(tokens, 2)
    for a in anchors:
        if _contains_phrase_ci(text, a):
            return a
    return _best_present_needle(text, tokens, None)


def _headword_hints(chunk: DictChunk) -> list[str]:
    first = chunk.text.strip().split("\n", 1)[0].strip()
    if not first:
        return []
    # Often: "word, n." or "word, vb."
    hint = re.sub(r"\s+", " ", first)[:160]
    return [hint] if hint else []


def lookup_term(
    term: TermCandidate,
    index: BlacksPdfIndex,
    cfg: PipelineConfig,
) -> TermLookupResult:
    original = term.term_original.strip()
    normalized = term.term_normalized.strip() or normalize_phrase(original)
    variants = term.variants or expand_variants(original)
    searched = list(dict.fromkeys(variants + [normalized]))

    definitions: list[DefinitionHit] = []
    status = DictionaryStatus.NOT_FOUND
    notes_parts: list[str] = []

    # 1) EXACT (case-insensitive substring in any chunk)
    exact_chunks: list[DictChunk] = []
    for v in searched:
        hits = index.contains_exact_ci(v.strip())
        if hits:
            exact_chunks.extend(hits)
    if exact_chunks:
        status = DictionaryStatus.FOUND_EXACT
        seen: set[str] = set()
        for ch in exact_chunks[: cfg.bm25_top_k_chunks]:
            key = ch.chunk_id
            if key in seen:
                continue
            seen.add(key)
            needle = original if original.lower() in ch.text.lower() else searched[0]
            quote = _extract_quote_window(
                ch.text,
                needle,
                min_chars=cfg.min_quote_chars,
                max_chars=cfg.max_quote_chars,
            )
            definitions.append(
                DefinitionHit(
                    source_file=str(Path(ch.source_file).name),
                    page=ch.page,
                    chunk_id=ch.chunk_id,
                    quote=quote,
                    score=1.0,
                )
            )
            if len(definitions) >= cfg.top_k_definitions:
                break

    # 2) NORMALIZED: require all important normalized tokens in one chunk.
    # This is intentionally strict to avoid noisy BM25-only matches.
    if status == DictionaryStatus.NOT_FOUND:
        lemmas_full = tokenize(normalized or normalize_phrase(original))
        lemmas = important_tokens(normalized or original)
        if not lemmas:
            lemmas = lemmas_full
        if lemmas:
            hits = index.contains_all_tokens_ci(lemmas)
            if len(lemmas) >= 3 and hits:
                # Anchor long phrases by requiring at least one adjacent bigram/trigram.
                anchors = _phrase_ngrams(lemmas, 2) + _phrase_ngrams(lemmas, 3)
                anchored_hits: list[DictChunk] = []
                for ch in hits:
                    has_anchor = any(_contains_phrase_ci(ch.text, a) for a in anchors)
                    has_ordered = _ordered_tokens_match(ch.text, lemmas, max_gap_words=5)
                    if has_anchor or has_ordered:
                        anchored_hits.append(ch)
                hits = anchored_hits
            if hits:
                # Rank normalized hits by lexical tightness, not by page order.
                ranked: list[tuple[DictChunk, float]] = []
                for ch in hits:
                    coverage = _token_coverage_ratio(ch.text, lemmas)
                    ordered_bonus = 1.0 if _ordered_tokens_match(ch.text, lemmas, max_gap_words=5) else 0.0
                    ranked.append((ch, coverage + ordered_bonus))
                ranked.sort(key=lambda x: x[1], reverse=True)

                status = DictionaryStatus.FOUND_NORMALIZED
                notes_parts.append(f"normalized_tokens={lemmas}")
                for ch, _ in ranked[: cfg.top_k_definitions]:
                    needle = _best_anchor_phrase(ch.text, lemmas) or _best_present_needle(
                        ch.text, lemmas, lemmas[0] if lemmas else None
                    )
                    quote = _extract_quote_window(
                        ch.text,
                        needle,
                        min_chars=cfg.min_quote_chars,
                        max_chars=cfg.max_quote_chars,
                    )
                    definitions.append(
                        DefinitionHit(
                            source_file=str(Path(ch.source_file).name),
                            page=ch.page,
                            chunk_id=ch.chunk_id,
                            quote=quote,
                            score=0.8,
                        )
                    )

    # 3) COMPONENT: important tokens one by one via BM25, then coverage filter.
    if status == DictionaryStatus.NOT_FOUND:
        imp = important_tokens(original)
        if not imp:
            imp = tokenize(original)
        collected: list[tuple[DictChunk, float]] = []
        for tok in imp[:4]:
            ranked = index.bm25_top([tok], max(10, cfg.bm25_top_k_chunks // 4))
            collected.extend(ranked)
        collected.sort(key=lambda x: x[1], reverse=True)
        seen_ids: set[str] = set()
        uniq: list[tuple[DictChunk, float]] = []
        min_required = 1
        if len(imp) >= 3:
            min_required = 2
        if len(imp) >= 5:
            min_required = 3
        anchors = _phrase_ngrams(imp, 2) + _phrase_ngrams(imp, 3)
        for ch, sc in collected:
            if ch.chunk_id in seen_ids:
                continue
            matches = _token_matches_count(ch.text, imp)
            if matches < min_required:
                continue
            if len(imp) >= 4 and anchors:
                # For long phrases, demand at least one explicit multi-word anchor.
                has_anchor = any(_contains_phrase_ci(ch.text, a) for a in anchors)
                has_ordered = _ordered_tokens_match(ch.text, imp, max_gap_words=5)
                if not (has_anchor or has_ordered):
                    continue
            seen_ids.add(ch.chunk_id)
            # blend BM25 score with lexical coverage to rank cleaner chunks first
            coverage = _token_coverage_ratio(ch.text, imp)
            ordered_bonus = 2.0 if _ordered_tokens_match(ch.text, imp, max_gap_words=5) else 0.0
            blended = float(sc) + (coverage * 5.0) + ordered_bonus
            uniq.append((ch, blended))
            if len(uniq) >= cfg.top_k_definitions:
                break
        if uniq:
            status = DictionaryStatus.FOUND_COMPONENT
            notes_parts.append(f"component_tokens={imp}; min_required={min_required}")
            for ch, sc in uniq:
                needle = _best_anchor_phrase(ch.text, imp) or _best_present_needle(
                    ch.text, imp, imp[0] if imp else None
                )
                quote = _extract_quote_window(
                    ch.text,
                    needle,
                    min_chars=cfg.min_quote_chars,
                    max_chars=cfg.max_quote_chars,
                )
                definitions.append(
                    DefinitionHit(
                        source_file=str(Path(ch.source_file).name),
                        page=ch.page,
                        chunk_id=ch.chunk_id,
                        quote=quote,
                        score=float(sc),
                    )
                )

    matched_hints: list[str] = []
    for d in definitions[:1]:
        # re-find chunk for hint - optional
        pass
    if definitions:
        # best-effort headword from first definition chunk text via page lookup
        first_id = definitions[0].chunk_id
        for ch in index.chunks:
            if ch.chunk_id == first_id:
                matched_hints = _headword_hints(ch)
                break

    confidence = 0.0
    if status == DictionaryStatus.FOUND_EXACT:
        confidence = 0.95
    elif status == DictionaryStatus.FOUND_NORMALIZED:
        confidence = 0.78
    elif status == DictionaryStatus.FOUND_COMPONENT:
        confidence = min(0.72, max(0.35, definitions[0].score / 50.0 if definitions else 0.35))

    manual_review = status in (
        DictionaryStatus.FOUND_COMPONENT,
        DictionaryStatus.FOUND_NORMALIZED,
    ) or confidence < 0.8

    return TermLookupResult(
        term_original=original,
        term_normalized=normalized or normalize_phrase(original),
        dictionary_status=status,
        matched_headwords_hint=matched_hints,
        searched_forms=searched,
        definitions=definitions,
        notes="; ".join(notes_parts),
        manual_review=manual_review,
        confidence=confidence,
    )


def lookup_all_terms(
    terms: list[TermCandidate],
    index: BlacksPdfIndex,
    cfg: PipelineConfig,
) -> list[TermLookupResult]:
    return [lookup_term(t, index, cfg) for t in terms]
