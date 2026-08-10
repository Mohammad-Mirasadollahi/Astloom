"""Directed impact, caller ranking, and escalate hints (Codebase-Memory hybrid Wave A/B).

Role: Rank callers and compute directed blast-radius over structural CALL edges.
Source of truth: CODE_REL confidence + ``min_confidence`` floor (default probable).
Allowed: filter by confidence / rel_type; escalate hints when sparse. Forbidden:
treating ambiguous/unresolved as impact-eligible under the default floor.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Iterable

from .confidence_policy import (
    DEFAULT_IMPACT_MIN_CONFIDENCE,
    confidence_rank,
    impact_eligible,
)
from .enums import CallConfidence
from .models import GraphEdge, GraphSymbol

DEFAULT_STRUCTURAL_REL_TYPES: frozenset[str] = frozenset(
    {"CALLS", "HTTP_CALLS", "ASYNC_CALLS", "ROUTES_TO"}
)

ESCALATE_NEXT = (
    "astloom_code_graph_explore",
    "astloom_code_graph_call_path",
    "astloom_code_graph_hybrid_search",
)


def meets_min_confidence(
    value: str | CallConfidence,
    minimum: str | None = DEFAULT_IMPACT_MIN_CONFIDENCE,
) -> bool:
    """True when edge confidence meets the floor (default: probable).

    Pass ``minimum=None`` only to disable the floor (include all confidences).
    """
    return impact_eligible(value, min_confidence=minimum)


def escalate_hint(*, reason: str = "ok", sparse: bool = False) -> dict[str, Any]:
    resolved = "structural_sparse" if sparse else reason
    return {
        "next_tools": list(ESCALATE_NEXT),
        "prefer_before_raw_read": True,
        "reason": resolved,
    }


def _fan_in(
    edges: Iterable[GraphEdge],
    *,
    rel_types: frozenset[str],
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for edge in edges:
        if edge.rel_type.upper() not in rel_types:
            continue
        counts[edge.target_id] += 1
    return dict(counts)


def rank_callers(
    seed_id: str,
    symbols: dict[str, GraphSymbol],
    edges: list[GraphEdge],
    *,
    top_k: int = 20,
    max_depth: int = 1,
    min_confidence: str | None = DEFAULT_IMPACT_MIN_CONFIDENCE,
    rel_types: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Rank inbound callers of seed (fan-in), optionally multi-hop upstream."""
    allowed = rel_types or frozenset({"CALLS", "HTTP_CALLS", "ASYNC_CALLS"})
    fan = _fan_in(edges, rel_types=allowed)
    depth = max(1, min(int(max_depth), 8))
    top_k = max(1, min(int(top_k), 200))

    # BFS upstream: follow edges where target is current → source is caller
    inbound: dict[str, list[GraphEdge]] = defaultdict(list)
    for edge in edges:
        if edge.rel_type.upper() not in allowed:
            continue
        if not meets_min_confidence(edge.confidence, min_confidence):
            continue
        inbound[edge.target_id].append(edge)

    best: dict[str, dict[str, Any]] = {}
    queue: deque[tuple[str, int]] = deque([(seed_id, 0)])
    seen_nodes = {seed_id}
    while queue:
        node_id, hop = queue.popleft()
        if hop >= depth:
            continue
        for edge in inbound.get(node_id, []):
            caller_id = edge.source_id
            conf = edge.confidence.value if isinstance(edge.confidence, CallConfidence) else str(edge.confidence)
            prev = best.get(caller_id)
            hop_to = hop + 1
            if prev is None or hop_to < prev["hop"] or (
                hop_to == prev["hop"] and confidence_rank(conf) > confidence_rank(prev["confidence"])
            ):
                best[caller_id] = {
                    "symbol_id": caller_id,
                    "hop": hop_to,
                    "confidence": conf,
                    "call_count": fan.get(caller_id, 0),
                    "via_rel": edge.rel_type.upper(),
                }
            if caller_id not in seen_nodes:
                seen_nodes.add(caller_id)
                queue.append((caller_id, hop_to))

    rows: list[dict[str, Any]] = []
    for caller_id, meta in best.items():
        sym = symbols.get(caller_id)
        rows.append(
            {
                **meta,
                "qualified_name": sym.qualified_name if sym else caller_id,
                "kind": sym.kind.value if sym else "unknown",
                "file_path": sym.file_path if sym else "",
                "name": sym.name if sym else caller_id,
            }
        )
    rows.sort(
        key=lambda r: (
            r["hop"],
            -int(r["call_count"]),
            -confidence_rank(r["confidence"]),
            str(r["qualified_name"]),
        )
    )
    truncated = rows[:top_k]
    sparse = len(truncated) == 0
    return {
        "seed_id": seed_id,
        "callers": truncated,
        "caller_count": len(rows),
        "returned": len(truncated),
        "max_depth": depth,
        "escalate_hint": escalate_hint(sparse=sparse),
    }


def directed_impact(
    seed_id: str,
    symbols: dict[str, GraphSymbol],
    edges: list[GraphEdge],
    *,
    direction: str = "both",
    max_depth: int = 3,
    min_confidence: str | None = DEFAULT_IMPACT_MIN_CONFIDENCE,
    rel_types: frozenset[str] | None = None,
    top_k: int = 50,
) -> dict[str, Any]:
    """Directed blast-radius over structural edges."""
    allowed = rel_types or DEFAULT_STRUCTURAL_REL_TYPES
    direction_n = (direction or "both").strip().lower()
    if direction_n not in {"upstream", "downstream", "both"}:
        direction_n = "both"
    depth = max(1, min(int(max_depth), 8))
    top_k = max(1, min(int(top_k), 500))
    fan = _fan_in(edges, rel_types=allowed)

    outbound: dict[str, list[GraphEdge]] = defaultdict(list)
    inbound: dict[str, list[GraphEdge]] = defaultdict(list)
    for edge in edges:
        if edge.rel_type.upper() not in allowed:
            continue
        if not meets_min_confidence(edge.confidence, min_confidence):
            continue
        outbound[edge.source_id].append(edge)
        inbound[edge.target_id].append(edge)

    best: dict[str, dict[str, Any]] = {}

    def _walk(start_map: dict[str, list[GraphEdge]], *, upstream: bool) -> None:
        queue: deque[tuple[str, int]] = deque([(seed_id, 0)])
        seen = {seed_id}
        while queue:
            node_id, hop = queue.popleft()
            if hop >= depth:
                continue
            for edge in start_map.get(node_id, []):
                nxt = edge.source_id if upstream else edge.target_id
                if nxt == seed_id:
                    continue
                conf = (
                    edge.confidence.value
                    if isinstance(edge.confidence, CallConfidence)
                    else str(edge.confidence)
                )
                hop_to = hop + 1
                prev = best.get(nxt)
                direction_label = "upstream" if upstream else "downstream"
                if prev is None or hop_to < prev["hop"]:
                    best[nxt] = {
                        "symbol_id": nxt,
                        "hop": hop_to,
                        "direction": direction_label,
                        "confidence": conf,
                        "fan_in": fan.get(nxt, 0),
                        "via_rel": edge.rel_type.upper(),
                    }
                elif hop_to == prev["hop"] and prev["direction"] != "both":
                    if prev["direction"] != direction_label:
                        prev["direction"] = "both"
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, hop_to))

    if direction_n in {"upstream", "both"}:
        _walk(inbound, upstream=True)
    if direction_n in {"downstream", "both"}:
        _walk(outbound, upstream=False)

    blast: list[dict[str, Any]] = []
    file_counts: dict[str, int] = defaultdict(int)
    for sid, meta in best.items():
        sym = symbols.get(sid)
        path = sym.file_path if sym else ""
        if path:
            file_counts[path] += 1
        blast.append(
            {
                **meta,
                "qualified_name": sym.qualified_name if sym else sid,
                "kind": sym.kind.value if sym else "unknown",
                "file_path": path,
                "name": sym.name if sym else sid,
            }
        )
    blast.sort(
        key=lambda r: (
            r["hop"],
            -int(r["fan_in"]),
            -confidence_rank(r["confidence"]),
            str(r["qualified_name"]),
        )
    )
    truncated = blast[:top_k]
    files = [
        {"file_path": path, "symbol_count": count}
        for path, count in sorted(file_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    sparse = len(truncated) == 0
    return {
        "seed_id": seed_id,
        "direction": direction_n,
        "max_depth": depth,
        "blast": truncated,
        "blast_count": len(blast),
        "returned": len(truncated),
        "files": files[:40],
        "escalate_hint": escalate_hint(sparse=sparse),
    }
