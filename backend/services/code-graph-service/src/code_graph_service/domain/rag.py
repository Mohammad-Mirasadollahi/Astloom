"""Hybrid RAG constants for code-graph retrieval (pgvector Stage-1 + optional ANN Stage-2).

Stage-1: kind-filtered pgvector (or in-store cosine) candidate narrowing.
Stage-2: optional VectorIndexPort allowlist dense search; fall back to Stage-1 scores.
"""

from __future__ import annotations

from .enums import SymbolKind

# Indexed and returned by semantic_search (SQL filter before ANN when using pgvector).
SEARCHABLE_SYMBOL_KINDS: frozenset[str] = frozenset(
    {
        SymbolKind.CLASS.value,
        SymbolKind.FUNCTION.value,
        SymbolKind.METHOD.value,
        SymbolKind.DOCUMENTATION.value,
    }
)

# Default hybrid expand: top-N vector seeds get neighborhood attached.
DEFAULT_EXPAND_SEEDS = 3
DEFAULT_EXPAND_DEPTH = 1
DEFAULT_EXPAND_EDGE_LIMIT = 8
