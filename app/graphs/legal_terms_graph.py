"""LangGraph workflow: load -> extract -> normalize -> lookup -> validate -> optional RU -> export."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.adapters.blacks_pdf_index import BlacksPdfIndex
from app.config import load_pipeline_config
from app.pipelines.extract_terms import extract_terms_llm, read_terms_file
from app.pipelines.ingest import document_to_chunks, load_document, merge_chunk_lists
from app.pipelines.lookup_dictionary import lookup_all_terms
from app.pipelines.normalize_terms import enrich_term_variants
from app.pipelines.ru_law_mapper import map_results_optional
from app.pipelines.validate_output import validate_results
from app.reports.export_results import export_human_xlsx, export_json, export_xlsx
from app.schemas.term import PipelineConfig, TermCandidate, TermLookupResult, TermWithRuMapping


class AgentState(TypedDict, total=False):
    input_paths: list[str]
    dictionary_paths: list[str]
    terms_file_path: str | None
    output_dir: str
    index_cache_path: str | None
    doc_text: str
    doc_chunks: list[dict[str, Any]]
    terms: list[dict[str, Any]]
    results: list[dict[str, Any]]
    enable_ru_law: bool
    ru_corpus_paths: list[str]
    errors: list[str]


_RUNTIME: dict[str, Any] = {}


def _cfg() -> PipelineConfig:
    return _RUNTIME["cfg"]


def _get_index(state: AgentState) -> BlacksPdfIndex:
    if _RUNTIME.get("index") is not None:
        return _RUNTIME["index"]
    paths = [Path(p) for p in state.get("dictionary_paths", [])]
    cache = state.get("index_cache_path")
    if cache:
        cp = Path(cache)
        if cp.exists():
            try:
                with cp.open("rb") as f:
                    idx = pickle.load(f)
                    _RUNTIME["index"] = idx
                    return idx
            except Exception:
                pass
    idx = BlacksPdfIndex.build(paths)
    _RUNTIME["index"] = idx
    if cache:
        cp = Path(cache)
        cp.parent.mkdir(parents=True, exist_ok=True)
        with cp.open("wb") as f:
            pickle.dump(idx, f)
    return idx


def node_load_input(state: AgentState) -> dict[str, Any]:
    errs = list(state.get("errors", []))
    inputs = [Path(p) for p in state.get("input_paths", [])]
    if not inputs:
        # Terms-only mode: lookup uses --terms without textbook pages.
        if state.get("terms_file_path"):
            return {"doc_text": "", "doc_chunks": [], "errors": errs}
        errs.append("No input_paths provided for document ingestion (or pass --terms).")
        return {"errors": errs}
    texts: list[str] = []
    chunk_lists: list[list[dict[str, Any]]] = []
    for p in inputs:
        if not p.exists():
            errs.append(f"Missing input file: {p}")
            continue
        try:
            full, chunks = document_to_chunks(p)
            texts.append(full)
            chunk_lists.append(chunks)
        except Exception as e:
            errs.append(f"Failed to load {p}: {e}")
    merged = merge_chunk_lists(chunk_lists)
    doc_text = "\n\n".join(t for t in texts if t)
    return {"doc_text": doc_text, "doc_chunks": merged, "errors": errs}


def node_extract_terms(state: AgentState) -> dict[str, Any]:
    errs = list(state.get("errors", []))
    terms_path = state.get("terms_file_path")
    if terms_path:
        p = Path(terms_path)
        if not p.exists():
            errs.append(f"Terms file not found: {p}")
            return {"terms": [], "errors": errs}
        try:
            terms = read_terms_file(p)
        except Exception as e:
            errs.append(f"Failed to read terms file: {e}")
            return {"terms": [], "errors": errs}
        return {"terms": [t.model_dump() for t in terms], "errors": errs}

    doc_text = state.get("doc_text", "")
    if not doc_text.strip():
        errs.append("No document text to extract terms from.")
        return {"terms": [], "errors": errs}
    try:
        terms = extract_terms_llm(doc_text, _cfg())
    except Exception as e:
        errs.append(f"LLM extraction failed: {e}")
        return {"terms": [], "errors": errs}
    return {"terms": [t.model_dump() for t in terms], "errors": errs}


def node_normalize_terms(state: AgentState) -> dict[str, Any]:
    raw = state.get("terms", [])
    candidates = [TermCandidate.model_validate(x) for x in raw]
    enriched = enrich_term_variants(candidates)
    return {"terms": [t.model_dump() for t in enriched]}


def node_lookup_definitions(state: AgentState) -> dict[str, Any]:
    errs = list(state.get("errors", []))
    try:
        index = _get_index(state)
    except Exception as e:
        errs.append(f"Dictionary index build failed: {e}")
        return {"results": [], "errors": errs}

    terms = [TermCandidate.model_validate(x) for x in state.get("terms", [])]
    if not terms:
        return {"results": [], "errors": errs + ["No terms to lookup."]}
    try:
        looked = lookup_all_terms(terms, index, _cfg())
    except Exception as e:
        errs.append(f"Lookup failed: {e}")
        return {"results": [], "errors": errs}
    return {"results": [r.model_dump() for r in looked], "errors": errs}


def node_validate_output(state: AgentState) -> dict[str, Any]:
    raw = state.get("results", [])
    results = [TermLookupResult.model_validate(x) for x in raw]
    fixed = validate_results(results)
    return {"results": [r.model_dump() for r in fixed]}


def node_optional_ru(state: AgentState) -> dict[str, Any]:
    if not state.get("enable_ru_law"):
        raw = state.get("results", [])
        with_ru = [TermWithRuMapping(**TermLookupResult.model_validate(x).model_dump()) for x in raw]
        return {"results": [r.model_dump() for r in with_ru]}

    raw = state.get("results", [])
    base = [TermLookupResult.model_validate(x) for x in raw]
    ru_paths = state.get("ru_corpus_paths", []) or []
    mapped = map_results_optional(base, _cfg(), ru_paths)
    return {"results": [r.model_dump() for r in mapped]}


def node_export_report(state: AgentState) -> dict[str, Any]:
    out_dir = Path(state.get("output_dir", "output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = state.get("results", [])
    results = [TermWithRuMapping.model_validate(x) for x in raw]
    export_json(results, out_dir / "results.json")
    export_xlsx(results, out_dir / "results.xlsx")
    export_human_xlsx(results, out_dir / "results_human.xlsx")
    (out_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "dictionary_paths": state.get("dictionary_paths", []),
                "input_paths": state.get("input_paths", []),
                "terms_file": state.get("terms_file_path"),
                "enable_ru_law": bool(state.get("enable_ru_law")),
                "ru_corpus_paths": state.get("ru_corpus_paths", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {}


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("load_input", node_load_input)
    g.add_node("extract_terms", node_extract_terms)
    g.add_node("normalize_terms", node_normalize_terms)
    g.add_node("lookup_definitions", node_lookup_definitions)
    g.add_node("validate_output", node_validate_output)
    g.add_node("optional_ru", node_optional_ru)
    g.add_node("export_report", node_export_report)

    g.set_entry_point("load_input")
    g.add_edge("load_input", "extract_terms")
    g.add_edge("extract_terms", "normalize_terms")
    g.add_edge("normalize_terms", "lookup_definitions")
    g.add_edge("lookup_definitions", "validate_output")
    g.add_edge("validate_output", "optional_ru")
    g.add_edge("optional_ru", "export_report")
    g.add_edge("export_report", END)
    return g


def compile_app():
    return build_graph().compile()


def run_full_pipeline(
    *,
    input_paths: list[Path],
    dictionary_paths: list[Path],
    output_dir: Path,
    terms_file: Path | None = None,
    enable_ru_law: bool = False,
    ru_corpus_paths: list[Path] | None = None,
    index_cache_path: Path | None = None,
    cfg: PipelineConfig | None = None,
) -> list[TermWithRuMapping]:
    """High-level entry used by CLI."""
    _RUNTIME.clear()
    _RUNTIME["cfg"] = cfg or load_pipeline_config()
    _RUNTIME["index"] = None

    app = compile_app()
    init: AgentState = {
        "input_paths": [str(p.resolve()) for p in input_paths],
        "dictionary_paths": [str(p.resolve()) for p in dictionary_paths],
        "terms_file_path": str(terms_file.resolve()) if terms_file else None,
        "output_dir": str(output_dir.resolve()),
        "index_cache_path": str(index_cache_path.resolve()) if index_cache_path else None,
        "enable_ru_law": enable_ru_law,
        "ru_corpus_paths": [str(p.resolve()) for p in (ru_corpus_paths or [])],
        "errors": [],
    }
    final = app.invoke(init)
    return [TermWithRuMapping.model_validate(x) for x in final.get("results", [])]


def run_extract_only(
    *,
    input_paths: list[Path],
    cfg: PipelineConfig | None = None,
) -> list[TermCandidate]:
    _RUNTIME.clear()
    _RUNTIME["cfg"] = cfg or load_pipeline_config()
    state: AgentState = {"input_paths": [str(p.resolve()) for p in input_paths], "errors": []}
    state.update(node_load_input(state))
    state.update(node_extract_terms(state))
    state.update(node_normalize_terms(state))
    return [TermCandidate.model_validate(x) for x in state.get("terms", [])]


def run_lookup_only(
    *,
    terms_file: Path,
    dictionary_paths: list[Path],
    output_dir: Path,
    enable_ru_law: bool = False,
    ru_corpus_paths: list[Path] | None = None,
    index_cache_path: Path | None = None,
    cfg: PipelineConfig | None = None,
) -> list[TermWithRuMapping]:
    _RUNTIME.clear()
    _RUNTIME["cfg"] = cfg or load_pipeline_config()
    _RUNTIME["index"] = None

    state: AgentState = {
        "input_paths": [],
        "dictionary_paths": [str(p.resolve()) for p in dictionary_paths],
        "terms_file_path": str(terms_file.resolve()),
        "output_dir": str(output_dir.resolve()),
        "index_cache_path": str(index_cache_path.resolve()) if index_cache_path else None,
        "doc_text": "",
        "enable_ru_law": enable_ru_law,
        "ru_corpus_paths": [str(p.resolve()) for p in (ru_corpus_paths or [])],
        "errors": [],
    }
    state.update(node_extract_terms(state))
    state.update(node_normalize_terms(state))
    state.update(node_lookup_definitions(state))
    state.update(node_validate_output(state))
    state.update(node_optional_ru(state))
    state.update(node_export_report(state))
    raw = state.get("results", [])
    return [TermWithRuMapping.model_validate(x) for x in raw]
