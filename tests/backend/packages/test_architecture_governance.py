"""GAP-A01–A07 architecture governance catalogs and helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from architecture_governance import (
    ArchitectureGovernanceError,
    admin_action_allowed,
    apply_trust_transition,
    forbidden_persistence_violations,
    guidance_resolve_required,
    load_bounded_context_map,
    load_read_model_catalog,
    load_sync_async_boundaries,
    operation_mode,
    provider_rank,
    read_model,
    resolve_tenancy_mode,
    retry_policy,
    surface_for_action,
    timeout_seconds,
    trust_allows_high_risk,
)


def test_bounded_context_map_has_owners_and_forbidden_edges():
    catalog = load_bounded_context_map()
    assert catalog["contexts"]
    owners = {c["owning_service"] for c in catalog["contexts"]}
    assert "core-data-service" in owners
    assert "memory-service" in owners
    assert catalog["forbidden_persistence_imports"]


def test_forbidden_persistence_scan_clean_for_memory():
    root = Path(__file__).resolve().parents[3] / "backend/services/memory-service/src"
    hits = forbidden_persistence_violations(root, "memory-service")
    assert hits == []


def test_sync_async_catalog_classifies_known_ops():
    catalog = load_sync_async_boundaries()
    assert catalog["operations"]
    assert operation_mode("code_graph.sync_repo") == "async"
    assert operation_mode("memory.retrieve_context") == "sync"
    assert operation_mode("code_graph.ingest_file") == "sync"
    assert operation_mode("memory.consolidate_memory") == "sync"
    assert operation_mode("outbox.relay") == "async"
    assert timeout_seconds("code_graph.ingest_file") == 60
    assert timeout_seconds("outbox.relay") == 120
    retry = retry_policy("memory.consolidate_memory")
    assert retry["max_attempts"] == 3
    assert retry["backoff_seconds"]


def test_read_model_catalog_includes_context_bundle():
    item = read_model("memory.context_bundle")
    assert item["build"] == "on_demand"
    assert item["invalidation"] == "source_memory_version_change"
    ids = {r["read_model_id"] for r in load_read_model_catalog()["read_models"]}
    assert "memory.context_bundle" in ids
    assert "code_graph.generation_context" in ids
    assert "audit.timeline" in ids
    assert "common_context.guidance" in ids


def test_tenancy_mode_default_and_fail_fast(monkeypatch):
    monkeypatch.delenv("ASTLOOM_TENANCY_MODE", raising=False)
    assert resolve_tenancy_mode({}) == "shared_scoped"
    with pytest.raises(ArchitectureGovernanceError):
        resolve_tenancy_mode({"ASTLOOM_TENANCY_MODE": "db_per_tenant"})
    with pytest.raises(ArchitectureGovernanceError):
        resolve_tenancy_mode({"ASTLOOM_TENANCY_MODE": "graph_per_tenant"})
    with pytest.raises(ArchitectureGovernanceError):
        resolve_tenancy_mode({"ASTLOOM_TENANCY_MODE": "deploy_per_customer"})


def test_shared_scoped_postgres_queries_include_tenant_id():
    root = Path(__file__).resolve().parents[3] / "backend/services"
    samples = [
        root / "memory-service/src/memory_service/postgres_store.py",
        root / "core-data-service/src/core_data_service/postgres_store.py",
        root / "audit-service/src/audit_service/postgres_store.py",
    ]
    for path in samples:
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "tenant_id" in text, path
        assert "tenant_id=%s" in text or "tenant_id =" in text


def test_trust_lifecycle_and_high_risk_floor():
    assert apply_trust_transition("standard", successes=5) == "elevated"
    assert apply_trust_transition("elevated", failures=3) == "untrusted"
    assert apply_trust_transition("elevated", revoke=True) == "untrusted"
    assert trust_allows_high_risk("elevated") is True
    assert trust_allows_high_risk("standard") is False
    assert provider_rank("local") > provider_rank("untrusted")


def test_admin_matrix_and_boundary_surfaces():
    assert admin_action_allowed("adapter.install", roles=["integration_admin"], permissions=[])
    assert not admin_action_allowed("adapter.install", roles=["viewer"], permissions=[])
    assert "mcp" in surface_for_action("guidance.resolve")
    assert guidance_resolve_required({"ASTLOOM_GUIDANCE_RESOLVE_REQUIRED": "1"}) is True


def test_admin_matrix_contract_all_actions():
    rows = {
        "tenant.create": (["tenant_admin"], True),
        "project.create": (["workspace_admin"], True),
        "policy.approve": (["policy_approver"], True),
        "weight_profile.change": (["memory_admin"], True),
        "adapter.install": (["integration_admin"], True),
    }
    for action_id, (roles, expected) in rows.items():
        assert admin_action_allowed(action_id, roles=roles, permissions=[]) is expected
        assert admin_action_allowed(action_id, roles=["viewer"], permissions=[]) is False


def test_agent_trust_package_reexports():
    from agent_trust import provider_rank as pr
    from agent_trust import trust_allows_high_risk as thr

    assert thr("elevated") is True
    assert pr("standard") == 2
