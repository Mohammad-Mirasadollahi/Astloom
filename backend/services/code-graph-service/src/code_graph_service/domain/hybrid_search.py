"""Hybrid BM25 + semantic retrieval via Reciprocal Rank Fusion.

In-process Okapi BM25 (Lucene-style IDF; optional ``rank_bm25`` on large corpora).
Store adapters may also contribute Neo4j Lucene / Postgres FTS ranked lists.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Iterable


_TOKEN_RE = re.compile(r"(?u)[^\W\d][\w\u200c\u200d]{1,63}")
_SCRIPT_NORMALIZATION = str.maketrans({"ي": "ی", "ك": "ک"})


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text or "").translate(
        _SCRIPT_NORMALIZATION
    )
    return [t.lower() for t in _TOKEN_RE.findall(normalized) if len(t) >= 2]


def rrf_merge(
    *ranked_lists: list[str],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Merge ranked id lists with Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, sid in enumerate(ranked, start=1):
            if not sid:
                continue
            scores[sid] = scores.get(sid, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def lexical_rank(
    query: str,
    corpus: list[tuple[str, str]],
    *,
    top_k: int = 20,
) -> list[str]:
    """BM25 rank of corpus `(id, searchable_text)`; returns ids only."""
    return [sid for sid, _score in lexical_rank_scored(query, corpus, top_k=top_k)]


def lexical_rank_scored(
    query: str,
    corpus: list[tuple[str, str]],
    *,
    top_k: int = 20,
) -> list[tuple[str, float]]:
    """Okapi BM25 scores for in-process lexical retrieval."""
    top_k = max(1, min(int(top_k), 200))
    q_tokens = tokenize(query)
    if not q_tokens or not corpus:
        return []

    docs = [tokenize(text) for _sid, text in corpus]
    ids = [sid for sid, _text in corpus]
    scores = _bm25_scores(q_tokens, docs)
    ranked = sorted(
        ((ids[i], float(scores[i])) for i in range(len(ids)) if scores[i] > 0),
        key=lambda kv: (-kv[1], kv[0]),
    )
    return ranked[:top_k]


def _bm25_scores(query_tokens: list[str], docs: list[list[str]]) -> list[float]:
    """Okapi BM25 with Lucene-style positive IDF (stable on small corpora).

    ``rank_bm25`` is an optional accelerator for larger corpora; its classic IDF
    can be zero/negative when a term appears in ~half the docs (tiny test sets).
    """
    n = len(docs)
    if n >= 32:
        try:
            from rank_bm25 import BM25Okapi

            scores = [float(s) for s in BM25Okapi(docs).get_scores(query_tokens)]
            if any(s > 0 for s in scores):
                return scores
        except Exception:
            pass
    return _okapi_bm25(query_tokens, docs)


def _okapi_bm25(
    query_tokens: list[str],
    docs: list[list[str]],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    n = len(docs)
    if n == 0:
        return []
    df: dict[str, int] = {}
    for doc in docs:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1
    avgdl = sum(len(d) for d in docs) / float(n)
    scores = [0.0] * n
    for term in query_tokens:
        n_qi = df.get(term, 0)
        if n_qi == 0:
            continue
        idf = math.log(1.0 + (n - n_qi + 0.5) / (n_qi + 0.5))
        for i, doc in enumerate(docs):
            freq = doc.count(term)
            if freq == 0:
                continue
            dl = len(doc) or 1
            denom = freq + k1 * (1.0 - b + b * dl / (avgdl or 1.0))
            scores[i] += idf * (freq * (k1 + 1.0)) / denom
    return scores


def searchable_text(
    *,
    name: str = "",
    qualified_name: str = "",
    signature: str = "",
    file_path: str = "",
    ai_documentation: str = "",
    body: str = "",
    body_limit: int = 800,
) -> str:
    """Canonical lexical document for a symbol (shared by BM25 / FTS upserts)."""
    body_snip = (body or "")[: max(0, body_limit)]
    return " ".join(
        part
        for part in (
            name,
            qualified_name,
            signature,
            file_path.replace("/", " ").replace(".", " "),
            ai_documentation,
            body_snip,
        )
        if part
    )


def coalesce_rank_lists(
    *lists: Iterable[str] | None,
) -> list[list[str]]:
    out: list[list[str]] = []
    for lst in lists:
        if not lst:
            continue
        cleaned = [str(x) for x in lst if x]
        if cleaned:
            out.append(cleaned)
    return out
