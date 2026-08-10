"""Inventory one software root: discover, index, classify, assemble."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astloom_cli.commands.inventory.edited import classify_edited_paths
from astloom_cli.commands.inventory.graph_index import (
    demote_edited_llm,
    pending_rels_for_root,
    scan_root_symbols,
)
from astloom_cli.commands.inventory.languages import language_breakdown
from astloom_cli.commands.inventory.processing import embed_models_by_symbol, processing_context
from astloom_cli.commands.inventory.util import (
    bucket,
    file_row,
    norm_rel,
    sort_done,
    sort_remaining,
    status_bucket,
    top,
)
from astloom_cli.sync_config import resolve_sync_filters


def inventory_one_root(
    *,
    svc: Any,
    scope: Any,
    root_path: Path,
    max_files: int,
    processing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from astloom_cli.commands.inventory.discover import discover_code_and_docs

    root_path = root_path.expanduser().resolve()
    filters = resolve_sync_filters(root=root_path)
    processing = processing or processing_context(svc)
    embed_by_symbol = embed_models_by_symbol(svc, scope)
    docs_model_label = str(processing.get("docs_model_label") or "heuristic")

    discovered_code, discovered_docs = discover_code_and_docs(
        root_path,
        filters=filters,
        max_files=max_files,
    )
    code_discovered = {norm_rel(item.relative_path) for item in discovered_code}
    docs_enabled = bool(filters.get("docs_enabled")) and bool(filters.get("doc_match_globs"))
    docs_discovered = {norm_rel(item.relative_path) for item in discovered_docs} if docs_enabled else set()

    scanned = scan_root_symbols(
        symbols=list(svc.store.list_symbols(scope)),
        root_path=root_path,
        code_discovered=code_discovered,
        docs_discovered=docs_discovered,
        embed_by_symbol=embed_by_symbol,
        docs_model_label=docs_model_label,
    )
    indexed_code = scanned["indexed_code"]
    indexed_docs = scanned["indexed_docs"]
    llm_done = scanned["llm_done"]
    llm_remaining = scanned["llm_remaining"]
    file_meta = scanned["file_meta"]
    docs_hashes = scanned["docs_hashes"]
    code_stats = scanned["code_stats"]
    docs_stats = scanned["docs_stats"]

    pending_rels = pending_rels_for_root(
        svc=svc,
        scope=scope,
        root_path=root_path,
        code_discovered=code_discovered,
        docs_discovered=docs_discovered,
    )
    code_edited_map = classify_edited_paths(
        root_path=root_path,
        indexed=indexed_code,
        pending_rels=pending_rels,
        file_meta=file_meta,
    )
    docs_edited_map = {rel: "pending" for rel in sorted(indexed_docs & pending_rels)}
    if indexed_docs:
        from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter
        from code_graph_service.domain.hashing import digest

        for rel in sorted(indexed_docs - pending_rels):
            known_hashes = docs_hashes.get(rel) or set()
            if not known_hashes:
                continue
            try:
                _frontmatter, body = parse_markdown_frontmatter(
                    (root_path / rel).read_text(encoding="utf-8")
                )
            except (OSError, UnicodeDecodeError):
                docs_edited_map[rel] = "unreadable"
                continue
            if digest(body) not in known_hashes:
                docs_edited_map[rel] = "content_changed"

    code_edited = set(code_edited_map)
    docs_edited = set(docs_edited_map)
    code_done = sorted(indexed_code - code_edited)
    code_edited_list = sorted(code_edited)
    code_remaining = sorted(code_discovered - indexed_code)
    docs_done = sorted(indexed_docs - docs_edited) if docs_discovered else []
    docs_edited_list = sorted(docs_edited)
    docs_remaining = sorted(docs_discovered - indexed_docs) if docs_discovered else []

    llm_done, llm_remaining = demote_edited_llm(llm_done, llm_remaining, code_edited)

    code_done_files = _code_rows(code_done, "done", code_stats, code_edited_map)
    code_edited_files = _code_rows(code_edited_list, "edited", code_stats, code_edited_map)
    code_remaining_files = _code_rows(code_remaining, "remaining", code_stats, code_edited_map)
    docs_done_files = _docs_rows(docs_done, "done", docs_stats, docs_edited_map)
    docs_edited_files = _docs_rows(docs_edited_list, "edited", docs_stats, docs_edited_map)
    docs_remaining_files = _docs_rows(docs_remaining, "remaining", docs_stats, docs_edited_map)

    models_used = sorted(
        {
            *(m for row in code_done_files for m in row.get("models") or []),
            *(m for row in code_edited_files for m in row.get("models") or []),
            *(m for row in docs_done_files for m in row.get("models") or []),
            *(m for row in docs_edited_files for m in row.get("models") or []),
        }
    )

    code_bucket = status_bucket(code_done, code_edited_list, code_remaining)
    docs_bucket = status_bucket(docs_done, docs_edited_list, docs_remaining)
    languages = language_breakdown(
        discovered_code,
        done=code_done,
        edited=code_edited_list,
        remaining=code_remaining,
    )
    code_bytes = sum(int(getattr(item, "size_bytes", 0) or 0) for item in discovered_code)
    docs_bytes = sum(int(getattr(item, "size_bytes", 0) or 0) for item in discovered_docs)
    eligible_embeddings = sum(
        int(stats.get("embedding_eligible") or 0) for stats in code_stats.values()
    )
    indexed_embeddings = sum(
        int(stats.get("embedding_indexed") or 0) for stats in code_stats.values()
    )
    missing_embeddings = sum(
        int(stats.get("embedding_missing") or 0) for stats in code_stats.values()
    )

    return {
        "path": str(root_path),
        "filters": {
            "sources": filters.get("sources") or [],
            "docs_enabled": docs_enabled,
            "doc_match_globs": list(filters.get("doc_match_globs") or []),
        },
        "processing": processing,
        "models_used": models_used,
        "totals": {
            "code_files": len(discovered_code),
            "code_bytes": code_bytes,
            "docs_files": len(discovered_docs),
            "docs_bytes": docs_bytes,
        },
        "languages": languages,
        "code": {
            **code_bucket,
            "embeddings": {
                "eligible_symbols": eligible_embeddings,
                "indexed_symbols": indexed_embeddings,
                "missing_symbols": missing_embeddings,
                "coverage_percent": (
                    round(100.0 * indexed_embeddings / eligible_embeddings, 1)
                    if eligible_embeddings
                    else 100.0
                ),
            },
            "pending_count": len(pending_rels & code_discovered),
            "pending": sorted(pending_rels & code_discovered),
            "llm": bucket(llm_done, llm_remaining),
            "done_files": code_done_files,
            "edited_files": code_edited_files,
            "remaining_files": code_remaining_files,
            "top_done": top(code_done_files),
            "top_edited": top(code_edited_files),
            "top_remaining": top(code_remaining_files),
        },
        "docs": {
            **docs_bucket,
            "enabled": docs_enabled,
            "done_files": docs_done_files,
            "edited_files": docs_edited_files,
            "remaining_files": docs_remaining_files,
            "top_done": top(docs_done_files),
            "top_edited": top(docs_edited_files),
            "top_remaining": top(docs_remaining_files),
        },
    }


def _code_rows(
    paths: list[str],
    status: str,
    code_stats: dict[str, dict[str, Any]],
    code_edited_map: dict[str, str],
) -> list[dict[str, Any]]:
    rows = [
        file_row(
            path=rel,
            status=status,
            symbols=int(code_stats[rel]["symbols"]),
            documented=int(code_stats[rel]["documented"]),
            embedding_eligible=int(code_stats[rel]["embedding_eligible"]),
            embedding_indexed=int(code_stats[rel]["embedding_indexed"]),
            embedding_missing=int(code_stats[rel]["embedding_missing"]),
            embed_models=list(code_stats[rel]["embed_models"]),
            docs_models=list(code_stats[rel]["docs_models"]),
            category="code",
            edit_reason=code_edited_map.get(rel, ""),
        )
        for rel in paths
    ]
    return sort_done(rows) if status != "remaining" else sort_remaining(rows)


def _docs_rows(
    paths: list[str],
    status: str,
    docs_stats: dict[str, dict[str, Any]],
    docs_edited_map: dict[str, str],
) -> list[dict[str, Any]]:
    rows = [
        file_row(
            path=rel,
            status=status,
            symbols=int(docs_stats[rel]["symbols"]),
            documented=int(docs_stats[rel]["documented"]),
            embed_models=list(docs_stats[rel]["embed_models"]),
            docs_models=list(docs_stats[rel]["docs_models"]) or (["human"] if status != "remaining" else []),
            category="docs",
            edit_reason=docs_edited_map.get(rel, ""),
        )
        for rel in paths
    ]
    return sort_done(rows) if status != "remaining" else sort_remaining(rows)
