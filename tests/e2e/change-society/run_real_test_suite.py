#!/usr/bin/env python3
"""Run multiple end-to-end society tests and write redacted agent interaction evidence."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys
import time

_SUPPORT = Path(__file__).resolve().parents[2] / "support"
if str(_SUPPORT) not in sys.path:
    sys.path.insert(0, str(_SUPPORT))
from hackathon_pack import init_script  # noqa: E402

PACK = init_script(__file__)

import httpx

from change_society.infrastructure.evidence_catalog import DEMO_SCENARIO_IDS, SCENARIOS

SCENARIO_CATALOG = {item.scenario_id: item for item in SCENARIOS}
from change_society_sdk import ChangeSocietyClient, Scope

VERIFY = Path(__file__).resolve().parent / "verify_society_run.py"


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


def redact_message(message: dict) -> dict:
    payload = message.get("payload") or {}
    summary = payload.get("summary") or payload.get("rationale") or payload.get("verdict") or ""
    if isinstance(summary, str) and len(summary) > 240:
        summary = summary[:237] + "..."
    return {
        "message_id": message.get("message_id"),
        "message_type": message.get("message_type"),
        "sender_role": message.get("sender_role"),
        "recipient_role": message.get("recipient_role"),
        "capability": message.get("capability"),
        "task_ref": message.get("task_ref"),
        "risk_level": message.get("risk_level"),
        "status": message.get("status"),
        "evidence_refs": message.get("evidence_refs", []),
        "payload_excerpt": summary,
        "policies": payload.get("policies") if isinstance(payload.get("policies"), list) else [],
    }


def export_interaction_trace(client: ChangeSocietyClient, run_id: str, tickets: list[dict]) -> dict:
    messages = client.list_messages(run_id)
    ticket_by_id = {item["ticket_id"]: item for item in tickets}
    timeline = []
    for index, message in enumerate(messages):
        ticket = ticket_by_id.get(message.get("task_ref"))
        timeline.append(
            {
                "step": index + 1,
                **redact_message(message),
                "ticket_state": ticket.get("state") if ticket else None,
                "assigned_agent_id": ticket.get("assigned_agent_id") if ticket else None,
            }
        )
    return {
        "message_count": len(messages),
        "ticket_count": len(tickets),
        "timeline": timeline,
        "roles_observed": sorted({item["sender_role"] for item in messages}),
    }


def run_verify(
    base_url: str,
    scenario_id: str,
    output: Path,
    profile: str,
    expect_production: bool,
    *,
    skip_cross_session_follow_up: bool = False,
) -> dict:
    command = [
        sys.executable,
        str(VERIFY),
        "--base-url",
        base_url,
        "--output",
        str(output),
        "--scenario",
        scenario_id,
        "--profile",
        profile,
    ]
    if expect_production:
        command.append("--expect-production")
    if skip_cross_session_follow_up:
        command.append("--skip-cross-session-follow-up")
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute multi-domain real society tests with interaction traces.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", default=str(PACK / "evidence/real/suite"))
    parser.add_argument("--profile", choices=("deterministic", "auto", "live-qwen", "judge-live"), default="auto")
    parser.add_argument("--expect-production", action="store_true")
    parser.add_argument(
        "--scenarios",
        default=",".join(DEMO_SCENARIO_IDS),
        help="Comma-separated scenario ids (default: all demo scenarios)",
    )
    parser.add_argument(
        "--skip-cross-session-follow-up",
        action="store_true",
        help="Skip memory follow-up run per scenario (recommended for live 7-scenario judge smoke).",
    )
    args = parser.parse_args()

    readiness = wait_ready(args.base_url, 120)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario_ids = [item.strip() for item in args.scenarios.split(",") if item.strip()]

    scope = Scope("live-test-tenant", "live-test-workspace", "live-test-project", "live-test-engineering-lead")
    client_timeout = 300.0 if args.profile in {"live-qwen", "judge-live"} else 60.0
    client = ChangeSocietyClient(args.base_url, scope, timeout=client_timeout)

    suite_rows = []
    for scenario_id in scenario_ids:
        report_path = output_dir / f"{scenario_id}.json"
        summary = run_verify(
            args.base_url,
            scenario_id,
            report_path,
            args.profile,
            args.expect_production,
            skip_cross_session_follow_up=args.skip_cross_session_follow_up,
        )
        report_body = json.loads(report_path.read_text())
        run_id = summary["run_id"]
        tickets = client.list_agent_tickets(run_id)
        trace = export_interaction_trace(client, run_id, tickets)
        trace_path = output_dir / f"{scenario_id}-interaction-trace.json"
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        suite_rows.append(
            {
                "scenario_id": scenario_id,
                "domain": SCENARIO_CATALOG[scenario_id].domain,
                "governance_rules": list(SCENARIO_CATALOG[scenario_id].governance_rules),
                "feature_demonstrations": list(SCENARIO_CATALOG[scenario_id].feature_demonstrations),
                "run_id": run_id,
                "report_path": str(report_path.relative_to(PACK)),
                "interaction_trace_path": str(trace_path.relative_to(PACK)),
                "roles": summary.get("roles", []),
                "agent_ticket_count": trace["ticket_count"],
                "message_count": trace["message_count"],
                "rebuttal_response_count": report_body.get("rebuttal_response_count"),
                "final_state": report_body.get("final_state"),
                "ticket_lifecycle_verified": report_body.get("ticket_lifecycle_verified"),
                "model_provider": (report_body.get("readiness") or {}).get("checks", {}).get("model", {}).get("provider"),
                "real_model_agents": report_body.get("real_model_agents"),
            }
        )

    test_family = (
        "judge_live_qwen"
        if args.profile == "judge-live"
        else ("live_qwen" if args.profile == "live-qwen" else ("live" if args.expect_production else "real_deterministic"))
    )
    manifest = {
        "suite": "change-society-real-multi-domain",
        "executed_at": datetime.now(UTC).isoformat(),
        "test_family": test_family,
        "verification_profile": args.profile,
        "readiness": readiness,
        "scenario_count": len(suite_rows),
        "scenarios": suite_rows,
        "secrets_included": False,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "manifest": str(manifest_path), "scenarios": len(suite_rows)}, indent=2))
    client.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(exc.stdout or "", file=sys.stdout)
        print(exc.stderr or "", file=sys.stderr)
        print(f"REAL TEST SUITE FAILED: verify step exited {exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
    except Exception as exc:
        print(f"REAL TEST SUITE FAILED: {exc}", file=sys.stderr)
        raise
