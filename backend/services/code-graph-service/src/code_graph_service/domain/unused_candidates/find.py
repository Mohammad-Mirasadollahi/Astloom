"""
Role: Orchestrate graph-backed unused / unreachable / dead-subgraph candidates.
Source of truth: docs/07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md —
scores only decrease; Astloom never mutates the repository.
Allowed: task-scoped and opt-in project_scan (+ path_prefix report filter); evidence rows.
Forbidden: deleting files; inventing safe_to_delete; Memory as candidate SoT.
"""

from __future__ import annotations

from typing import Any

from ..dead_code_scoring import (
    StringNameCorpus,
    directories_with_dynamic_loaders,
    flag_controlled_dead_port,
)
from ..models import GraphEdge, GraphSymbol
from .blockers import blockers_for
from .constants import ELIGIBLE_KINDS, SCOPE_MODES
from .findings import (
    runtime_dead_candidates,
    unreachable_file_candidates,
    zombie_package_candidates,
)
from .liveness import (
    any_inbound_counts,
    live_ids_in_pool,
    paths_with_live_importers,
    strong_inbound_sources,
    test_only_for_symbol,
    test_only_ids_from_tested_by,
    weak_inbound_targets,
)
from .rows import append_row, build_row
from .scope import neighbor_ids, normalize_path_prefix, path_matches_prefix, resolve_anchors


def find_unused_candidates(
    symbols: list[GraphSymbol],
    edges: list[GraphEdge],
    *,
    scope_mode: str,
    anchor_symbols: list[str] | None = None,
    anchor_paths: list[str] | None = None,
    max_results: int = 50,
    include_uncertain: bool = False,
    freshness: str = "ok",
    min_confidence: float | None = None,
    coverage_hits: dict[str, int] | None = None,
    flag_states: dict[str, Any] | None = None,
    repo_root: str | None = None,
    disk_search: bool = False,
    path_prefix: str | None = None,
) -> dict[str, Any]:
    """Return unused-candidate payload for MCP / service callers."""
    mode = (scope_mode or "").strip()
    if mode not in SCOPE_MODES:
        raise ValueError(
            "scope_mode must be one of: task_neighborhood, changed_symbols, "
            "explicit_paths, project_scan"
        )
    max_results = max(1, min(int(max_results or 50), 200))
    if min_confidence is None:
        min_confidence = 0.50 if mode == "project_scan" else 0.0
    else:
        try:
            min_confidence = float(min_confidence)
        except (TypeError, ValueError):
            min_confidence = 0.50 if mode == "project_scan" else 0.0
    min_confidence = max(0.0, min(1.0, min_confidence))
    prefix = normalize_path_prefix(path_prefix)
    by_id = {s.id: s for s in symbols}
    all_ids = set(by_id)
    anchors = resolve_anchors(symbols, anchor_symbols=anchor_symbols, anchor_paths=anchor_paths)

    if mode == "project_scan":
        pool_ids = {s.id for s in symbols if s.kind in ELIGIBLE_KINDS}
    elif mode == "explicit_paths":
        pool_ids = anchors if anchors else set()
    elif mode == "changed_symbols":
        pool_ids = anchors if anchors else set()
    else:
        pool_ids = neighbor_ids(edges, anchors, max_hops=1) if anchors else set()

    if mode != "project_scan" and not pool_ids:
        empty: dict[str, Any] = {
            "freshness": freshness,
            "scope_mode": mode,
            "candidates": [],
            "skipped_uncertain": [],
            "kpi_hints": {
                "dead_code_candidates_surfaced": 0,
                "dead_code_candidates_skipped_uncertain": 0,
                "dead_code_candidates_resolved": 0,
            },
            "note": "no_anchor_symbols_or_paths",
        }
        if prefix:
            empty["path_prefix"] = prefix
        return empty

    pool_ids = {sid for sid in pool_ids if (sym := by_id.get(sid)) and sym.kind in ELIGIBLE_KINDS}
    if prefix:
        pool_ids = {
            sid
            for sid in pool_ids
            if (sym := by_id.get(sid)) is not None
            and path_matches_prefix(sym.file_path, prefix)
        }

    live_ids = live_ids_in_pool(pool_ids, by_id, edges, all_ids=all_ids)
    dead_ids = pool_ids - live_ids
    strong_sources = strong_inbound_sources(edges)
    weak_targets = weak_inbound_targets(edges)
    any_inbound = any_inbound_counts(edges)

    subgraph_members: set[str] = set()
    for sid in dead_ids:
        sources = strong_sources.get(sid, set())
        if sources and sources <= dead_ids:
            subgraph_members.add(sid)

    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    corpus = StringNameCorpus.from_symbols(symbols)
    tainted_parents = directories_with_dynamic_loaders(symbols)
    importer_live_ids = live_ids | (all_ids - pool_ids)
    live_importer_paths = paths_with_live_importers(symbols, edges, importer_live_ids)
    tested_by_test_ids = test_only_ids_from_tested_by(edges, by_id)

    for sid in sorted(dead_ids):
        symbol = by_id.get(sid)
        if symbol is None:
            continue
        in_count = any_inbound.get(sid, 0)
        blockers = blockers_for(symbol, inbound_any=in_count)
        if freshness in {"stale", "pending_sync"}:
            blockers = list(dict.fromkeys([*blockers, f"freshness_{freshness}"]))
        test_only = test_only_for_symbol(
            sid,
            by_id,
            strong_sources,
            tested_by_test_ids=tested_by_test_ids,
        )
        if test_only:
            finding_kind = "unused_symbol"
        elif sid in subgraph_members:
            finding_kind = "dead_subgraph"
        else:
            finding_kind = "unused_symbol"
        file_live = (symbol.file_path or "").replace("\\", "/") in live_importer_paths
        row = build_row(
            symbol,
            finding_kind=finding_kind,
            freshness=freshness,
            blockers=blockers,
            test_only=test_only,
            file_has_live_importers=file_live,
            weak_call_edges=sid in weak_targets,
            all_symbols=symbols,
            coverage_hits=coverage_hits,
            repo_root=repo_root,
            disk_search=disk_search,
            corpus=corpus,
            tainted_parents=tainted_parents,
        )
        append_row(
            row,
            min_confidence=min_confidence,
            include_uncertain=include_uncertain,
            candidates=candidates,
            skipped=skipped,
        )

    for row in unreachable_file_candidates(
        symbols,
        edges,
        pool_ids,
        dead_ids,
        live_ids,
        freshness=freshness,
        coverage_hits=coverage_hits,
        repo_root=repo_root,
        disk_search=disk_search,
        corpus=corpus,
        tainted_parents=tainted_parents,
    ):
        append_row(
            row,
            min_confidence=min_confidence,
            include_uncertain=include_uncertain,
            candidates=candidates,
            skipped=skipped,
        )

    for row in zombie_package_candidates(
        symbols,
        edges,
        pool_ids,
        dead_ids,
        freshness=freshness,
        corpus=corpus,
        tainted_parents=tainted_parents,
        repo_root=repo_root,
    ):
        append_row(
            row,
            min_confidence=min_confidence,
            include_uncertain=include_uncertain,
            candidates=candidates,
            skipped=skipped,
        )

    if coverage_hits:
        for row in runtime_dead_candidates(
            symbols,
            pool_ids,
            live_ids,
            freshness=freshness,
            coverage_hits=coverage_hits,
            corpus=corpus,
            tainted_parents=tainted_parents,
        ):
            append_row(
                row,
                min_confidence=min_confidence,
                include_uncertain=include_uncertain,
                candidates=candidates,
                skipped=skipped,
            )

    for flag_row in flag_controlled_dead_port(flag_states=flag_states):
        if float(flag_row.get("score") or 0) < min_confidence:
            continue
        skipped.append(
            {
                "symbol": flag_row.get("symbol"),
                "symbol_id": flag_row.get("symbol_id"),
                "path": flag_row.get("path"),
                "finding_kind": flag_row.get("finding_kind"),
                "score": flag_row.get("score"),
                "confidence": flag_row.get("confidence"),
                "test_only": False,
                "safe_to_delete": False,
                "evidence": flag_row.get("evidence") or [],
                "blockers": flag_row.get("blockers") or [],
                "flag_key": flag_row.get("flag_key"),
            }
        )

    candidates.sort(key=lambda r: (-float(r.get("score") or 0), str(r.get("symbol") or "")))
    skipped.sort(key=lambda r: (-float(r.get("score") or 0), str(r.get("symbol") or "")))

    def _take_with_structure_priority(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        """Keep package/file findings visible when symbol noise fills max_results."""
        if limit <= 0 or len(rows) <= limit:
            return rows[:limit]
        kind_priority = {
            "unwired_shared_package": 0,
            "zombie_package": 0,
            "unreachable_file": 1,
        }
        structural = [r for r in rows if r.get("finding_kind") in kind_priority]
        others = [r for r in rows if r.get("finding_kind") not in kind_priority]
        structural.sort(
            key=lambda r: (
                kind_priority.get(str(r.get("finding_kind") or ""), 9),
                -float(r.get("score") or 0),
                str(r.get("symbol") or ""),
            )
        )
        picked = structural[:limit]
        if len(picked) < limit:
            picked.extend(others[: limit - len(picked)])
        return picked

    surfaced = _take_with_structure_priority(candidates, max_results)
    uncertain = _take_with_structure_priority(skipped, max_results)
    out: dict[str, Any] = {
        "freshness": freshness,
        "scope_mode": mode,
        "candidates": surfaced,
        "skipped_uncertain": uncertain,
        "kpi_hints": {
            "dead_code_candidates_surfaced": len(surfaced),
            "dead_code_candidates_skipped_uncertain": len(uncertain),
            "dead_code_candidates_resolved": 0,
        },
    }
    if prefix:
        out["path_prefix"] = prefix
    return out
