#!/usr/bin/env python3
"""Live integrator suite: all roles via external LangGraph+Qwen worker + Astloom control plane."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

_SUPPORT = Path(__file__).resolve().parents[2] / "support"
if str(_SUPPORT) not in sys.path:
    sys.path.insert(0, str(_SUPPORT))
from hackathon_pack import init_script  # noqa: E402

PACK = init_script(__file__)

import httpx

from change_society.infrastructure.evidence_catalog import DEMO_SCENARIO_IDS, SCENARIOS
from change_society_sdk import ChangeSocietyClient, Scope

VERIFY = Path(__file__).resolve().parents[2] / "e2e" / "change-society" / "verify_society_run.py"
SCENARIO_CATALOG = {item.scenario_id: item for item in SCENARIOS}


def redact_message(message: dict) -> dict:
    payload = message.get("payload") or {}
    summary = payload.get("summary") or payload.get("rationale") or payload.get("verdict") or ""
    if isinstance(summary, str) and len(summary) > 240:
        summary = summary[:237] + "..."
    return {
        "message_id": message.get("message_id"),
        "message_type": message.get("message_type"),
        "sender_role": message.get("sender_role"),
        "capability": message.get("capability"),
        "task_ref": message.get("task_ref"),
        "payload_excerpt": summary,
    }


def export_trace(client: ChangeSocietyClient, run_id: str, tickets: list[dict]) -> dict:
    messages = client.list_messages(run_id)
    ticket_by_id = {item["ticket_id"]: item for item in tickets}
    timeline = []
    for index, message in enumerate(messages):
        ticket = ticket_by_id.get(message.get("task_ref"))
        timeline.append(
            {
                "step": index + 1,
                **redact_message(message),
                "ticket_runtime": (ticket.get("execution_metrics") or {}).get("runtime") if ticket else None,
            }
        )
    return {"message_count": len(messages), "ticket_count": len(tickets), "timeline": timeline}


def run_verify(base_url: str, scenario_id: str, output: Path) -> dict:
    cmd = [
        sys.executable,
        str(VERIFY),
        "--base-url",
        base_url,
        "--output",
        str(output),
        "--scenario",
        scenario_id,
        "--profile",
        "judge-live",
        "--require-external-worker-all-roles",
        "--skip-cross-session-follow-up",
    ]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", default=str(PACK / "evidence" / "live" / "integrator-langgraph-qwen"))
    parser.add_argument("--scenarios", default=",".join(DEMO_SCENARIO_IDS))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario_ids = [s.strip() for s in args.scenarios.split(",") if s.strip()]

    scope = Scope("live-test-tenant", "live-test-workspace", "live-test-project", "live-test-engineering-lead")
    client = ChangeSocietyClient(args.base_url, scope, timeout=600.0)

    rows = []
    for scenario_id in scenario_ids:
        report_path = output_dir / f"{scenario_id}.json"
        summary = run_verify(args.base_url, scenario_id, report_path)
        run_id = summary["run_id"]
        tickets = client.list_agent_tickets(run_id)
        trace = export_trace(client, run_id, tickets)
        trace_path = output_dir / f"{scenario_id}-interaction-trace.json"
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report = json.loads(report_path.read_text())
        rows.append(
            {
                "scenario_id": scenario_id,
                "domain": SCENARIO_CATALOG[scenario_id].domain,
                "run_id": run_id,
                "report_path": str(report_path.relative_to(PACK)),
                "interaction_trace_path": str(trace_path.relative_to(PACK)),
                "langgraph_integrator": report.get("langgraph_integrator"),
                "rebuttal_response_count": report.get("rebuttal_response_count"),
                "final_state": report.get("final_state"),
                "ticket_lifecycle_verified": report.get("ticket_lifecycle_verified"),
                "agent_ticket_count": trace["ticket_count"],
                "message_count": trace["message_count"],
            }
        )

    readiness = httpx.get(f"{args.base_url.rstrip('/')}/ready", timeout=10).json()
    manifest = {
        "suite": "astloom-langgraph-qwen-live-all-roles",
        "executed_at": datetime.now(UTC).isoformat(),
        "test_family": "live_integrator_langgraph_qwen",
        "verification_profile": "integrator-live-all",
        "scenario_count": len(rows),
        "scenarios": rows,
        "readiness": readiness,
        "secrets_included": False,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "manifest": str(manifest_path), "scenarios": len(rows)}, indent=2))
    client.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(exc.stdout or "", file=sys.stdout)
        print(exc.stderr or "", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
