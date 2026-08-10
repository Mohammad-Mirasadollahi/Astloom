"""Lucene query helpers for Neo4j fulltext indexes."""

from __future__ import annotations


def lucene_query(raw: str) -> str:
    """Build a Lucene query: OR of sanitized tokens (fuzzy optional on long tokens)."""
    specials = set('+-&|!(){}[]^"~*?:\\/')
    tokens: list[str] = []
    for part in raw.replace(".", " ").replace("/", " ").split():
        cleaned = "".join(ch for ch in part if ch not in specials).strip()
        if len(cleaned) < 2:
            continue
        if len(cleaned) >= 5:
            tokens.append(f"{cleaned}~1")
        else:
            tokens.append(cleaned)
    return " OR ".join(tokens[:24])

