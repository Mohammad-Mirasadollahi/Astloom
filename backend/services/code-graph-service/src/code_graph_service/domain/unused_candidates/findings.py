"""Specialized finding kinds: unreachable file, zombie / unwired package, runtime-dead."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..dead_code_scoring import StringNameCorpus
from ..enums import RelType
from ..models import GraphEdge, GraphSymbol
from .blockers import blockers_for
from .constants import ELIGIBLE_KINDS
from .package_class import classify_shared_package
from .rows import build_row


def package_key(file_path: str) -> str:
    path = (file_path or "").replace("\\", "/")
    if "/" not in path:
        return ""
    parent = path.rsplit("/", 1)[0]
    if parent.endswith("/__init__") or parent.endswith("__init__"):
        parent = parent.rsplit("/", 1)[0] if "/" in parent else ""
    return parent


def unreachable_file_candidates(
    symbols: list[GraphSymbol],
    edges: list[GraphEdge],
    pool_ids: set[str],
    dead_ids: set[str],
    live_ids: set[str],  # noqa: ARG001 — signature parity with callers
    *,
    freshness: str,
    coverage_hits: dict[str, int] | None = None,
    repo_root: str | None = None,
    disk_search: bool = False,
    corpus: StringNameCorpus | None = None,
    tainted_parents: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Files with no inbound IMPORTS and all eligible exports unused."""
    by_id = {s.id: s for s in symbols}
    by_path: dict[str, list[GraphSymbol]] = defaultdict(list)
    for sym in symbols:
        path = (sym.file_path or "").replace("\\", "/")
        if not path:
            continue
        by_path[path].append(sym)

    imported_paths: set[str] = set()
    for edge in edges:
        if edge.rel_type != RelType.IMPORTS.value:
            continue
        tgt = by_id.get(edge.target_id)
        if tgt is None:
            continue
        imported_paths.add((tgt.file_path or "").replace("\\", "/"))

    rows: list[dict[str, Any]] = []
    for path, members in by_path.items():
        eligible = [m for m in members if m.kind in ELIGIBLE_KINDS and m.id in pool_ids]
        if not eligible:
            continue
        if path in imported_paths:
            continue
        if not all(m.id in dead_ids for m in eligible):
            continue
        rep = eligible[0]
        blockers = blockers_for(rep, inbound_any=0)
        row = build_row(
            rep,
            finding_kind="unreachable_file",
            freshness=freshness,
            blockers=blockers,
            test_only=False,
            file_has_live_importers=False,
            weak_call_edges=False,
            all_symbols=symbols,
            coverage_hits=coverage_hits,
            repo_root=repo_root,
            disk_search=disk_search,
            corpus=corpus,
            tainted_parents=tainted_parents,
        )
        row["symbol"] = path
        row["kind"] = "file"
        row["path"] = path
        rows.append(row)
    return rows


def zombie_package_candidates(
    symbols: list[GraphSymbol],
    edges: list[GraphEdge],
    pool_ids: set[str],
    dead_ids: set[str],
    *,
    freshness: str,
    corpus: StringNameCorpus | None = None,
    tainted_parents: set[str] | None = None,
    repo_root: str | None = None,
) -> list[dict[str, Any]]:
    """Packages with no inbound IMPORTS from outside and all pool exports unused.

    Shared trees under ``backend/packages/`` may be reclassified as
    ``unwired_shared_package`` with ``recommendation`` wire|keep_public.
    """
    by_id = {s.id: s for s in symbols}
    by_pkg: dict[str, list[GraphSymbol]] = defaultdict(list)
    for sym in symbols:
        if sym.kind not in ELIGIBLE_KINDS or sym.id not in pool_ids:
            continue
        pkg = package_key(sym.file_path)
        if not pkg:
            continue
        by_pkg[pkg].append(sym)

    imported_into_pkg: set[str] = set()
    for edge in edges:
        if edge.rel_type != RelType.IMPORTS.value:
            continue
        tgt = by_id.get(edge.target_id)
        if tgt is None:
            continue
        pkg = package_key(tgt.file_path)
        if not pkg:
            continue
        src = by_id.get(edge.source_id)
        src_pkg = package_key(src.file_path) if src is not None else ""
        if src_pkg != pkg:
            imported_into_pkg.add(pkg)

    rows: list[dict[str, Any]] = []
    for pkg, members in by_pkg.items():
        if pkg in imported_into_pkg:
            continue
        if not members or not all(m.id in dead_ids for m in members):
            continue
        paths = {(m.file_path or "").replace("\\", "/") for m in members}
        if len(paths) < 2:
            continue
        rep = members[0]
        classified = classify_shared_package(pkg, repo_root=repo_root)
        finding_kind = classified.finding_kind
        recommendation = classified.recommendation
        kind_blocker = (
            "unwired_shared_package"
            if finding_kind == "unwired_shared_package"
            else "zombie_package"
        )
        blockers = list(dict.fromkeys([*blockers_for(rep, inbound_any=0), kind_blocker]))
        row = build_row(
            rep,
            finding_kind=finding_kind,
            freshness=freshness,
            blockers=blockers,
            test_only=False,
            file_has_live_importers=False,
            weak_call_edges=False,
            all_symbols=symbols,
            corpus=corpus,
            tainted_parents=tainted_parents,
            repo_root=repo_root,
        )
        row["symbol"] = pkg
        row["kind"] = "package"
        row["path"] = pkg
        row["recommendation"] = recommendation
        row["safe_to_delete"] = False
        evidence = list(row.get("evidence") or [])
        evidence.append({"kind": "recommendation", "detail": recommendation})
        row["evidence"] = evidence
        rows.append(row)
    return rows


def runtime_dead_candidates(
    symbols: list[GraphSymbol],
    pool_ids: set[str],
    live_ids: set[str],
    *,
    freshness: str,
    coverage_hits: dict[str, int],
    corpus: StringNameCorpus | None = None,
    tainted_parents: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Live (reachable) symbols with zero coverage hits — never safe_to_delete."""
    by_id = {s.id: s for s in symbols}
    rows: list[dict[str, Any]] = []
    for sid in sorted(live_ids & pool_ids):
        if sid not in coverage_hits:
            continue
        try:
            hits = int(coverage_hits[sid])
        except (TypeError, ValueError):
            continue
        if hits != 0:
            continue
        symbol = by_id.get(sid)
        if symbol is None or symbol.kind not in ELIGIBLE_KINDS:
            continue
        blockers = list(
            dict.fromkeys([*blockers_for(symbol, inbound_any=1), "runtime_dead_needs_proof"])
        )
        row = build_row(
            symbol,
            finding_kind="runtime_dead",
            freshness=freshness,
            blockers=blockers,
            test_only=False,
            file_has_live_importers=True,
            weak_call_edges=False,
            all_symbols=symbols,
            coverage_hits=coverage_hits,
            corpus=corpus,
            tainted_parents=tainted_parents,
        )
        row["safe_to_delete"] = False
        rows.append(row)
    return rows
