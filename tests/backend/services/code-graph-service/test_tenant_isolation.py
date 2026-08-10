"""Tenant/project isolation enforcement for code-graph (backlog 34 D1 / GAP-005)."""

from __future__ import annotations

import pytest

from code_graph_service.core import CodeGraphService, NotFoundError, Scope
from code_graph_service.testing import InMemoryStore


AUTH = """
def secret_login(password):
    return len(password) > 8
"""


def test_inmemory_store_hides_symbols_across_tenants_and_projects():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    a = Scope("tenant-a", "ws", "proj-a")
    b = Scope("tenant-b", "ws", "proj-a")  # different tenant, same project id
    c = Scope("tenant-a", "ws", "proj-c")  # same tenant, different project

    svc.ingest_file(
        a,
        "agent",
        "c1",
        "k1",
        {"file_path": "src/auth.py", "source": AUTH, "language": "python"},
    )
    assert store.list_symbols(a)
    assert store.list_symbols(b) == []
    assert store.list_symbols(c) == []

    pack_a = svc.explore(a, "secret_login")
    assert pack_a["sections"]
    pack_b = svc.explore(b, "secret_login")
    # Other tenant must not see A's symbols via explore
    symbols_b = [s for sec in pack_b.get("sections") or [] for s in sec.get("symbols") or []]
    assert symbols_b == []

    hybrid_b = svc.hybrid_search(b, "secret_login")
    assert hybrid_b["hits"] == []

    sid = store.list_symbols(a)[0].id
    with pytest.raises(NotFoundError):
        store.get_symbol(sid, b)
    with pytest.raises(NotFoundError):
        store.get_symbol(sid, c)


def test_detect_changes_does_not_leak_cross_project_files():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    a = Scope("t", "w", "p1")
    other = Scope("t", "w", "p2")
    svc.ingest_file(
        a,
        "agent",
        "c1",
        "k1",
        {"file_path": "src/auth.py", "source": AUTH, "language": "python"},
    )
    report = svc.detect_changes(other, ["src/auth.py"])
    assert report["changed_functions"] == []
    assert report["risk_score"] == 0.0
