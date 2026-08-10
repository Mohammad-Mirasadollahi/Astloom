"""Service-level unused_candidates freshness / CI-40 absence claims."""

from __future__ import annotations

from code_graph_service.application.service import CodeGraphService
from code_graph_service.domain.enums import DocStatus, SymbolKind
from code_graph_service.domain.models import GraphSymbol, Scope
from code_graph_service.testing import InMemoryStore


def _private_orphan(scope: Scope) -> GraphSymbol:
    return GraphSymbol(
        id="s:orphan",
        scope=scope,
        kind=SymbolKind.FUNCTION,
        file_path="pkg/orphan.py",
        name="orphan_fn",
        qualified_name="pkg.orphan.orphan_fn",
        signature="def orphan_fn():",
        body="return 1",
        hash_value="h",
        ai_documentation="",
        doc_status=DocStatus.UNCHANGED,
        embedding=[],
        visibility="private",
    )


def test_durable_sync_stamp_allows_absence_claims_after_restart():
    """MCP restart keeps process freshness unknown, but durable stamp must not
    wipe safe_to_delete via false index_incomplete (CI-40).
    """
    store = InMemoryStore()
    scope = Scope("t", "w", "dur_unused")
    first = CodeGraphService(store)
    store.put_symbol(_private_orphan(scope))
    first.record_sync_stamp(scope)
    assert first.freshness_status(scope)["status"] == "ok"

    restarted = CodeGraphService(store)
    assert restarted.freshness_status(scope)["status"] == "unknown"
    assert restarted.freshness_status(scope)["last_sync_at"]

    out = restarted.unused_candidates(
        scope,
        scope_mode="project_scan",
        min_confidence=0.5,
        include_uncertain=True,
    )
    coverage = out.get("index_coverage") or {}
    assert coverage.get("status") == "ok"
    assert coverage.get("safe_absence_claims") is True
    assert out.get("freshness") == "ok"
    assert any(r.get("safe_to_delete") for r in (out.get("candidates") or []))


def test_pending_sync_still_fail_closes_absence_claims():
    store = InMemoryStore()
    scope = Scope("t", "w", "pending_unused")
    svc = CodeGraphService(store)
    store.put_symbol(_private_orphan(scope))
    svc.record_sync_stamp(scope)
    svc.mark_file_pending("pkg/orphan.py")

    out = svc.unused_candidates(
        scope,
        scope_mode="project_scan",
        min_confidence=0.5,
        include_uncertain=True,
    )
    coverage = out.get("index_coverage") or {}
    assert coverage.get("safe_absence_claims") is False
    assert out.get("freshness") == "pending_sync"
    assert not any(r.get("safe_to_delete") for r in (out.get("candidates") or []))
