"""MCP capability handlers for the code-knowledge graph (modular)."""

from __future__ import annotations

from ._resolve import resolve_symbol_id
from .query import (
    architecture_overview,
    call_path,
    callers,
    community,
    detect_changes,
    explore,
    freshness,
    generation_context,
    get_symbol,
    hybrid_search,
    impact,
    language_profile,
    neighbors,
    search,
    symbol_path,
    unused_candidates,
)
from .write import (
    ide_definition,
    ide_references,
    ide_rename,
    ingest_file,
    ingest_repo,
    purge_scope,
    reconcile_after_edit,
    sync_repo,
)

__all__ = [
    "architecture_overview",
    "call_path",
    "callers",
    "community",
    "detect_changes",
    "explore",
    "freshness",
    "generation_context",
    "get_symbol",
    "hybrid_search",
    "ide_definition",
    "ide_references",
    "ide_rename",
    "impact",
    "ingest_file",
    "ingest_repo",
    "language_profile",
    "neighbors",
    "purge_scope",
    "reconcile_after_edit",
    "resolve_symbol_id",
    "search",
    "symbol_path",
    "sync_repo",
    "unused_candidates",
]
