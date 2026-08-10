"""Unit tests for docs-sync fixture-noise hygiene."""

from __future__ import annotations

from docs_sync_service.core import DocsSyncService, Scope
from docs_sync_service.testing import InMemoryStore

from astloom_cli.docs_registry_hygiene import (
    is_docs_registry_fixture_noise,
    purge_docs_registry_fixture_noise,
)


def test_is_docs_registry_fixture_noise_markers():
    assert is_docs_registry_fixture_noise(
        symbol_path="never_linked_symbol_abc",
        file_path="src/never_linked_symbol_abc.py",
    )
    assert is_docs_registry_fixture_noise(symbol_path="ghost_audit_1", file_path="")
    assert is_docs_registry_fixture_noise(
        symbol_path="never_should_exist_xyz_999",
        file_path="src/module.py",
    )
    assert not is_docs_registry_fixture_noise(
        symbol_path="backend.packages.astloom_cli.docs_link_sync.sync_human_docs",
        file_path="backend/packages/astloom_cli/docs_link_sync.py",
    )


def test_purge_retries_list_symbols_after_admin_shutdown():
    store = InMemoryStore()
    service = DocsSyncService(store)
    scope = Scope("t", "w", "p-retry")
    service.index_symbol(
        scope,
        "agent",
        "c",
        "g",
        {
            "repo": "astloom",
            "file_path": "src/ghost_retry.py",
            "symbol_path": "ghost_retry",
            "kind": "function",
            "body": "def ghost_retry():\n    return 1\n",
        },
    )
    calls = {"n": 0}
    real_list = store.list_symbols

    def flaky_list(scope_arg):
        calls["n"] += 1
        if calls["n"] == 1:

            class AdminShutdown(Exception):
                pass

            raise AdminShutdown("terminating connection due to administrator command")
        return real_list(scope_arg)

    store.list_symbols = flaky_list  # type: ignore[method-assign]
    resets = {"n": 0}
    store.reset_connections = lambda: resets.__setitem__("n", resets["n"] + 1)  # type: ignore[attr-defined]
    result = purge_docs_registry_fixture_noise(service, scope)
    assert calls["n"] == 2
    assert resets["n"] == 1
    assert result["deleted_count"] == 1
    assert result["errors"] == []


def test_purge_docs_registry_fixture_noise_keeps_real_symbols():
    store = InMemoryStore()
    service = DocsSyncService(store)
    scope = Scope("t", "w", "p")
    real = service.index_symbol(
        scope,
        "agent",
        "c",
        "real",
        {
            "repo": "astloom",
            "file_path": "src/auth.py",
            "symbol_path": "auth.login",
            "kind": "function",
            "body": "def login():\n    return True\n",
        },
    )
    ghost = service.index_symbol(
        scope,
        "agent",
        "c",
        "ghost",
        {
            "repo": "astloom",
            "file_path": "src/ghost_abc.py",
            "symbol_path": "ghost_abc",
            "kind": "function",
            "body": "def ghost_abc():\n    return 1\n",
        },
    )
    never = service.index_symbol(
        scope,
        "agent",
        "c",
        "never",
        {
            "repo": "astloom",
            "file_path": "src/never_linked_x.py",
            "symbol_path": "never_linked_x",
            "kind": "function",
            "body": "def never_linked_x():\n    return 1\n",
        },
    )
    result = purge_docs_registry_fixture_noise(service, scope)
    assert result["deleted_count"] == 2
    ids = {row["id"] for row in result["deleted"]}
    assert ghost.id in ids
    assert never.id in ids
    remaining = store.list_symbols(scope)
    assert len(remaining) == 1
    assert remaining[0].id == real.id


def test_quality_audit_mcp_purges_fixture_noise(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from docs_sync_service.core import DocsSyncService, Scope as DocsScope
    from docs_sync_service.testing import InMemoryStore as DocsMem
    from mcp_gateway_service.backends import quality as quality_mod

    docs_store = DocsMem()
    docs = DocsSyncService(docs_store)
    dscope = DocsScope("mir", "dev", "astloom")
    docs.index_symbol(
        dscope,
        "agent",
        "c",
        "g1",
        {
            "repo": "astloom",
            "file_path": "src/ghost_zz.py",
            "symbol_path": "ghost_zz",
            "kind": "function",
            "body": "def ghost_zz():\n    return 1\n",
        },
    )

    backends = MagicMock()
    backends.docs = docs
    backends.docs_scope.return_value = dscope
    backends.actor_id = "mcp-gateway"
    backends.core_scope.return_value = SimpleNamespace(
        tenant_id="mir", workspace_id="dev", project_id="astloom"
    )

    monkeypatch.setattr(
        "astloom_cli.commands.quality_audit.collect.build_quality_audit_report",
        lambda *a, **k: {
            "findings": [],
            "summary": {"findings_total": 0, "categories_with_findings": 0},
            "categories": [],
            "generated_at": "2026-08-02T00:00:00Z",
            "repo": "/tmp",
        },
    )
    monkeypatch.setattr(
        "astloom_cli.commands.quality_audit.mcp_payload.compact_quality_audit_payload",
        lambda report, **k: {
            "findings": [],
            "findings_total": 0,
            "must_remediate": False,
            "actionable_count": 0,
            "summary": report.get("summary") or {},
            "categories": [],
            "agent_instruction": "ok",
        },
    )

    out = quality_mod.quality_audit(
        backends,
        {"top_n": 5},
        scope={"tenant_id": "mir", "workspace_id": "dev", "project_id": "astloom"},
        correlation_id="test-hygiene",
        base={"backend": "in_process"},
    )
    assert out["docs_registry_hygiene"]["deleted_count"] == 1
    assert docs_store.list_symbols(dscope) == []
