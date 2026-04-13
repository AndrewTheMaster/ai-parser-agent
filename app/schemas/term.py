"""MVP data contracts: statuses, term records, dictionary hits, report rows."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DictionaryStatus(str, Enum):
    """How a query term matched the Black's (or other) dictionary corpus."""

    FOUND_EXACT = "FOUND_EXACT"
    FOUND_NORMALIZED = "FOUND_NORMALIZED"
    FOUND_COMPONENT = "FOUND_COMPONENT"
    NOT_FOUND = "NOT_FOUND"


class DefinitionHit(BaseModel):
    """One retrieved passage from the dictionary (may be a chunk spanning partial entry)."""

    source_file: str
    page: int | None = None
    chunk_id: str | None = None
    quote: str = Field(..., description="Verbatim excerpt from the indexed dictionary text")
    score: float = 0.0


class TermCandidate(BaseModel):
    """After extraction, before / after normalization."""

    term_original: str
    term_normalized: str = ""
    variants: list[str] = Field(default_factory=list)
    source_chunk_id: str | None = None


class TermLookupResult(BaseModel):
    """Final row for one term after dictionary lookup + validation."""

    term_original: str
    term_normalized: str
    dictionary_status: DictionaryStatus
    matched_headwords_hint: list[str] = Field(
        default_factory=list,
        description="Best-effort headword guess from chunk start; not guaranteed for PDF chunks",
    )
    searched_forms: list[str] = Field(default_factory=list)
    definitions: list[DefinitionHit] = Field(default_factory=list)
    notes: str = ""
    manual_review: bool = False
    confidence: float = 0.0


class RuLawHit(BaseModel):
    """Optional Phase-2: Russian law analogue (placeholder-friendly)."""

    translation_candidate: str = ""
    law_name: str = ""
    article: str = ""
    context_quote: str = ""
    confidence: float = 0.0
    manual_review: bool = True


class TermWithRuMapping(TermLookupResult):
    """Lookup result extended with optional RU law mapping."""

    ru_mapping: RuLawHit | None = None


class PipelineConfig(BaseModel):
    """Runtime configuration (also loadable from env)."""

    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_model: str = "local-model"
    llm_temperature: float = 0.1
    top_k_definitions: int = 3
    bm25_top_k_chunks: int = 40
    min_quote_chars: int = 80
    max_quote_chars: int = 2000


class GraphState(BaseModel):
    """LangGraph-compatible state (mutable dict is used at runtime; this documents fields)."""

    model_config = {"extra": "allow"}

    input_paths: list[str] = Field(default_factory=list)
    dictionary_paths: list[str] = Field(default_factory=list)
    terms_file_path: str | None = None
    doc_text: str = ""
    doc_chunks: list[dict[str, Any]] = Field(default_factory=list)
    terms: list[TermCandidate] = Field(default_factory=list)
    results: list[TermWithRuMapping] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    enable_ru_law: bool = False
    ru_corpus_paths: list[str] = Field(default_factory=list)
    config: PipelineConfig = Field(default_factory=PipelineConfig)
