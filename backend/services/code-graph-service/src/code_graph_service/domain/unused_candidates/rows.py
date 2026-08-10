"""Score and shape candidate / uncertain rows."""

from __future__ import annotations

from typing import Any

from ..dead_code_scoring import (
    ScoreInput,
    StringNameCorpus,
    collect_directory_dynamic_taint,
    days_since_touch_from_symbol,
    disk_string_name_hits,
    graph_corpus_string_name_hits,
    path_has_runtime_load_risk,
    path_looks_wip,
    score_candidate,
    string_name_reference_port,
)
from ..models import GraphSymbol


def build_row(
    symbol: GraphSymbol,
    *,
    finding_kind: str,
    freshness: str,
    blockers: list[str],
    test_only: bool,
    file_has_live_importers: bool,
    weak_call_edges: bool,
    all_symbols: list[GraphSymbol],
    coverage_hits: dict[str, int] | None = None,
    repo_root: str | None = None,
    disk_search: bool = False,
    corpus: StringNameCorpus | None = None,
    tainted_parents: set[str] | None = None,
) -> dict[str, Any]:
    path = symbol.file_path or ""
    dynamic = collect_directory_dynamic_taint(
        all_symbols, path, tainted_parents=tainted_parents
    )
    path_risk = path_has_runtime_load_risk(path)
    wip_path = path_looks_wip(path)

    def _name_search(name: str, p: str) -> list[str]:
        hits = list(
            graph_corpus_string_name_hits(all_symbols, name, p, corpus=corpus)
        )
        if disk_search and repo_root:
            for hit in disk_string_name_hits(repo_root, name, p):
                if hit not in hits:
                    hits.append(hit)
        return hits

    extra = string_name_reference_port(symbol.name, path, search=_name_search)
    blockers = list(dict.fromkeys([*blockers, *extra]))
    if weak_call_edges:
        blockers = list(dict.fromkeys([*blockers, "weak_or_ambiguous_call_edge"]))
    if wip_path:
        blockers = list(dict.fromkeys([*blockers, "wip_or_recent_path"]))

    cov_count: int | None = None
    if coverage_hits is not None and symbol.id in coverage_hits:
        try:
            cov_count = int(coverage_hits[symbol.id])
        except (TypeError, ValueError):
            cov_count = None

    scored = score_candidate(
        ScoreInput(
            visibility=symbol.visibility or "public",
            blockers=blockers,
            freshness=freshness,
            finding_kind=finding_kind,
            test_only=test_only,
            file_has_live_importers=file_has_live_importers,
            weak_call_edges=weak_call_edges,
            dynamic_loader_nearby=dynamic,
            path_risk=path_risk,
            wip_path=wip_path,
            coverage_hits=cov_count,
            days_since_touch=days_since_touch_from_symbol(symbol, repo_root=repo_root),
        )
    )
    blockers = list(dict.fromkeys([*blockers, *scored.blockers]))
    reasons = [e.kind for e in scored.evidence]
    return {
        "symbol": symbol.qualified_name or symbol.name,
        "symbol_id": symbol.id,
        "path": symbol.file_path,
        "kind": symbol.kind.value if hasattr(symbol.kind, "value") else str(symbol.kind),
        "finding_kind": finding_kind,
        "score": scored.score,
        "confidence": scored.tier,
        "test_only": test_only,
        "evidence": [e.to_dict() for e in scored.evidence],
        "reasons": reasons,
        "blockers": blockers,
        "safe_to_delete": bool(scored.safe_to_delete) and not blockers,
    }


def append_row(
    row: dict[str, Any],
    *,
    min_confidence: float,
    include_uncertain: bool,
    candidates: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
) -> None:
    if float(row.get("score") or 0) < min_confidence:
        return
    if row.get("safe_to_delete"):
        candidates.append(row)
    elif include_uncertain or row.get("blockers"):
        skipped_row = {
            "symbol": row.get("symbol"),
            "symbol_id": row.get("symbol_id"),
            "path": row.get("path"),
            "kind": row.get("kind"),
            "finding_kind": row.get("finding_kind"),
            "score": row.get("score"),
            "confidence": row.get("confidence"),
            "test_only": row.get("test_only", False),
            "safe_to_delete": bool(row.get("safe_to_delete")),
            "evidence": row.get("evidence") or [],
            "blockers": row.get("blockers") or [],
        }
        if row.get("recommendation"):
            skipped_row["recommendation"] = row.get("recommendation")
        skipped.append(skipped_row)
