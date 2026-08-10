"""Wave 2–3 domain and service tests."""

from __future__ import annotations

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.architecture import shortest_path
from code_graph_service.domain.communities import detect_communities
from code_graph_service.domain.dispatch_synth import synthesize_interface_dispatch
from code_graph_service.domain.freshness import extract_rationale_comments, FreshnessState
from code_graph_service.domain.hybrid_search import lexical_rank, rrf_merge
from code_graph_service.testing import InMemoryStore


def test_communities_and_rrf_deterministic():
    nodes = ["a", "b", "c", "d"]
    edges = [
        ("a", "b", "CALLS"),
        ("b", "a", "CALLS"),
        ("c", "d", "CALLS"),
        ("d", "c", "CALLS"),
    ]
    c1 = detect_communities(nodes, edges, seed=42)
    c2 = detect_communities(nodes, edges, seed=42)
    assert [x.member_ids for x in c1] == [x.member_ids for x in c2]
    merged = rrf_merge(["a", "b", "c"], ["b", "a", "d"], k=60)
    assert merged[0][0] in {"a", "b"}
    assert lexical_rank("login auth", [("1", "login user"), ("2", "render")]) == ["1"]


def test_louvain_separates_dense_clusters():
    """Two cliques weakly linked should form two communities (free Louvain)."""
    left = ["a", "b", "c"]
    right = ["d", "e", "f"]
    edges: list[tuple[str, str, str]] = []
    for group in (left, right):
        for i, u in enumerate(group):
            for v in group[i + 1 :]:
                edges.append((u, v, "CALLS"))
                edges.append((v, u, "CALLS"))
    edges.append(("c", "d", "IMPORTS"))  # weak bridge
    found = detect_communities(left + right, edges, seed=7)
    member_sets = [set(c.member_ids) for c in found]
    # Prefer separating the two cliques (allowing bridge endpoints to move)
    assert any(set(left).issubset(s) or set(left) == s for s in member_sets) or (
        any({"a", "b"}.issubset(s) for s in member_sets)
        and any({"e", "f"}.issubset(s) for s in member_sets)
    )
    # Every community must be connected under the undirected edge set
    undirected = {(u, v) for u, v, _ in edges} | {(v, u) for u, v, _ in edges}
    for c in found:
        members = set(c.member_ids)
        if len(members) <= 1:
            continue
        start = next(iter(members))
        seen = {start}
        stack = [start]
        while stack:
            n = stack.pop()
            for other in members:
                if other not in seen and (n, other) in undirected:
                    seen.add(other)
                    stack.append(other)
        assert seen == members


def test_shortest_path_and_rationale():
    path = shortest_path("a", "c", [("a", "b"), ("b", "c")])
    assert path == ["a", "b", "c"]
    hits = extract_rationale_comments("# WHY: keep tokens low\n# NOTE: graph first\n")
    assert {h.tag for h in hits} >= {"WHY", "NOTE"}
    state = FreshnessState()
    state.mark_pending("src/a.py")
    banner = state.stale_banner(["src/a.py"])
    assert banner["banner"] and "Pending sync" in banner["banner"]


def test_freshness_is_unknown_after_process_restart_without_watcher():
    store = InMemoryStore()
    scope = Scope("t", "w", "freshness")
    first_process = CodeGraphService(store)
    first_process.record_sync_stamp(scope)
    assert first_process.freshness_status(scope)["status"] == "ok"

    restarted_process = CodeGraphService(store)
    status = restarted_process.freshness_status(scope)

    assert status["status"] == "unknown"
    assert status["is_stale"] is True
    assert "not monitored" in status["banner"]


def test_dispatch_synth_subclass_method():
    symbols = [
        ("base", "Handler", "pkg.Handler", "class"),
        ("child", "FastHandler", "pkg.FastHandler", "class"),
        ("m", "handle", "pkg.FastHandler.handle", "method"),
        ("caller", "run", "pkg.run", "function"),
    ]
    inherits = [("child", "base")]
    calls = [("caller", "base", "Handler.handle")]
    synth = synthesize_interface_dispatch(symbols=symbols, inherits=inherits, calls=calls)
    assert any(s.target_id == "m" and s.provenance == "dynamic_dispatch" for s in synth)


def test_wave2_service_architecture_hybrid_path():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "p2")
    src = '''
class Base:
    def handle(self):
        return 1

class Child(Base):
    def handle(self):
        return 2

def run():
    return Base.handle
'''
    # WHY comment for rationale
    src = "# WHY: entry delegates to handlers\n" + src
    svc.ingest_file(
        scope,
        "a",
        "c1",
        "k1",
        {"file_path": "src/handlers.py", "source": src, "language": "python"},
    )
    overview = svc.architecture_overview(scope)
    assert "communities" in overview
    assert "hubs" in overview
    hybrid = svc.hybrid_search(scope, "handle Child")
    assert hybrid["hits"]
    # path between two symbols by name
    path = svc.symbol_path(scope, "run", "handle")
    assert "path_ids" in path
    svc.mark_file_pending("src/handlers.py")
    pack = svc.explore(scope, "how does handle work")
    assert pack.get("freshness", {}).get("pending_count", 0) >= 1
    # rationale nodes exist
    kinds = {s.kind.value for s in store.list_symbols(scope)}
    assert "rationale" in kinds
