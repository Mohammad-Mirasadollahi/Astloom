"""Scope anchors, neighborhood hops, and path_prefix helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from ..models import GraphEdge, GraphSymbol


def neighbor_ids(
    edges: Iterable[GraphEdge],
    seeds: set[str],
    *,
    max_hops: int = 1,
) -> set[str]:
    if not seeds:
        return set()
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.source_id].add(edge.target_id)
        adjacency[edge.target_id].add(edge.source_id)
    frontier = set(seeds)
    seen = set(seeds)
    for _ in range(max(1, max_hops)):
        nxt: set[str] = set()
        for node in frontier:
            for other in adjacency.get(node, ()):
                if other not in seen:
                    seen.add(other)
                    nxt.add(other)
        frontier = nxt
        if not frontier:
            break
    return seen


def resolve_anchors(
    symbols: list[GraphSymbol],
    *,
    anchor_symbols: list[str] | None,
    anchor_paths: list[str] | None,
) -> set[str]:
    wanted_names = {s.strip() for s in (anchor_symbols or []) if str(s).strip()}
    wanted_paths = {
        p.strip().replace("\\", "/") for p in (anchor_paths or []) if str(p).strip()
    }
    if not wanted_names and not wanted_paths:
        return set()
    ids: set[str] = set()
    for sym in symbols:
        qn = sym.qualified_name or ""
        path = (sym.file_path or "").replace("\\", "/")
        if sym.id in wanted_names or qn in wanted_names or sym.name in wanted_names:
            ids.add(sym.id)
            continue
        if any(
            path == wp or path.startswith(wp.rstrip("/") + "/") or path.endswith("/" + wp)
            for wp in wanted_paths
        ):
            ids.add(sym.id)
            continue
        if any(wp and wp in path for wp in wanted_paths):
            ids.add(sym.id)
    return ids


def normalize_path_prefix(path_prefix: str | None) -> str | None:
    raw = (path_prefix or "").strip().replace("\\", "/")
    if not raw:
        return None
    return raw.rstrip("/")


def path_matches_prefix(file_path: str, prefix: str) -> bool:
    path = (file_path or "").replace("\\", "/")
    return path == prefix or path.startswith(prefix + "/")
