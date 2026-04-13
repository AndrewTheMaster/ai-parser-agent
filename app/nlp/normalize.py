"""Tokenization, lemmatization, and search-variant expansion for English legal terms."""

from __future__ import annotations

import re
import string
from functools import lru_cache

# Common English stopwords to skip in COMPONENT matching only
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "on",
        "with",
        "by",
        "from",
        "as",
        "at",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
    }
)


def clean_text(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def tokenize(s: str) -> list[str]:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s\-]", " ", s)
    parts = [p for p in s.split() if p]
    return parts


@lru_cache(maxsize=1)
def _wn_lemmatizer():
    try:
        import nltk
        from nltk.stem import WordNetLemmatizer

        for pkg in ("wordnet", "omw-1.4"):
            try:
                nltk.data.find(f"corpora/{pkg}")
            except LookupError:
                try:
                    nltk.download(pkg, quiet=True)
                except Exception:
                    pass
        return WordNetLemmatizer()
    except Exception:
        return None


def lemmatize_word(w: str) -> str:
    w = w.lower().strip()
    if not w:
        return w
    lem = _wn_lemmatizer()
    if lem is None:
        return w
    # Try noun then verb heuristic for legal English
    out = lem.lemmatize(w, pos="n")
    if out == w:
        out = lem.lemmatize(w, pos="v")
    return out


def lemmatize_tokens(tokens: list[str]) -> list[str]:
    return [lemmatize_word(t) for t in tokens]


def normalize_phrase(phrase: str) -> str:
    toks = tokenize(phrase)
    if not toks:
        return ""
    lemmas = lemmatize_tokens(toks)
    return " ".join(lemmas)


def expand_variants(phrase: str) -> list[str]:
    """Ordered unique variants for cascade search."""
    raw = clean_text(phrase)
    if not raw:
        return []
    variants: list[str] = []
    seen: set[str] = set()

    def add(v: str) -> None:
        v = clean_text(v)
        if not v:
            return
        key = v.lower()
        if key not in seen:
            seen.add(key)
            variants.append(v)

    add(raw)
    add(raw.lower())
    # Title case for dictionary-style headwords
    add(string.capwords(raw))
    norm = normalize_phrase(raw)
    if norm:
        add(norm)
    # Acronym / parenthetical preserved as-is already in raw
    return variants


def important_tokens(phrase: str) -> list[str]:
    """Tokens used for COMPONENT search (drop stopwords, short noise)."""
    toks = tokenize(phrase)
    lemmas = lemmatize_tokens(toks)
    out: list[str] = []
    for t in lemmas:
        if t in STOPWORDS or len(t) < 3:
            continue
        out.append(t)
    return out


def best_headword_hint(chunk_text: str, max_len: int = 120) -> str:
    """Heuristic: first non-empty line of a chunk often resembles a headword line."""
    for line in chunk_text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"\s+", " ", line)
        return line[:max_len]
    return ""
