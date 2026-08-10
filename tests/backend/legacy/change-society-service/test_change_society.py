from __future__ import annotations

import asyncio
import httpx

from change_society.application.service import ChangeSocietyService
from change_society.application.control_plane import AgentControlPlane, AgentTemplate, CapabilityRouter
from change_society.domain.models import ConflictError, RunState, Scope
from change_society.infrastructure.evidence_catalog import ScenarioEvidenceProvider
from change_society.infrastructure.fake_model import DeterministicModelClient
from change_society.infrastructure.agent_adapters import ModelAgentAdapter, StaticAgentAdapterRegistry
from change_society.infrastructure.control_plane_repositories import InMemoryControlPlaneRepository
from change_society.infrastructure.repositories import InMemoryRunRepository
from change_society.interfaces.api import create_api


class FixedClock:
    def __init__(self):
        self.value = 0

    def now(self):
        self.value += 1
        return f"2026-07-11T00:00:{self.value:02d}+00:00"


class SequenceIds:
    def __init__(self):
        self.value = 0

    def new(self, prefix):
        self.value += 1
        return f"{prefix}_{self.value}"


def make_service(*, demo_auto_approve: bool = False):
    model = DeterministicModelClient()
    clock = FixedClock()
    ids = SequenceIds()
    templates = tuple(AgentTemplate(key, name, "test", "model", (capability,), role, name) for key, name, capability, role in (
        ("context", "Context Scout", "retrieve_scoped_project_truth", "context_scout"),
        ("change", "Change Analyst", "interpret_ambiguous_software_change", "change_analyst"),
        ("impact", "Impact Analyst", "analyze_cross_boundary_impact", "impact_analyst"),
        ("policy", "Policy Guardian", "evaluate_policy_and_approval_risk", "policy_guardian"),
        ("judge", "Conflict Judge", "decompose_route_reconcile", "coordinator_judge"),
        ("frontend", "Frontend Delivery Coordinator", "coordinate_frontend_ui_delivery", "frontend_delivery_lead"),
    ))
    control = AgentControlPlane(InMemoryControlPlaneRepository(), StaticAgentAdapterRegistry({"model": ModelAgentAdapter(model)}), CapabilityRouter(), clock, ids, templates)
    return ChangeSocietyService(InMemoryRunRepository(), model, ScenarioEvidenceProvider(), clock, ids, control, 1800, demo_auto_approve=demo_auto_approve)


SCOPE = Scope("tenant-a", "workspace-a", "project-a")
HEADERS = {
    "X-Tenant-Id": "tenant-a", "X-Workspace-Id": "workspace-a", "X-Actor-Id": "developer-a",
    "Idempotency-Key": "create-1", "X-Correlation-Id": "corr-test",
}


def test_agent_society_negotiates_and_blocks_for_approval():
    service = make_service()
    run = service.create_run(SCOPE, "developer-a", "corr-1", "create-1", "pricing-refactor", None)

    assert run.state == RunState.AWAITING_APPROVAL
    assert {message.sender_role.value for message in run.messages} >= {
        "coordinator", "context_scout", "change_analyst", "impact_analyst", "policy_guardian",
    }
    assert len(run.conflicts) == 1
    assert run.conflicts[0].status == "resolved"
    assert len(run.conflicts[0].rebuttal_message_ids) == 2
    assert run.approval and run.approval.status == "pending"
    assert any(message.message_type == "rebuttal_request" for message in run.messages)
    assert any(message.message_type == "coordinator_decision" for message in run.messages)
    assert {item["reason"] for item in run.excluded_evidence} >= {"not_current", "restricted_memory_boundary"}
    tickets = service.control_plane.list_tickets(SCOPE, run.run_id)
    assert len(tickets) == 8
    assert all(ticket.state.value == "completed" for ticket in tickets)
    assert all(ticket.assigned_agent_id for ticket in tickets)
    assert all({event.to_state for event in ticket.events} >= {"assigned", "claimed", "in_progress", "review", "completed"} for ticket in tickets)


def test_demo_auto_approve_completes_high_risk_run_for_display():
    service = make_service(demo_auto_approve=True)
    run = service.create_run(SCOPE, "developer-a", "corr-demo", "create-demo-auto", "pricing-refactor", None)
    assert run.state == RunState.COMPLETED
    assert run.approval is not None
    assert run.approval.status == "approve"
    assert "display only" in run.approval.reason.lower()
    assert any(m.message_type == "approval_decided" and m.payload.get("demo_only") for m in run.messages)


def test_approval_is_versioned_idempotent_and_creates_cross_session_memory():
    service = make_service()
    first = service.create_run(SCOPE, "developer-a", "corr-1", "create-1", "pricing-refactor", None)
    approved = service.decide(SCOPE, first.run_id, "reviewer-a", "corr-2", "approve-1", "approve", "Revenue owners approved the guarded plan.", first.version)

    assert approved.state == RunState.COMPLETED
    assert approved.final_result["memory_ref"] == "memory_1"
    repeated = service.decide(SCOPE, first.run_id, "reviewer-a", "corr-2", "approve-1", "approve", "Revenue owners approved the guarded plan.", first.version)
    assert repeated.run_id == approved.run_id

    second = service.create_run(SCOPE, "developer-a", "corr-3", "create-2", "pricing-refactor", "Review another checkout pricing refactor using the approved decision.")
    context_messages = [item for item in second.messages if item.sender_role.value == "context_scout"]
    assert "memory_1" in context_messages[0].evidence_refs


def test_idempotency_conflict_and_project_isolation():
    service = make_service()
    run = service.create_run(SCOPE, "developer-a", "corr-1", "same", "pricing-refactor", None)
    repeated = service.create_run(SCOPE, "developer-a", "corr-2", "same", "pricing-refactor", None)
    assert repeated.run_id == run.run_id
    try:
        service.create_run(SCOPE, "developer-a", "corr-3", "same", "pricing-refactor", "A different request with enough characters.")
        raise AssertionError("expected idempotency conflict")
    except ConflictError:
        pass
    assert service.repository.list_runs(Scope("other", "workspace-a", "project-a")) == []


def test_baseline_comparison_is_reproducible_and_reports_tradeoffs():
    service = make_service()
    run = service.create_run(SCOPE, "developer-a", "corr-1", "create-1", "pricing-refactor", None)
    comparison = service.evaluate_baseline(SCOPE, run.run_id)
    assert comparison["society"]["critical_impact_recall"] > comparison["baseline"]["critical_impact_recall"]
    assert comparison["tradeoffs"]["impact_recall_delta"] > 0
    assert "not statistically significant" in comparison["caveat"]
    ablation = comparison["ablation"]
    assert len(ablation["variants"]) == 4
    by_id = {item["variant_id"]: item["metrics"] for item in ablation["variants"]}
    assert by_id["full_change_society"]["policy_match_recall"] >= by_id["society_without_policy_guardian"]["policy_match_recall"]
    assert "efficiency" in ablation


def test_evaluate_all_scenarios_includes_aggregate():
    service = make_service()
    result = service.evaluate_all_scenarios(SCOPE, "developer-a", "eval-test")
    assert result["sample_count"] == 7
    assert "aggregate" in result
    assert "ablation_critical_impact_recall_avg" in result["aggregate"]


def test_all_versioned_demo_scenarios_complete_and_beat_baseline():
    service = make_service()
    for index, scenario_id in enumerate(("pricing-refactor", "password-migration", "payment-memory")):
        run = service.create_run(SCOPE, "developer-a", f"corr-{scenario_id}", f"create-{index}", scenario_id, None)
        assert run.state == RunState.AWAITING_APPROVAL
        comparison = service.evaluate_baseline(SCOPE, run.run_id)
        assert comparison["scenario_id"] == scenario_id
        assert comparison["society"]["critical_impact_recall"] >= comparison["baseline"]["critical_impact_recall"]
        assert comparison["society"]["policy_match_recall"] >= comparison["baseline"]["policy_match_recall"]


def test_fastapi_contract_and_error_envelope():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post("/api/v1/projects/project-a/society-runs", headers=HEADERS, json={"scenario_id": "pricing-refactor"})
            assert created.status_code == 200
            run = created.json()["society_run"]
            assert created.json()["correlation_id"] == "corr-test"

            messages = await client.get(f"/api/v1/projects/project-a/society-runs/{run['run_id']}/agent-messages?page_size=5", headers=HEADERS)
            assert messages.status_code == 200
            assert len(messages.json()["items"]) == 5
            assert messages.json()["page"]["has_more"] is True

            agents = await client.get("/api/v1/projects/project-a/managed-agents", headers=HEADERS)
            assert agents.status_code == 200
            assert len(agents.json()["items"]) == 6
            tickets = await client.get(f"/api/v1/projects/project-a/agent-tickets?run_id={run['run_id']}", headers=HEADERS)
            assert tickets.status_code == 200
            assert len(tickets.json()["items"]) == 8
            assert all(item["state"] == "completed" for item in tickets.json()["items"])

            approved = await client.post(
                f"/api/v1/projects/project-a/society-runs/{run['run_id']}:approve",
                headers={**HEADERS, "Idempotency-Key": "approve-api"},
                json={"reason": "Product and Finance approved.", "expected_version": run["version"]},
            )
            assert approved.status_code == 200
            assert approved.json()["society_run"]["state"] == "completed"

            missing = await client.get("/api/v1/projects/project-a/society-runs/missing", headers=HEADERS)
            assert missing.status_code == 404
            assert missing.json()["error"]["category"] == "not_found_error"

    asyncio.run(exercise())


def test_openapi_has_stable_operation_ids_and_no_duplicate_ids():
    schema = create_api(make_service()).openapi()
    operation_ids = []
    for methods in schema["paths"].values():
        for operation in methods.values():
            if isinstance(operation, dict) and "operationId" in operation:
                operation_ids.append(operation["operationId"])
    assert len(operation_ids) == len(set(operation_ids))
    assert "change_society_create_society_run" in operation_ids
    assert "change_society_evaluate_single_agent_baseline" in operation_ids
    assert "change_society_get_judging_engineering_profile" in operation_ids
    assert "change_society_evaluate_all_scenarios" in operation_ids
    assert "agent_control_list_managed_agents" in operation_ids
    assert "agent_control_list_agent_tickets" in operation_ids
