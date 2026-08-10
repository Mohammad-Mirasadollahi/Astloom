"""Community detection (Wave 2) — free Leiden (scikit-network) or Louvain.

Prefer BSD-licensed ``scikit-network`` Leiden when installed. Otherwise run
clean-room weighted Louvain + Leiden-style connectivity refine.

GDS note: Neo4j GDS *Community* includes Leiden without an Enterprise key, but
Astloom keeps communities in-process for portability (no plugin required).
See docs/07-code-knowledge-graph/32-intentional-fallbacks-and-neo4j-plugin-licensing.md.
Never depend on GPL ``leidenalg``/``igraph``.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

EDGE_WEIGHTS: dict[str, float] = {
    "CALLS": 1.0,
    "HTTP_CALLS": 0.9,
    "ASYNC_CALLS": 0.9,
    "INHERITS_FROM": 0.8,
    "IMPLEMENTS": 0.7,
    "ROUTES_TO": 0.7,
    "IMPORTS": 0.5,
    "TESTED_BY": 0.4,
    "CONTAINS": 0.3,
    "DOCUMENTED_BY": 0.2,
}

_MAX_COMMUNITY_FRACTION = 0.25
_MIN_SPLIT_SIZE = 10
_RESOLUTION = 1.0

# Last algorithm used by detect_communities (for API transparency).
_LAST_ALGORITHM = "none"


def last_community_algorithm() -> str:
    return _LAST_ALGORITHM


def _set_algorithm(name: str) -> None:
    global _LAST_ALGORITHM
    _LAST_ALGORITHM = name


@dataclass(frozen=True)
class Community:
    id: int
    member_ids: tuple[str, ...]
    label: str
    size: int


def _weighted_undirected(
    node_ids: list[str],
    edges: list[tuple[str, str, str]],
) -> tuple[dict[str, dict[str, float]], dict[str, float], float]:
    allowed = set(node_ids)
    adj: dict[str, dict[str, float]] = {n: {} for n in node_ids}
    for src, tgt, rel in edges:
        if src not in allowed or tgt not in allowed or src == tgt:
            continue
        w = EDGE_WEIGHTS.get(rel, 0.5)
        adj[src][tgt] = adj[src].get(tgt, 0.0) + w
        adj[tgt][src] = adj[tgt].get(src, 0.0) + w
    strength = {n: sum(nbrs.values()) for n, nbrs in adj.items()}
    total = sum(strength.values())  # 2m
    return adj, strength, total


def _try_sknetwork_leiden(
    nodes: list[str],
    adj: dict[str, dict[str, float]],
    *,
    seed: int,
    labels_by_id: dict[str, str],
) -> list[Community] | None:
    """Run scikit-network Leiden; return None if package/runtime unavailable."""
    try:
        import numpy as np
        from scipy import sparse
        from sknetwork.clustering import Leiden
    except Exception:
        return None

    n = len(nodes)
    if n == 0:
        return []
    index = {node: i for i, node in enumerate(nodes)}
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for src, nbrs in adj.items():
        i = index[src]
        for tgt, w in nbrs.items():
            j = index[tgt]
            if i == j:
                continue
            rows.append(i)
            cols.append(j)
            data.append(float(w))
    if not data:
        return None
    matrix = sparse.csr_matrix((data, (rows, cols)), shape=(n, n))
    # Symmetrize for undirected modularity
    matrix = matrix.maximum(matrix.T)
    try:
        labels = Leiden(resolution=_RESOLUTION, random_state=seed, shuffle_nodes=False).fit_predict(matrix)
    except Exception:
        return None

    groups: dict[int, list[str]] = defaultdict(list)
    for node, lab in zip(nodes, labels, strict=True):
        groups[int(lab)].append(node)

    adj_list = {node: list(nbrs.items()) for node, nbrs in adj.items()}
    refined = _leiden_refine(list(groups.values()), adj_list, {n: sum(d.values()) for n, d in adj.items()}, float(np.sum(data)))
    refined_map = _split_oversized({i: g for i, g in enumerate(refined)}, adj_list)
    ranked = sorted(
        refined_map.values(),
        key=lambda members: (-len(members), members[0] if members else ""),
    )
    result: list[Community] = []
    for cid, members in enumerate(ranked):
        members_sorted = tuple(sorted(members))
        result.append(
            Community(
                id=cid,
                member_ids=members_sorted,
                label=_community_label(members_sorted, labels_by_id),
                size=len(members_sorted),
            )
        )
    _set_algorithm("scikit_network_leiden")
    return result


class _Lcg:
    """Tiny deterministic PRNG (no import of random)."""

    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = seed % (2**31)

    def __call__(self) -> float:
        self.state = (1103515245 * self.state + 12345) % (2**31)
        return self.state / float(2**31)


def detect_communities(
    node_ids: list[str],
    edges: list[tuple[str, str, str]],
    *,
    seed: int = 42,
    max_levels: int = 8,
    max_passes: int = 12,
    labels_by_id: dict[str, str] | None = None,
) -> list[Community]:
    """Community detection: prefer free scikit-network Leiden, else Louvain.

    Never uses Neo4j GDS (commercial). GPL leidenalg/igraph are not used.
    """
    if not node_ids:
        return []
    labels_by_id = labels_by_id or {}
    nodes = sorted(set(node_ids))
    adj, strength, total_weight = _weighted_undirected(nodes, edges)

    if total_weight <= 0:
        _set_algorithm("isolated_nodes")
        return [
            Community(id=i, member_ids=(n,), label=_community_label((n,), labels_by_id), size=1)
            for i, n in enumerate(nodes)
        ]

    skn = _try_sknetwork_leiden(nodes, adj, seed=seed, labels_by_id=labels_by_id)
    if skn is not None:
        return skn

    # expand[level_node] -> original member ids
    expand: dict[str, list[str]] = {n: [n] for n in nodes}
    level_nodes = list(nodes)
    level_adj = adj
    level_strength = strength
    level_total = total_weight
    rng = _Lcg(seed)

    for level in range(max_levels):
        partition = _local_move(
            level_nodes,
            level_adj,
            level_strength,
            level_total,
            seed=seed,
            level=level,
            max_passes=max_passes,
            rng=rng,
        )
        # partition: community_label -> members (level node ids)
        if len(partition) == len(level_nodes):
            # No merges at this level — done (use current expand)
            break

        new_expand: dict[str, list[str]] = {}
        new_adj: dict[str, dict[str, float]] = {}
        # Stable community keys
        keys: list[str] = []
        member_of: dict[str, str] = {}
        for members in sorted(partition.values(), key=lambda ms: (len(ms), sorted(ms)[0])):
            key = "|".join(sorted(members))
            keys.append(key)
            flat: list[str] = []
            for m in members:
                flat.extend(expand[m])
                member_of[m] = key
            new_expand[key] = sorted(set(flat))
            new_adj[key] = {}

        for a, nbrs in level_adj.items():
            ca = member_of[a]
            for b, w in nbrs.items():
                if a >= b:
                    continue
                cb = member_of[b]
                if ca == cb:
                    continue
                new_adj[ca][cb] = new_adj[ca].get(cb, 0.0) + w
                new_adj[cb][ca] = new_adj[cb].get(ca, 0.0) + w

        new_strength = {n: sum(nbrs.values()) for n, nbrs in new_adj.items()}
        new_total = sum(new_strength.values())
        expand = new_expand
        if new_total <= 0 or len(keys) <= 1:
            break
        level_nodes = keys
        level_adj = new_adj
        level_strength = new_strength
        level_total = new_total

    final_groups = [list(members) for members in expand.values()]

    adj_list = {n: list(nbrs.items()) for n, nbrs in adj.items()}
    refined = _leiden_refine(final_groups, adj_list, strength, total_weight)
    refined_map = _split_oversized({i: g for i, g in enumerate(refined)}, adj_list)

    ranked = sorted(
        refined_map.values(),
        key=lambda members: (-len(members), members[0] if members else ""),
    )
    result: list[Community] = []
    for cid, members in enumerate(ranked):
        members_sorted = tuple(sorted(members))
        label = _community_label(members_sorted, labels_by_id)
        result.append(
            Community(id=cid, member_ids=members_sorted, label=label, size=len(members_sorted))
        )
    _set_algorithm("louvain_leiden_refine")
    return result


def _local_move(
    nodes: list[str],
    adj: dict[str, dict[str, float]],
    strength: dict[str, float],
    total_weight: float,
    *,
    seed: int,
    level: int,
    max_passes: int,
    rng: _Lcg,
) -> dict[str, list[str]]:
    """Louvain phase-1: move nodes to neighbor communities maximizing ΔQ."""
    comm = {n: n for n in nodes}
    improved = True
    passes = 0
    while improved and passes < max_passes:
        improved = False
        passes += 1
        sigma_tot: dict[str, float] = defaultdict(float)
        for n, c in comm.items():
            sigma_tot[c] += strength.get(n, 0.0)

        order = sorted(
            nodes,
            key=lambda n: (hash((n, seed, level, passes)) ^ int(rng() * 1e9)) % 10_000_007,
        )
        for node in order:
            ki = strength.get(node, 0.0)
            if ki <= 0:
                continue
            node_comm = comm[node]
            to_comm: dict[str, float] = defaultdict(float)
            for nbr, w in adj.get(node, {}).items():
                to_comm[comm[nbr]] += w

            best_comm = node_comm
            best_gain = 0.0
            for cand in sorted(set(to_comm) | {node_comm}):
                if cand == node_comm:
                    continue
                ki_in = to_comm.get(cand, 0.0)
                sigma = sigma_tot[cand]
                # ΔQ ∝ ki_in - γ * ki * Σtot / (2m); total_weight == 2m
                gain = ki_in - (_RESOLUTION * ki * sigma / total_weight)
                rng()  # advance for seed sensitivity without non-determinism across runs
                if gain > best_gain + 1e-12 or (
                    abs(gain - best_gain) <= 1e-12 and cand < best_comm
                ):
                    best_gain = gain
                    best_comm = cand

            if best_comm != node_comm and best_gain > 1e-12:
                sigma_tot[node_comm] -= ki
                sigma_tot[best_comm] += ki
                if sigma_tot[node_comm] <= 1e-15:
                    del sigma_tot[node_comm]
                comm[node] = best_comm
                improved = True

    groups: dict[str, list[str]] = defaultdict(list)
    for n, c in comm.items():
        groups[c].append(n)
    return dict(groups)


def _leiden_refine(
    groups: list[list[str]],
    adj: dict[str, list[tuple[str, float]]],
    strength: dict[str, float],
    total_weight: float,
) -> list[list[str]]:
    """Ensure connectivity; reattach tiny fragments to best neighbor community."""
    connected: list[list[str]] = []
    for members in groups:
        connected.extend(_components(members, adj))

    large = [g for g in connected if len(g) >= 3]
    small = [g for g in connected if len(g) < 3]
    if not large:
        return connected

    assignment: dict[str, int] = {}
    for i, g in enumerate(large):
        for n in g:
            assignment[n] = i

    for frag in sorted(small, key=lambda g: (len(g), g[0] if g else "")):
        scores: dict[int, float] = defaultdict(float)
        frag_k = sum(strength.get(n, 0.0) for n in frag)
        for n in frag:
            for other, w in adj.get(n, ()):
                cid = assignment.get(other)
                if cid is not None:
                    scores[cid] += w
        if not scores:
            large.append(list(frag))
            idx = len(large) - 1
            for n in frag:
                assignment[n] = idx
            continue
        best = max(
            scores.items(),
            key=lambda kv: (
                kv[1]
                - (
                    _RESOLUTION
                    * frag_k
                    * sum(strength.get(x, 0.0) for x in large[kv[0]])
                    / max(total_weight, 1e-9)
                ),
                -kv[0],
            ),
        )[0]
        large[best].extend(frag)
        for n in frag:
            assignment[n] = best

    return [sorted(set(g)) for g in large]


def _split_oversized(
    groups: dict[int, list[str]],
    adj: dict[str, list[tuple[str, float]]],
) -> dict[int, list[str]]:
    total = sum(len(v) for v in groups.values()) or 1
    out: dict[int, list[str]] = {}
    next_id = 0
    for members in groups.values():
        if len(members) > max(_MIN_SPLIT_SIZE, int(total * _MAX_COMMUNITY_FRACTION)):
            for component in _components(members, adj):
                out[next_id] = component
                next_id += 1
        else:
            out[next_id] = members
            next_id += 1
    return out


def _components(members: list[str], adj: dict[str, list[tuple[str, float]]]) -> list[list[str]]:
    allowed = set(members)
    seen: set[str] = set()
    comps: list[list[str]] = []
    for start in sorted(members):
        if start in seen:
            continue
        stack = [start]
        comp: list[str] = []
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            comp.append(n)
            for other, _w in adj.get(n, ()):
                if other in allowed and other not in seen:
                    stack.append(other)
        comps.append(sorted(comp))
    return comps


def _community_label(members: tuple[str, ...], labels_by_id: dict[str, str]) -> str:
    names = [labels_by_id.get(m, m.split(":")[-1]) for m in members]
    tokens: list[str] = []
    for name in names:
        for part in name.replace("/", ".").replace("-", "_").split("."):
            if len(part) >= 3 and part.isidentifier():
                tokens.append(part.lower())
    if not tokens:
        return f"community-{len(members)}"
    top = Counter(tokens).most_common(1)[0][0]
    return f"{top}-cluster"
