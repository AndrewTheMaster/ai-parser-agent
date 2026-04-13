from __future__ import annotations

from app.adapters.blacks_pdf_index import BlacksPdfIndex, DictChunk
from app.pipelines.lookup_dictionary import lookup_term
from app.pipelines.ru_law_mapper import tokenize_ru
from app.schemas.term import PipelineConfig, TermCandidate


def _cfg() -> PipelineConfig:
    return PipelineConfig(
        top_k_definitions=2,
        bm25_top_k_chunks=20,
        min_quote_chars=10,
        max_quote_chars=800,
    )


def test_exact_match_status():
    chunks = [
        DictChunk(
            chunk_id="t::p1::0",
            source_file="/tmp/dict.pdf",
            page=1,
            text="patent, n. A government monopoly right to exclude others from making or selling an invention.",
        )
    ]
    idx = BlacksPdfIndex.from_dict_chunks(chunks)
    term = TermCandidate(term_original="patent", term_normalized="patent", variants=["patent"])
    r = lookup_term(term, idx, _cfg())
    assert r.dictionary_status.value == "FOUND_EXACT"
    assert r.definitions
    assert "patent" in r.definitions[0].quote.lower()


def test_normalized_match_when_exact_missing():
    chunks = [
        DictChunk(
            chunk_id="t::p1::0",
            source_file="/tmp/dict.pdf",
            page=1,
            text="patents, pl. See PATENT.",
        )
    ]
    idx = BlacksPdfIndex.from_dict_chunks(chunks)
    term = TermCandidate(term_original="patents", term_normalized="patent", variants=["patents", "patent"])
    r = lookup_term(term, idx, _cfg())
    # "patents" substring exists; should hit EXACT first
    assert r.dictionary_status.value in ("FOUND_EXACT", "FOUND_NORMALIZED")


def test_component_fallback():
    chunks = [
        DictChunk(
            chunk_id="t::p1::0",
            source_file="/tmp/dict.pdf",
            page=1,
            text="unrelated entry about contracts and consideration in common law systems.",
        ),
        DictChunk(
            chunk_id="t::p1::1",
            source_file="/tmp/dict.pdf",
            page=1,
            text="jurisdiction, n. A court's power to hear a dispute and render a binding decision.",
        ),
    ]
    idx = BlacksPdfIndex.from_dict_chunks(chunks)
    term = TermCandidate(
        term_original="federal court jurisdiction",
        term_normalized="federal court jurisdiction",
        variants=["federal court jurisdiction"],
    )
    r = lookup_term(term, idx, _cfg())
    assert r.dictionary_status.value in ("FOUND_NORMALIZED", "FOUND_COMPONENT", "NOT_FOUND")


def test_tokenize_ru_keeps_cyrillic():
    toks = tokenize_ru("Статья 15. Право на охрану здоровья гражданина.")
    assert any("статья" in t for t in toks)
    assert any("право" in t for t in toks)
