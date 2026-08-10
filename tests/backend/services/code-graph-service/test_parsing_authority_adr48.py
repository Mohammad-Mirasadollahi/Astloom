"""ADR 48: durable SoR is AST; LSP writers rejected; reconcile_after_edit → pending/reingest."""

from __future__ import annotations

from pathlib import Path

import pytest

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.enums import CallConfidence
from code_graph_service.domain.errors import ValidationError
from code_graph_service.domain.parsing_authority import (
    DURABLE_EDGE_REFERENCE_KIND,
    assert_durable_edge_metadata_allowed,
)
from code_graph_service.testing import InMemoryStore


def _scope() -> Scope:
    return Scope(tenant_id="t", workspace_id="w", project_id="p")


def test_assert_durable_edge_rejects_lsp_provenance():
    with pytest.raises(ValidationError, match="LSP/IDE"):
        assert_durable_edge_metadata_allowed({"provenance": "lsp"})


def test_assert_durable_edge_allows_ast_enrichment_provenance():
    assert_durable_edge_metadata_allowed({"provenance": "di_injection"})
    assert_durable_edge_metadata_allowed(None)
    assert_durable_edge_metadata_allowed({"call": "foo"})


def test_put_edge_rejects_lsp_writer_before_store():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = _scope()
    with pytest.raises(ValidationError, match="forbidden writer"):
        svc._put_edge(
            scope,
            "CALLS",
            "sym:a",
            "sym:b",
            file_path="a.py",
            confidence=CallConfidence.EXACT,
            metadata={"writer": "language_server"},
        )
    assert store.list_edges(scope) == []


def test_put_edge_allows_normal_ast_call_metadata():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = _scope()
    # Placeholders materialize unresolved/ext only; seed real symbols via ingest.
    svc.ingest_file(
        scope,
        "actor",
        "corr",
        "idem-1",
        {
            "file_path": "mod.py",
            "source": "def a():\n    b()\n\ndef b():\n    return 1\n",
            "language": "python",
        },
    )
    edges = store.list_edges(scope)
    assert any(e.rel_type == "CALLS" for e in edges)


def test_reconcile_after_edit_pending_only():
    svc = CodeGraphService(InMemoryStore())
    out = svc.reconcile_after_edit(["src/a.py", "src/b.py"])
    assert out["reference_kind"] == DURABLE_EDGE_REFERENCE_KIND
    assert out["mode"] == "pending_only"
    assert out["reconciled"] is False
    assert out["freshness"]["pending_count"] == 2


def test_reconcile_after_edit_run_sync_requires_scope_and_root():
    svc = CodeGraphService(InMemoryStore())
    with pytest.raises(ValidationError, match="scope is required"):
        svc.reconcile_after_edit(["a.py"], run_sync=True, root_path="/tmp")
    with pytest.raises(ValidationError, match="root_path is required"):
        svc.reconcile_after_edit(["a.py"], scope=_scope(), run_sync=True)


def test_reconcile_after_edit_run_sync_reingests(tmp_path: Path):
    root = tmp_path
    rel = "mod.py"
    src = root / rel
    src.write_text("def hello():\n    return 1\n", encoding="utf-8")
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = _scope()
    svc.ingest_file(
        scope,
        "actor",
        "c1",
        "i1",
        {"file_path": rel, "source": src.read_text(encoding="utf-8"), "language": "python"},
    )
    src.write_text("def hello():\n    return 2\n\ndef world():\n    return 3\n", encoding="utf-8")
    out = svc.reconcile_after_edit(
        [rel],
        scope=scope,
        root_path=str(root),
        actor_id="actor",
        correlation_id="c2",
        idempotency_key="i2",
        run_sync=True,
    )
    assert out["reconciled"] is True
    assert out["reference_kind"] == DURABLE_EDGE_REFERENCE_KIND
    assert out["mode"] in {"incremental", "noop", "full"}
    names = {s.name for s in store.list_symbols(scope) if s.file_path == rel}
    assert "hello" in names
    assert "world" in names
