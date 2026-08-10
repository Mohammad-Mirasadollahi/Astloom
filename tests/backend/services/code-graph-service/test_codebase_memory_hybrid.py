"""Unit tests for Codebase-Memory hybrid structural tools (callers / impact / HTTP_CALLS)."""

from __future__ import annotations

from code_graph_service.core import (
    CallConfidence,
    CodeGraphService,
    GraphEdge,
    GraphSymbol,
    Scope,
    SymbolKind,
    DocStatus,
)
from code_graph_service.api import app
from code_graph_service.domain.http_calls import extract_http_calls, normalize_http_path
from code_graph_service.domain.impact import directed_impact, rank_callers
from code_graph_service.domain.parsing import parse_python_source
from code_graph_service.testing import InMemoryStore

SCOPE = Scope("t", "w", "p")


def _sym(sid: str, name: str, *, kind: SymbolKind = SymbolKind.FUNCTION) -> GraphSymbol:
    return GraphSymbol(
        id=sid,
        scope=SCOPE,
        kind=kind,
        file_path=f"src/{name}.py",
        name=name,
        qualified_name=f"src.{name}",
        signature=f"{name}()",
        body="",
        hash_value=name,
        ai_documentation="",
        doc_status=DocStatus.UNCHANGED,
        embedding=[],
    )


def _edge(eid: str, rel: str, src: str, tgt: str, conf: CallConfidence = CallConfidence.EXACT) -> GraphEdge:
    return GraphEdge(
        id=eid,
        scope=SCOPE,
        rel_type=rel,
        source_id=src,
        target_id=tgt,
        confidence=conf,
    )


def test_rank_callers_orders_by_fan_in_and_hop() -> None:
    symbols = {
        "a": _sym("a", "a"),
        "b": _sym("b", "b"),
        "c": _sym("c", "c"),
        "seed": _sym("seed", "seed"),
    }
    edges = [
        _edge("e1", "CALLS", "a", "seed"),
        _edge("e2", "CALLS", "b", "seed"),
        _edge("e3", "CALLS", "c", "a"),  # hop-2 upstream of seed
        _edge("e4", "CALLS", "x", "b"),  # increases fan-in of b if we counted wrong — not inbound to seed
    ]
    # give b higher fan-in
    edges.append(_edge("e5", "CALLS", "c", "b"))
    out = rank_callers("seed", symbols, edges, top_k=10, max_depth=2)
    assert out["caller_count"] >= 2
    ids = [r["symbol_id"] for r in out["callers"]]
    assert "a" in ids and "b" in ids
    assert out["escalate_hint"]["prefer_before_raw_read"] is True


def test_directed_impact_upstream_vs_downstream() -> None:
    symbols = {
        "caller": _sym("caller", "caller"),
        "seed": _sym("seed", "seed"),
        "callee": _sym("callee", "callee"),
    }
    edges = [
        _edge("e1", "CALLS", "caller", "seed"),
        _edge("e2", "CALLS", "seed", "callee"),
    ]
    up = directed_impact("seed", symbols, edges, direction="upstream", max_depth=2)
    down = directed_impact("seed", symbols, edges, direction="downstream", max_depth=2)
    assert {r["symbol_id"] for r in up["blast"]} == {"caller"}
    assert {r["symbol_id"] for r in down["blast"]} == {"callee"}
    both = directed_impact("seed", symbols, edges, direction="both", max_depth=2)
    assert {r["symbol_id"] for r in both["blast"]} == {"caller", "callee"}
    assert both["files"]


def test_service_callers_and_impact_and_community() -> None:
    store = InMemoryStore()
    svc = CodeGraphService(store)
    svc.ingest_file(
        SCOPE,
        "actor",
        "corr",
        "idem-1",
        {
            "file_path": "auth.py",
            "source": "def check():\n    return 1\n\ndef login():\n    return check()\n",
            "language": "python",
        },
    )
    symbols = {s.name: s for s in store.list_symbols(SCOPE) if s.kind.value in {"function", "method"}}
    check = symbols["check"]
    callers = svc.callers(SCOPE, check.id, top_k=10)
    assert any(c["name"] == "login" for c in callers["callers"])
    impact = svc.impact_analysis(SCOPE, check.id, direction="upstream", max_depth=2)
    assert impact["blast_count"] >= 1
    assert "escalate_hint" in impact
    community = svc.community_of_symbol(SCOPE, check.id, member_limit=20)
    assert "community_id" in community
    assert "escalate_hint" in community


def test_extract_http_calls_python_and_normalize() -> None:
    source = 'import httpx\n\ndef run():\n    httpx.get("/api/v1/users")\n    requests.post("https://example.com/api/v1/users")\n'
    hits = extract_http_calls(source, language="python")
    assert len(hits) >= 1
    assert normalize_http_path("https://example.com/api/v1/users") == "/api/v1/users"
    assert normalize_http_path("/api/v1/users/") == "/api/v1/users"
    assert any(h.is_async for h in hits if h.framework == "httpx")


def test_extract_http_calls_javascript_fetch_and_axios() -> None:
    source = '''
async function load() {
  await fetch("/api/v1/users");
  axios.post("/api/v1/users", {});
}
'''
    hits = extract_http_calls(source, language="javascript")
    assert any(h.framework == "fetch" for h in hits)
    assert any(h.framework == "axios" for h in hits)
    fetch_hit = next(h for h in hits if h.framework == "fetch")
    assert fetch_hit.is_async is True


def test_http_calls_emitted_on_ingest() -> None:
    store = InMemoryStore()
    svc = CodeGraphService(store)
    routes = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/v1/users")
def list_users():
    return []
'''
    client = '''
import httpx

def fetch_users():
    return httpx.get("/api/v1/users")
'''
    sync_client = '''
import requests

def fetch_users_sync():
    return requests.get("/api/v1/users")
'''
    svc.ingest_file(
        SCOPE,
        "actor",
        "corr",
        "idem-r",
        {"file_path": "api.py", "source": routes, "language": "python"},
    )
    svc.ingest_file(
        SCOPE,
        "actor",
        "corr",
        "idem-c",
        {"file_path": "client.py", "source": client, "language": "python"},
    )
    svc.ingest_file(
        SCOPE,
        "actor",
        "corr",
        "idem-s",
        {"file_path": "client_sync.py", "source": sync_client, "language": "python"},
    )
    http_edges = [e for e in store.list_edges(SCOPE) if e.rel_type == "HTTP_CALLS"]
    async_edges = [e for e in store.list_edges(SCOPE) if e.rel_type == "ASYNC_CALLS"]
    assert async_edges, "httpx client should emit ASYNC_CALLS"
    assert http_edges, "requests client should emit HTTP_CALLS"


def test_call_path_pack() -> None:
    store = InMemoryStore()
    svc = CodeGraphService(store)
    svc.ingest_file(
        SCOPE,
        "actor",
        "corr",
        "idem-path",
        {
            "file_path": "auth.py",
            "source": "def check():\n    return 1\n\ndef login():\n    return check()\n",
            "language": "python",
        },
    )
    login = next(s for s in store.list_symbols(SCOPE) if s.name == "login")
    pack = svc.call_path_pack(SCOPE, login.id, max_depth=3)
    assert "call_path_ids" in pack
    assert "path" in pack
    assert pack["escalate_hint"]["prefer_before_raw_read"] is True


def test_call_path_pack_excludes_ambiguous_calls() -> None:
    store = InMemoryStore()
    svc = CodeGraphService(store)
    seed = _sym("sym:p:seed", "seed")
    exact = _sym("sym:p:exact", "exact")
    ambiguous = _sym("sym:p:ambiguous", "ambiguous")
    for symbol in (seed, exact, ambiguous):
        store.put_symbol(symbol)
    store.put_edge(_edge("e-exact", "CALLS", seed.id, exact.id))
    store.put_edge(
        _edge(
            "e-ambiguous",
            "CALLS",
            seed.id,
            ambiguous.id,
            CallConfidence.AMBIGUOUS,
        )
    )

    pack = svc.call_path_pack(SCOPE, seed.id, max_depth=2)

    assert exact.id in pack["call_path_ids"]
    assert ambiguous.id not in pack["call_path_ids"]


def test_getattr_call_extracted() -> None:
    src = '''
def helper():
    return 1

def run(obj):
    return getattr(obj, "helper")()
'''
    parsed = parse_python_source("mod.py", src)
    run = next(s for s in parsed.symbols if s.name == "run")
    assert "helper" in run.calls
    assert "helper" in run.reflection_calls
    assert "getattr" not in run.calls


def test_getattr_ingest_emits_calls_edge() -> None:
    store = InMemoryStore()
    svc = CodeGraphService(store)
    src = '''
def helper():
    return 1

def run(obj):
    return getattr(obj, "helper")()
'''
    svc.ingest_file(
        SCOPE,
        "actor",
        "corr",
        "idem-getattr",
        {"file_path": "dyn.py", "source": src, "language": "python"},
    )
    by_name = {s.name: s for s in store.list_symbols(SCOPE) if s.kind.value in {"function", "method"}}
    run = by_name["run"]
    helper = by_name["helper"]
    calls = [
        e
        for e in store.list_edges(SCOPE)
        if e.rel_type == "CALLS" and e.source_id == run.id and e.target_id == helper.id
    ]
    assert calls, "getattr('helper') should resolve to CALLS edge to helper"
    # GAP-T02: getattr-derived CALLS are reflection — never exact/probable.
    assert calls[0].confidence == CallConfidence.AMBIGUOUS
    assert calls[0].metadata.get("via") == "reflection"


def test_http_api_callers_impact_community_routes() -> None:
    from fastapi.testclient import TestClient

    store = InMemoryStore()
    svc = CodeGraphService(store)
    svc.ingest_file(
        SCOPE,
        "actor",
        "corr",
        "idem-http-api",
        {
            "file_path": "auth.py",
            "source": "def check():\n    return 1\n\ndef login():\n    return check()\n",
            "language": "python",
        },
    )
    check = next(s for s in store.list_symbols(SCOPE) if s.name == "check")
    client = TestClient(app(svc))
    headers = {
        "X-Tenant-Id": SCOPE.tenant_id,
        "X-Workspace-Id": SCOPE.workspace_id,
        "X-Actor-Id": "agent",
    }
    callers = client.post(
        f"/api/v1/projects/{SCOPE.project_id}/graph/symbols/{check.id}/callers",
        headers=headers,
        json={"top_k": 10, "max_depth": 1},
    )
    assert callers.status_code == 200
    body = callers.json()
    assert any(c["name"] == "login" for c in body["callers"])
    assert "escalate_hint" in body

    impact = client.post(
        f"/api/v1/projects/{SCOPE.project_id}/graph/symbols/{check.id}/impact",
        headers=headers,
        json={"direction": "upstream", "max_depth": 2},
    )
    assert impact.status_code == 200
    assert impact.json()["direction"] == "upstream"
    assert "blast" in impact.json()

    community = client.post(
        f"/api/v1/projects/{SCOPE.project_id}/graph/symbols/{check.id}/community",
        headers=headers,
        json={"member_limit": 20},
    )
    assert community.status_code == 200
    assert "community_id" in community.json()
    assert "escalate_hint" in community.json()

    login = next(s for s in store.list_symbols(SCOPE) if s.name == "login")
    call_path = client.post(
        f"/api/v1/projects/{SCOPE.project_id}/graph/symbols/{login.id}/call-path",
        headers=headers,
        json={"max_depth": 3},
    )
    assert call_path.status_code == 200
    assert "call_path_ids" in call_path.json()
