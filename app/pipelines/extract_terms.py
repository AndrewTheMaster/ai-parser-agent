"""Extract legal term candidates via LLM (LM Studio) or from a plain terms list file."""

from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.nlp.normalize import clean_text, expand_variants, normalize_phrase
from app.schemas.term import PipelineConfig, TermCandidate


SYSTEM_PROMPT = """You extract English legal/regulatory terminology from study material.
Return ONLY valid JSON: an array of strings. Each string is one term or phrase as it appears
or in dictionary-friendly form (keep acronyms). No commentary, no markdown."""


USER_TEMPLATE = """From the text below, list legal/regulatory terms and phrases worth looking up
in Black's Law Dictionary (including statutes, acts, procedures, and multi-word phrases).
Deduplicate. Cap at 200 items if huge.

TEXT:
---
{text}
---
"""


def _parse_json_terms(raw: str) -> list[str]:
    raw = raw.strip()
    # strip markdown fences if model adds them
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # try to find first [...]
        m = re.search(r"\[[\s\S]*\]", raw)
        if not m:
            return []
        data = json.loads(m.group(0))
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for x in data:
        if isinstance(x, str) and x.strip():
            out.append(clean_text(x))
    return out


def extract_terms_llm(
    doc_text: str,
    cfg: PipelineConfig,
    *,
    max_chars: int = 24000,
) -> list[TermCandidate]:
    text = doc_text
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[...truncated...]"

    llm = ChatOpenAI(
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key,
        model=cfg.llm_model,
        temperature=cfg.llm_temperature,
    )
    msg = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=USER_TEMPLATE.format(text=text)),
        ]
    )
    content = msg.content if isinstance(msg.content, str) else str(msg.content)
    terms_raw = _parse_json_terms(content)
    return [_to_candidate(t) for t in terms_raw]


def read_terms_file(path: Path) -> list[TermCandidate]:
    """Parse bullet list / one term per line."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    found: list[str] = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        s = re.sub(r"^[\-*•]\s*", "", s).strip()
        if s.startswith("##"):
            continue
        if s:
            found.append(clean_text(s))
    # dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for t in found:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return [_to_candidate(t) for t in out]


def _to_candidate(term: str) -> TermCandidate:
    t = clean_text(term)
    norm = normalize_phrase(t)
    variants = expand_variants(t)
    return TermCandidate(term_original=t, term_normalized=norm, variants=variants)
