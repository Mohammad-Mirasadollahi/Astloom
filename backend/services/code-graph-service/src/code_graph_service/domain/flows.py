"""Execution-flow detection and criticality (Wave 1 — code-review-graph-inspired)."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Iterable

SECURITY_KEYWORDS: frozenset[str] = frozenset(
    {
        "auth",
        "password",
        "token",
        "secret",
        "crypto",
        "permission",
        "acl",
        "oauth",
        "jwt",
        "session",
        "encrypt",
        "decrypt",
        "login",
        "signup",
        "credential",
    }
)

_ENTRY_NAME = re.compile(
    r"^(main|__main__|handler|lambda_handler|lifespan|get_db|"
    r"middleware|errorHandler|"
    r"on_[a-z].*|handle_[a-z].*|"
    r"test_.*|Test[A-Z].*)$"
)

_DECORATOR_HINT = re.compile(
    r"@(?:app|router|blueprint)\.(?:get|post|put|delete|patch|route|websocket)\b|"
    r"@click\.(?:command|group)\b|"
    r"@(?:task|shared_task)\b|"
    r"@(?:Get|Post|Put|Delete|Patch|Request)Mapping\b",
    re.IGNORECASE,
)


@dataclass
class FlowNode:
    id: str
    name: str
    qualified_name: str
    file_path: str
    signature: str = ""
    body: str = ""


@dataclass
class ExecutionFlow:
    entry_id: str
    entry_name: str
    path_ids: list[str] = field(default_factory=list)
    depth: int = 0
    file_count: int = 0
    criticality: float = 0.0


def is_entry_point(
    node: FlowNode,
    *,
    inbound_call_count: int,
    is_route_handler: bool = False,
) -> bool:
    if is_route_handler:
        return True
    if inbound_call_count == 0 and node.name not in {"__init__", "__new__"}:
        # Leaf modules still qualify when named conventionally or decorated
        if _ENTRY_NAME.match(node.name):
            return True
        blob = f"{node.signature}\n{node.body[:400]}"
        if _DECORATOR_HINT.search(blob):
            return True
        if inbound_call_count == 0 and _DECORATOR_HINT.search(blob):
            return True
    if _ENTRY_NAME.match(node.name):
        return True
    blob = f"{node.signature}\n{node.body[:400]}"
    return bool(_DECORATOR_HINT.search(blob))


def detect_entry_points(
    nodes: Iterable[FlowNode],
    call_edges: Iterable[tuple[str, str]],
    *,
    route_handler_ids: set[str] | None = None,
) -> list[FlowNode]:
    """Return candidate entry nodes (no/few inbound CALLS or framework markers)."""
    inbound: dict[str, int] = defaultdict(int)
    for _src, tgt in call_edges:
        inbound[tgt] += 1
    route_handler_ids = route_handler_ids or set()
    entries: list[FlowNode] = []
    for node in nodes:
        if is_entry_point(
            node,
            inbound_call_count=inbound.get(node.id, 0),
            is_route_handler=node.id in route_handler_ids,
        ):
            entries.append(node)
    return entries


def trace_flow(
    entry: FlowNode,
    nodes_by_id: dict[str, FlowNode],
    calls_out: dict[str, list[str]],
    *,
    max_depth: int = 8,
    max_nodes: int = 40,
) -> ExecutionFlow:
    """Forward BFS along CALLS from an entry point."""
    path: list[str] = []
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(entry.id, 0)])
    max_d = 0
    while queue and len(path) < max_nodes:
        nid, depth = queue.popleft()
        if nid in visited:
            continue
        visited.add(nid)
        path.append(nid)
        max_d = max(max_d, depth)
        if depth >= max_depth:
            continue
        for tgt in calls_out.get(nid, ()):
            if tgt not in visited and tgt in nodes_by_id:
                queue.append((tgt, depth + 1))
    files = {nodes_by_id[i].file_path for i in path if i in nodes_by_id}
    flow = ExecutionFlow(
        entry_id=entry.id,
        entry_name=entry.qualified_name or entry.name,
        path_ids=path,
        depth=max_d,
        file_count=len(files),
    )
    flow.criticality = compute_criticality(flow, nodes_by_id, calls_out)
    return flow


def compute_criticality(
    flow: ExecutionFlow,
    nodes_by_id: dict[str, FlowNode],
    calls_out: dict[str, list[str]],
) -> float:
    """Weighted criticality 0..1 (code-review-graph-inspired)."""
    nodes = [nodes_by_id[i] for i in flow.path_ids if i in nodes_by_id]
    if not nodes:
        return 0.0

    file_count = len({n.file_path for n in nodes if n.file_path})
    file_spread = min((file_count - 1) / 4.0, 1.0) if file_count > 1 else 0.0

    known = set(nodes_by_id)
    external = 0
    for n in nodes:
        for tgt in calls_out.get(n.id, ()):
            if tgt not in known:
                external += 1
    external_score = min(external / 5.0, 1.0)

    security_hits = 0
    for n in nodes:
        blob = f"{n.name} {n.qualified_name}".lower()
        if any(kw in blob for kw in SECURITY_KEYWORDS):
            security_hits += 1
    security_score = min(security_hits / max(len(nodes), 1), 1.0)

    # Without TESTED_BY adjacency here, treat as unknown gap mid-point (0.5)
    # Callers can override via compute_risk_score with real test counts.
    test_gap = 0.5
    depth_score = min(flow.depth / 10.0, 1.0)

    return round(
        min(
            max(
                file_spread * 0.30
                + external_score * 0.20
                + security_score * 0.25
                + test_gap * 0.15
                + depth_score * 0.10,
                0.0,
            ),
            1.0,
        ),
        4,
    )
