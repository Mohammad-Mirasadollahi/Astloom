#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

_SUPPORT = Path(__file__).resolve().parents[2] / "support"
if str(_SUPPORT) not in sys.path:
    sys.path.insert(0, str(_SUPPORT))
from hackathon_pack import init_script  # noqa: E402

PACK = init_script(__file__)

import httpx

from change_society_sdk import ChangeSocietyClient, Scope

from change_society.infrastructure.evidence_catalog import SCENARIOS

SCENARIO_CATALOG = {item.scenario_id: item for item in SCENARIOS}

REQUIRED_ROLES = {"coordinator", "context_scout", "change_analyst", "impact_analyst", "policy_guardian"}


def _assert_external_langgraph_agents(tickets: list[dict]) -> None:
    for item in tickets:
        if item.get("state") != "completed":
            continue
        runtime = str((item.get("execution_metrics") or {}).get("runtime") or "")
        if not (
            "langgraph" in runtime.lower()
            or "society-worker" in runtime.lower()
            or runtime.startswith("langgraph-qwen")
            or "langgraph-sdk" in runtime.lower()
        ):
            raise AssertionError(
                f"expected external LangGraph worker runtime on ticket {item.get('ticket_id')}, got {runtime!r}"
            )


def _assert_real_model_agents(tickets: list[dict], readiness: dict) -> None:
    provider = (readiness.get("checks") or {}).get("model", {}).get("provider")
    if provider != "qwen_cloud":
        raise RuntimeError(
            "Judge live proof requires real Qwen model agents (CHANGE_SOCIETY_MODEL_PROVIDER=qwen and QWEN_API_KEY). "
            f"Readiness model provider was {provider!r}."
        )
    for item in tickets:
        if item.get("state") != "completed":
            continue
        metrics = item.get("execution_metrics") or {}
        runtime = str(metrics.get("runtime") or "")
        if not runtime.startswith("model:"):
            raise AssertionError(f"expected ModelAgentAdapter ticket runtime, got {runtime!r} on {item.get('ticket_id')}")
        if int(metrics.get("input_tokens") or 0) < 1:
            raise AssertionError(f"expected live model token usage on ticket {item.get('ticket_id')}")


def wait_ready(base_url: str, timeout: int) -> dict:
    deadline = time.monotonic() + timeout
    last_error = "not started"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base_url.rstrip('/')}/ready", timeout=3)
            if response.status_code == 200:
                return response.json()
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(1)
    raise RuntimeError(f"API readiness timed out: {last_error}")


def _assert_ticket_lifecycle(tickets: list[dict]) -> None:
    expected_lifecycle = {"assigned", "claimed", "in_progress", "review", "completed"}
    assert all(item["state"] == "completed" for item in tickets), "every dispatched agent ticket must complete"
    assert all(expected_lifecycle <= {event["to_state"] for event in item["events"]} for item in tickets), "ticket lifecycle evidence is incomplete"


def _verify_negotiation(messages: list[dict], tickets: list[dict], *, strict: bool) -> dict[str, int]:
    rebuttal_count = sum(item["message_type"] == "rebuttal_response" for item in messages)
    has_decision = any(item["message_type"] == "coordinator_decision" for item in messages)
    negotiation_events = sum(
        1 for item in messages if item["message_type"] in {"rebuttal_request", "rebuttal_response", "coordinator_decision"}
    )
    if strict:
        assert rebuttal_count == 2, "expected exactly two rebuttal responses"
        assert has_decision, "coordinator decision missing"
        frontend_tickets = [item for item in tickets if item["capability"] == "coordinate_frontend_ui_delivery"]
        assert len(frontend_tickets) == 1, "expected one frontend delivery ticket"
        assert len(tickets) == 8, f"expected eight durable agent tickets including frontend handoff, received {len(tickets)}"
    else:
        assert rebuttal_count in {0, 2}, f"unexpected rebuttal count {rebuttal_count}"
        if rebuttal_count:
            assert rebuttal_count == 2 and has_decision, "partial negotiation evidence"
            assert len(tickets) == 8, f"negotiation runs must produce eight tickets including frontend handoff, received {len(tickets)}"
            assert any(item["capability"] == "coordinate_frontend_ui_delivery" for item in tickets), "frontend delivery ticket missing"
        else:
            assert len(tickets) >= 4, f"expected at least four specialist tickets, received {len(tickets)}"
        frontend_tickets = [item for item in tickets if item["capability"] == "coordinate_frontend_ui_delivery"]
        assert frontend_tickets, "expected a frontend delivery ticket for cross-team handoff"
    return {"rebuttal_response_count": rebuttal_count, "negotiation_event_count": negotiation_events}


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute and verify the complete Change Society workflow.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expect-production", action="store_true")
    parser.add_argument("--profile", choices=("deterministic", "auto", "live-qwen", "judge-live"), default="auto")
    parser.add_argument("--scenario", default="pricing-refactor")
    parser.add_argument(
        "--require-langgraph-change-analyst",
        action="store_true",
        help="Assert change_analyst tickets executed via external LangGraph worker (integrator profile).",
    )
    parser.add_argument(
        "--require-external-worker-all-roles",
        action="store_true",
        help="Assert every completed agent ticket used the external society worker runtime (live integrator).",
    )
    parser.add_argument(
        "--skip-cross-session-follow-up",
        action="store_true",
        help="Skip second run memory recall check (integrator/LangGraph harness).",
    )
    args = parser.parse_args()

    readiness = wait_ready(args.base_url, 90)
    checks = readiness.get("checks", {})
    model_provider = checks.get("model", {}).get("provider", "")
    if args.profile == "auto":
        strict = model_provider != "qwen_cloud"
    elif args.profile == "deterministic":
        strict = True
    else:
        strict = False
    if args.profile == "judge-live" and model_provider != "qwen_cloud" and not args.require_external_worker_all_roles:
        raise RuntimeError("profile judge-live refused: API is not using live Qwen Cloud model agents.")
    client_timeout = (
        600.0
        if args.profile in {"live-qwen", "judge-live"} or args.require_external_worker_all_roles
        else (300.0 if not strict else 45.0)
    )
    if args.expect_production:
        if checks.get("model", {}).get("provider") != "qwen_cloud":
            raise RuntimeError("Live test refused: API is not using Qwen Cloud.")
        if checks.get("store", {}).get("store") != "postgresql":
            raise RuntimeError("Live test refused: API is not using PostgreSQL.")
        if readiness.get("status") != "ok":
            raise RuntimeError("Live test refused: production readiness is not ok.")

    client = ChangeSocietyClient(args.base_url, Scope("live-test-tenant", "live-test-workspace", "live-test-project", "live-test-engineering-lead"), timeout=client_timeout)
    run_request: str | None = None
    if args.profile == "judge-live":
        run_request = SCENARIO_CATALOG[args.scenario].effective_judge_request()
    run = client.create_run(args.scenario, run_request, idempotency_key=f"live-create-{args.scenario}-{uuid4()}")
    agents = client.list_managed_agents()
    tickets = client.list_agent_tickets(run["run_id"])
    messages = client.list_messages(run["run_id"])
    roles = {item["sender_role"] for item in messages}
    assert REQUIRED_ROLES <= roles, f"missing roles: {REQUIRED_ROLES - roles}"
    negotiation_metrics = _verify_negotiation(messages, tickets, strict=strict)
    if strict:
        assert run["state"] == "awaiting_approval", f"expected approval boundary, received {run['state']}"
    else:
        assert run["state"] in {"awaiting_approval", "completed"}, f"unexpected run state {run['state']}"
    assert len(agents) >= 6, "expected at least six registered managed agents (including frontend delivery)"
    _assert_ticket_lifecycle(tickets)
    if args.profile == "judge-live":
        if args.require_external_worker_all_roles:
            _assert_external_langgraph_agents(tickets)
        else:
            _assert_real_model_agents(tickets, readiness)

    langgraph_evidence: dict[str, object] = {}
    if args.require_langgraph_change_analyst:
        change_tickets = [
            item
            for item in tickets
            if item.get("capability") == "interpret_ambiguous_software_change"
            or "change" in (item.get("title") or "").lower()
        ]
        assert change_tickets, "no change_analyst capability tickets found"
        runtimes = []
        for item in change_tickets:
            metrics = item.get("execution_metrics") or {}
            runtime = str(metrics.get("runtime") or "")
            runtimes.append({"ticket_id": item["ticket_id"], "state": item["state"], "runtime": runtime})
        external = [row for row in runtimes if "langgraph" in row["runtime"].lower() or "society-worker" in row["runtime"].lower()]
        assert external, f"expected external worker runtime on change tickets, got {runtimes}"
        langgraph_evidence = {
            "change_analyst_ticket_runtimes": runtimes,
            "external_worker_runtime": external[0]["runtime"],
            "worker_integration": "webhook_langgraph_qwen",
        }

    if args.require_external_worker_all_roles:
        ticket_runtimes = []
        for item in tickets:
            metrics = item.get("execution_metrics") or {}
            runtime = str(metrics.get("runtime") or "")
            ticket_runtimes.append(
                {
                    "ticket_id": item["ticket_id"],
                    "capability": item.get("capability"),
                    "state": item["state"],
                    "runtime": runtime,
                }
            )
        invalid = [
            row
            for row in ticket_runtimes
            if row["state"] == "completed"
            and not (
                "langgraph" in row["runtime"].lower()
                or "society-worker" in row["runtime"].lower()
                or row["runtime"].startswith("langgraph-qwen")
                or "langgraph-sdk" in row["runtime"].lower()
            )
        ]
        assert not invalid, f"expected external worker runtime on all tickets, invalid={invalid}"
        langgraph_evidence = {
            **langgraph_evidence,
            "all_ticket_runtimes": ticket_runtimes,
            "external_worker_runtime": ticket_runtimes[0]["runtime"] if ticket_runtimes else "",
            "worker_integration": "webhook_langgraph_qwen_all_roles",
        }

    if run["state"] == "awaiting_approval":
        approved = client.decide(
            run["run_id"],
            "approve",
            "Live-test reviewer approved the evidence-bound guarded plan.",
            run["version"],
            f"live-approve-{uuid4()}",
        )
        assert approved["state"] == "completed"
    else:
        approved = client.get_run(run["run_id"])
        assert approved["state"] == "completed"
    evaluation = client.evaluate_baseline(run["run_id"])

    recalled = False
    if not args.skip_cross_session_follow_up and args.profile != "judge-live":
        follow_up = client.create_run(args.scenario, "Review a follow-up change using the previously approved decision.", f"live-followup-{args.scenario}-{uuid4()}")
        follow_messages = client.list_messages(follow_up["run_id"])
        context = next(item for item in follow_messages if item["sender_role"] == "context_scout")
        recalled = any(ref.startswith("memory_") for ref in context.get("evidence_refs", []))
        if not strict and not recalled:
            recalled = any("memory_" in str(item) for item in follow_messages)

    frontend_delivery = httpx.get(
        f"{args.base_url.rstrip('/')}/api/v1/projects/live-test-project/society-runs/{run['run_id']}/frontend-delivery",
        headers={
            "X-Tenant-Id": "live-test-tenant",
            "X-Workspace-Id": "live-test-workspace",
            "X-Actor-Id": "live-test-engineering-lead",
        },
        timeout=30,
    ).json()["delivery"]
    assert frontend_delivery["frontend_work_required"] is True
    assert frontend_delivery["team_queue"] == "frontend"
    handoff_types = {item["message_type"] for item in messages}
    assert "frontend_delivery_handoff" in handoff_types

    report = {
        "test_family": "live" if args.expect_production else "real_deterministic",
        "executed_at": datetime.now(UTC).isoformat(),
        "environment": "production_like" if args.expect_production else "local_test",
        "data_classification": "synthetic",
        "mutation_policy": "isolated_test_project_writes",
        "readiness": readiness,
        "run_id": run["run_id"],
        "correlation_id": run.get("correlation_id"),
        "roles": sorted(roles),
        "managed_agent_count": len(agents),
        "managed_agents": [{"agent_id": item["agent_id"], "name": item["name"], "capabilities": item["capabilities"], "state": item["state"], "adapter_type": item["adapter_type"]} for item in agents],
        "agent_ticket_count": len(tickets),
        "ticket_lifecycle_verified": True,
        "message_count": len(messages),
        "negotiation_event_count": negotiation_metrics["negotiation_event_count"],
        "rebuttal_response_count": negotiation_metrics["rebuttal_response_count"],
        "verification_profile": args.profile,
        "strict_negotiation_assertions": strict,
        "real_model_agents": args.profile == "judge-live" and not args.require_external_worker_all_roles,
        "langgraph_worker_agents": args.profile == "judge-live" and args.require_external_worker_all_roles,
        "judge_demo_request": run_request if args.profile == "judge-live" else None,
        "approval_state_before": run["state"],
        "final_state": approved["state"],
        "cross_session_memory_recalled": recalled,
        "society_metrics": run.get("metrics", {}),
        "baseline_comparison": evaluation,
        "frontend_delivery": frontend_delivery,
        "secrets_included": False,
    }
    if langgraph_evidence:
        report["verification_profile"] = (
            "integrator-live-all" if args.require_external_worker_all_roles else "integrator-langgraph"
        )
        report["langgraph_integrator"] = langgraph_evidence
    if args.require_external_worker_all_roles:
        report["test_family"] = "live_integrator_langgraph_qwen"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": "passed", "report": str(output), "run_id": run["run_id"], "roles": sorted(roles)}, indent=2))
    client.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"LIVE TEST FAILED: {exc}", file=sys.stderr)
        raise
