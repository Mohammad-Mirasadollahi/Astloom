"""Architecture analytics (Wave 2): hubs, bridges, gaps, surprise, shortest path."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ArchNode:
    id: str
    name: str
    qualified_name: str
    file_path: str
    kind: str
    community_id: int | None = None


def degree_hubs(
    nodes: Iterable[ArchNode],
    edges: Iterable[tuple[str, str, str]],
    *,
    top_n: int = 10,
) -> list[dict]:
    degree: Counter[str] = Counter()
    for src, tgt, _rel in edges:
        degree[src] += 1
        degree[tgt] += 1
    by_id = {n.id: n for n in nodes}
    scored = []
    for nid, deg in degree.items():
        n = by_id.get(nid)
        if n is None or n.kind in {"file", "unresolved", "external", "import", "documentation", "route"}:
            continue
        scored.append(
            {
                "symbol_id": n.id,
                "name": n.name,
                "qualified_name": n.qualified_name,
                "file_path": n.file_path,
                "kind": n.kind,
                "degree": deg,
                "community_id": n.community_id,
            }
        )
    scored.sort(key=lambda r: (-r["degree"], r["qualified_name"]))
    return scored[:top_n]


def approximate_betweenness(
    nodes: Iterable[ArchNode],
    edges: Iterable[tuple[str, str]],
    *,
    top_n: int = 10,
    sample_cap: int = 80,
) -> list[dict]:
    """Brandes betweenness on undirected graph; sample sources when large."""
    by_id = {n.id: n for n in nodes if n.kind not in {"file", "unresolved", "external", "import", "documentation"}}
    adj: dict[str, set[str]] = defaultdict(set)
    for src, tgt in edges:
        if src in by_id and tgt in by_id and src != tgt:
            adj[src].add(tgt)
            adj[tgt].add(src)
    node_list = sorted(by_id)
    if not node_list:
        return []
    # Sample sources deterministically
    step = max(1, len(node_list) // sample_cap)
    sources = node_list[::step][:sample_cap]
    cb: dict[str, float] = defaultdict(float)

    for s in sources:
        stack: list[str] = []
        pred: dict[str, list[str]] = {n: [] for n in node_list}
        sigma: dict[str, float] = dict.fromkeys(node_list, 0.0)
        dist: dict[str, int] = dict.fromkeys(node_list, -1)
        sigma[s] = 1.0
        dist[s] = 0
        queue: deque[str] = deque([s])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in adj.get(v, ()):
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta: dict[str, float] = dict.fromkeys(node_list, 0.0)
        while stack:
            w = stack.pop()
            for v in pred[w]:
                if sigma[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                cb[w] += delta[w]

    # Normalize by sample size
    norm = float(len(sources)) or 1.0
    results = []
    for nid, score in cb.items():
        n = by_id[nid]
        results.append(
            {
                "symbol_id": n.id,
                "name": n.name,
                "qualified_name": n.qualified_name,
                "file_path": n.file_path,
                "kind": n.kind,
                "betweenness": round(score / norm, 6),
                "community_id": n.community_id,
            }
        )
    results.sort(key=lambda r: (-r["betweenness"], r["qualified_name"]))
    return results[:top_n]


def knowledge_gaps(
    nodes: Iterable[ArchNode],
    edges: Iterable[tuple[str, str, str]],
    *,
    tested_targets: set[str] | None = None,
) -> dict[str, list[dict]]:
    """isolated / thin communities / untested hotspots.

    Isolation uses structural relationship types only (not CONTAINS/DOCUMENTED_BY),
    so leaf helpers that are merely contained do not flood the gap list — truly
    call-orphaned symbols (degree 0 on CALLS/IMPORTS/…) do.
    """
    tested_targets = tested_targets or set()
    structural_rels = {
        "CALLS",
        "IMPORTS",
        "INHERITS_FROM",
        "HTTP_CALLS",
        "ASYNC_CALLS",
        "ROUTES_TO",
        "TESTED_BY",
    }
    structural_degree: Counter[str] = Counter()
    degree: Counter[str] = Counter()
    for src, tgt, rel in edges:
        degree[src] += 1
        degree[tgt] += 1
        if rel in structural_rels:
            structural_degree[src] += 1
            structural_degree[tgt] += 1
    isolated = []
    for n in nodes:
        if n.kind in {"file", "unresolved", "external", "import", "documentation", "route"}:
            continue
        d = structural_degree.get(n.id, 0)
        if d == 0:
            isolated.append(
                {
                    "symbol_id": n.id,
                    "qualified_name": n.qualified_name,
                    "file_path": n.file_path,
                    "degree": d,
                }
            )

    # Thin communities
    by_comm: dict[int, list[ArchNode]] = defaultdict(list)
    for n in nodes:
        if n.community_id is not None:
            by_comm[n.community_id].append(n)
    thin = []
    for cid, members in by_comm.items():
        useful = [m for m in members if m.kind not in {"file", "unresolved", "external", "import"}]
        if 0 < len(useful) < 3:
            thin.append({"community_id": cid, "size": len(useful), "members": [m.qualified_name for m in useful]})

    hotspots = []
    for n in nodes:
        if n.kind not in {"function", "method", "class"}:
            continue
        if n.name in {"__init__", "__new__"}:
            continue
        norm_path = (n.file_path or "").replace("\\", "/")
        if norm_path.endswith("/testing.py") or "/testing/" in norm_path:
            continue
        if degree.get(n.id, 0) >= 4 and n.id not in tested_targets:
            # tested_targets = production ids covered by TESTED_BY or test CALLS
            hotspots.append(
                {
                    "symbol_id": n.id,
                    "qualified_name": n.qualified_name,
                    "file_path": n.file_path,
                    "degree": degree.get(n.id, 0),
                }
            )
    hotspots.sort(key=lambda r: (-r["degree"], r["qualified_name"]))
    return {
        "isolated_nodes": isolated[:50],
        "thin_communities": thin[:30],
        "untested_hotspots": hotspots[:30],
    }


def surprising_connections(
    nodes: Iterable[ArchNode],
    edges: Iterable[tuple[str, str, str, str]],
    *,
    top_n: int = 10,
) -> list[dict]:
    """edges: (src, tgt, rel, confidence). Prefer cross-community + inferred."""
    by_id = {n.id: n for n in nodes}
    conf_rank = {"external": 0, "unresolved": 0, "ambiguous": 1, "probable": 2, "exact": 3}
    scored = []
    for src, tgt, rel, conf in edges:
        a, b = by_id.get(src), by_id.get(tgt)
        if a is None or b is None:
            continue
        if a.kind in {"file", "documentation"} or b.kind in {"file", "documentation"}:
            continue
        score = 0
        reasons: list[str] = []
        if a.community_id is not None and b.community_id is not None and a.community_id != b.community_id:
            score += 3
            reasons.append("cross_community")
        if a.file_path and b.file_path and a.file_path.split("/")[0] != b.file_path.split("/")[0]:
            score += 2
            reasons.append("cross_top_dir")
        conf_l = (conf or "exact").lower()
        if conf_l in {"ambiguous", "probable", "unresolved", "external"}:
            score += conf_rank.get("exact", 3) - conf_rank.get(conf_l, 3)
            reasons.append(f"confidence:{conf_l}")
        if score <= 0:
            continue
        scored.append(
            {
                "source_id": src,
                "target_id": tgt,
                "source": a.qualified_name,
                "target": b.qualified_name,
                "rel_type": rel,
                "confidence": conf,
                "score": score,
                "reasons": reasons,
            }
        )
    scored.sort(key=lambda r: (-r["score"], r["source"], r["target"]))
    return scored[:top_n]


def suggested_questions(
    hubs: list[dict],
    bridges: list[dict],
    surprises: list[dict],
    *,
    limit: int = 5,
) -> list[dict]:
    qs: list[dict] = []
    for h in hubs[:2]:
        qs.append(
            {
                "question": f"What depends on hub `{h['qualified_name']}` and why is it central?",
                "why": f"High degree ({h.get('degree')})",
            }
        )
    for b in bridges[:2]:
        qs.append(
            {
                "question": f"What breaks if bridge `{b['qualified_name']}` changes?",
                "why": f"Betweenness {b.get('betweenness')}",
            }
        )
    for s in surprises[:2]:
        qs.append(
            {
                "question": f"Why does `{s['source']}` connect to `{s['target']}` ({s['rel_type']})?",
                "why": ", ".join(s.get("reasons") or []),
            }
        )
    return qs[:limit]


def shortest_path(
    start_id: str,
    end_id: str,
    edges: Iterable[tuple[str, str]],
    *,
    max_depth: int = 12,
) -> list[str]:
    """Undirected BFS shortest path of node ids (inclusive). Empty if unreachable."""
    if start_id == end_id:
        return [start_id]
    adj: dict[str, set[str]] = defaultdict(set)
    for src, tgt in edges:
        adj[src].add(tgt)
        adj[tgt].add(src)
    parent: dict[str, str | None] = {start_id: None}
    queue: deque[str] = deque([start_id])
    depth = {start_id: 0}
    while queue:
        v = queue.popleft()
        if depth[v] >= max_depth:
            continue
        for w in adj.get(v, ()):
            if w in parent:
                continue
            parent[w] = v
            depth[w] = depth[v] + 1
            if w == end_id:
                path = [end_id]
                cur = end_id
                while parent[cur] is not None:
                    cur = parent[cur]  # type: ignore[assignment]
                    path.append(cur)
                path.reverse()
                return path
            queue.append(w)
    return []
