"""GAP-004 approval mode routing + queue."""

from __future__ import annotations

from approval_modes import (
    accept_gate,
    decide_route,
    enqueue_gate,
    get_gate,
    list_gates,
    list_pending,
    reject_gate,
    resolve_effective_mode,
)


def test_default_mode_is_manual():
    profile = resolve_effective_mode(env={})
    assert profile["mode"] == "manual"


def test_hard_block_forces_human_even_when_auto():
    decision = decide_route(
        mode="auto_approve",
        subject_class="secret.exposure",
        risk_level="low",
        profile={"mode": "auto_approve", "hard_block_classes": ["secret.exposure"]},
    )
    assert decision.route == "human"
    assert decision.hard_block is True


def test_auto_approve_eligible_gate():
    decision = decide_route(
        mode="auto_approve",
        subject_class="docs.low_risk",
        risk_level="low",
        profile={"mode": "auto_approve", "denied_auto_classes": []},
    )
    assert decision.route == "auto"


def test_system_routed_respects_max_risk():
    decision = decide_route(
        mode="system_routed",
        subject_class="docs.low_risk",
        risk_level="critical",
        profile={
            "mode": "system_routed",
            "allowed_auto_classes": ["docs.low_risk"],
            "max_auto_risk": "medium",
        },
    )
    assert decision.route == "human"


def test_queue_enqueue_accept_reject(tmp_path):
    pending = enqueue_gate(
        tmp_path,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        subject_ref="change:1",
        subject_class="docs.low_risk",
        risk_level="low",
        project_state={"approval_mode": "manual"},
        now_iso="2026-07-23T00:00:00Z",
    )
    assert pending["status"] == "pending"
    assert len(list_pending(tmp_path, tenant_id="t", workspace_id="w", project_id="p")) == 1
    accepted = accept_gate(
        tmp_path,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        approval_id=pending["id"],
        actor="tester",
        reason="ok",
        now_iso="2026-07-23T00:01:00Z",
    )
    assert accepted["status"] == "approved"
    assert list_pending(tmp_path, tenant_id="t", workspace_id="w", project_id="p") == []


def test_queue_auto_resolves_when_mode_auto(tmp_path):
    item = enqueue_gate(
        tmp_path,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        subject_ref="change:2",
        subject_class="docs.low_risk",
        risk_level="low",
        project_state={"approval_mode": "auto_approve"},
        now_iso="2026-07-23T00:00:00Z",
    )
    assert item["status"] == "approved"
    assert item["resolved_by"] == "system:auto_approve"


def test_list_gates_filters_by_id_and_time(tmp_path):
    early = enqueue_gate(
        tmp_path,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        subject_ref="change:early",
        project_state={"approval_mode": "manual"},
        now_iso="2026-07-20T00:00:00Z",
    )
    late = enqueue_gate(
        tmp_path,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        subject_ref="change:late",
        project_state={"approval_mode": "manual"},
        now_iso="2026-07-23T12:00:00Z",
    )
    by_id = list_gates(
        tmp_path,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        approval_id=early["id"],
    )
    assert [item["id"] for item in by_id] == [early["id"]]
    assert get_gate(
        tmp_path,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        approval_id=late["id"],
    )["subject_ref"] == "change:late"
    window = list_gates(
        tmp_path,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        since="2026-07-23T00:00:00Z",
        until="2026-07-23T23:59:59Z",
    )
    assert [item["subject_ref"] for item in window] == ["change:late"]
    pending_only = list_pending(tmp_path, tenant_id="t", workspace_id="w", project_id="p")
    assert len(pending_only) == 2
