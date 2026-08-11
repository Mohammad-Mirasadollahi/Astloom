"""Scan graph symbols for one software root into indexed/stats/LLM buckets."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from astloom_cli.commands.inventory.util import CODE_KINDS, DOCUMENTED, norm_rel, rel_under


def empty_file_stats() -> dict[str, Any]:
    return {
        "symbols": 0,
        "documented": 0,
        "embedding_eligible": 0,
        "embedding_indexed": 0,
        "embedding_missing": 0,
        "embed_models": set(),
        "docs_models": set(),
    }


def scan_root_symbols(
    *,
    symbols: list[Any],
    root_path: Path,
    code_discovered: set[str],
    docs_discovered: set[str],
    embed_by_symbol: dict[str, str],
    docs_model_label: str,
) -> dict[str, Any]:
    """Classify graph symbols into indexed paths, per-file stats, and LLM labels."""
    from code_graph_service.domain.enums import SymbolKind

    indexed_code: set[str] = set()
    indexed_docs: set[str] = set()
    llm_done: list[str] = []
    llm_remaining: list[str] = []
    file_meta: dict[str, dict[str, str]] = {}
    docs_hashes: dict[str, set[str]] = defaultdict(set)
    code_stats: dict[str, dict[str, Any]] = defaultdict(empty_file_stats)
    docs_stats: dict[str, dict[str, Any]] = defaultdict(empty_file_stats)

    for sym in symbols:
        kind = sym.kind.value if hasattr(sym.kind, "value") else str(sym.kind)
        rel = rel_under(root_path, str(sym.file_path or ""))
        if rel is None:
            continue
        sid = str(getattr(sym, "id", "") or "")
        embed_model = embed_by_symbol.get(sid) or ""

        if kind == SymbolKind.FILE.value and rel in code_discovered:
            indexed_code.add(rel)
            file_meta[rel] = {
                "hash": str(getattr(sym, "hash_value", "") or ""),
                "language": str(getattr(sym, "language", "") or ""),
                "updated_at": str(getattr(sym, "updated_at", "") or ""),
            }
            if embed_model:
                code_stats[rel]["embed_models"].add(embed_model)
        elif rel in code_discovered and kind != SymbolKind.DOCUMENTATION.value:
            indexed_code.add(rel)

        if kind == SymbolKind.DOCUMENTATION.value and rel in docs_discovered:
            indexed_docs.add(rel)
            hash_value = str(getattr(sym, "hash_value", "") or "")
            if len(hash_value) == 64:
                docs_hashes[rel].add(hash_value)
            docs_stats[rel]["symbols"] += 1
            docs_stats[rel]["documented"] += 1
            docs_stats[rel]["docs_models"].add("human")
            if embed_model:
                docs_stats[rel]["embed_models"].add(embed_model)

        if kind in CODE_KINDS and rel in code_discovered:
            status = sym.doc_status.value if hasattr(sym.doc_status, "value") else str(sym.doc_status or "")
            label = f"{rel}::{sym.qualified_name or sym.name}"
            code_stats[rel]["symbols"] += 1
            code_stats[rel]["embedding_eligible"] += 1
            if embed_model:
                code_stats[rel]["embedding_indexed"] += 1
                code_stats[rel]["embed_models"].add(embed_model)
            else:
                code_stats[rel]["embedding_missing"] += 1
            if status in DOCUMENTED or (sym.ai_documentation or "").strip():
                llm_done.append(label)
                code_stats[rel]["documented"] += 1
                if status == "human":
                    code_stats[rel]["docs_models"].add("human")
                else:
                    meta = getattr(sym, "metadata", None) or {}
                    if not isinstance(meta, dict):
                        meta = {}
                    origin = str(meta.get("doc_origin") or "").strip().lower()
                    if origin == "heuristic":
                        code_stats[rel]["docs_models"].add("heuristic")
                    elif origin == "llm":
                        code_stats[rel]["docs_models"].add(docs_model_label)
                    else:
                        # Legacy rows: unknown generator — do not claim the LLM model.
                        code_stats[rel]["docs_models"].add("heuristic")
            else:
                llm_remaining.append(label)

    return {
        "indexed_code": indexed_code,
        "indexed_docs": indexed_docs,
        "llm_done": llm_done,
        "llm_remaining": llm_remaining,
        "file_meta": file_meta,
        "docs_hashes": docs_hashes,
        "code_stats": code_stats,
        "docs_stats": docs_stats,
    }


def pending_rels_for_root(
    *,
    svc: Any,
    scope: Any,
    root_path: Path,
    code_discovered: set[str],
    docs_discovered: set[str],
) -> set[str]:
    freshness = svc.freshness_status(scope) if hasattr(svc, "freshness_status") else {}
    pending_raw = [str(p) for p in (freshness.get("pending_files") or []) if str(p).strip()]
    pending_rels: set[str] = set()
    for raw in pending_raw:
        rel = rel_under(root_path, raw) or norm_rel(raw)
        if rel in code_discovered or rel in docs_discovered:
            pending_rels.add(rel)
    return pending_rels


def demote_edited_llm(llm_done: list[str], llm_remaining: list[str], code_edited: set[str]) -> tuple[list[str], list[str]]:
    """Move symbols in edited files from LLM-done to LLM-remaining (stale until re-sync)."""
    if not code_edited:
        return llm_done, llm_remaining
    kept_done: list[str] = []
    for label in llm_done:
        rel = label.split("::", 1)[0]
        if rel in code_edited:
            llm_remaining.append(label)
        else:
            kept_done.append(label)
    return kept_done, llm_remaining
