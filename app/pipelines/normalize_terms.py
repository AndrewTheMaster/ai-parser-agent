"""Ensure each TermCandidate has normalized form and search variants."""

from __future__ import annotations

from app.nlp.normalize import expand_variants, normalize_phrase
from app.schemas.term import TermCandidate


def enrich_term_variants(terms: list[TermCandidate]) -> list[TermCandidate]:
    out: list[TermCandidate] = []
    for t in terms:
        norm = t.term_normalized or normalize_phrase(t.term_original)
        variants = t.variants or expand_variants(t.term_original)
        merged = list(dict.fromkeys(variants + [norm, t.term_original]))
        out.append(
            TermCandidate(
                term_original=t.term_original,
                term_normalized=norm,
                variants=merged,
                source_chunk_id=t.source_chunk_id,
            )
        )
    return out
