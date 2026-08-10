#!/usr/bin/env python3
"""Real E2E test: Astloom Change Society + external LangGraph Change Analyst worker."""

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

from change_society_sdk import ChangeSocietyClient, Scope

VERIFY = Path(__file__).resolve().parent / "verify_society_run.py"


def wait_http(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"timed out waiting for {url}")


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
                "ticket_state": ticket.get("state") if ticket else None,
                "ticket_runtime": (ticket.get("execution_metrics") or {}).get("runtime") if ticket else None,
            }
        )
    return {
        "message_count": len(messages),
        "ticket_count": len(tickets),
        "timeline": timeline,
        "roles_observed": sorted({item["sender_role"] for item in messages}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify society run with LangGraph change analyst worker.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", default=str(PACK / "evidence" / "real" / "integrator-langgraph"))
    parser.add_argument("--scenario", default="checkout-api-refactor")
    parser.add_argument("--live-all-roles", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{args.scenario}.json"

    cmd = [
        sys.executable,
        str(VERIFY),
        "--base-url",
        args.base_url,
        "--output",
        str(report_path),
        "--scenario",
        args.scenario,
        "--profile",
        "live-qwen" if args.live_all_roles else "deterministic",
        "--skip-cross-session-follow-up",
    ]
    if args.live_all_roles:
        cmd.append("--require-external-worker-all-roles")
    else:
        cmd.append("--require-langgraph-change-analyst")
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    summary = json.loads(completed.stdout)

    scope = Scope("live-test-tenant", "live-test-workspace", "live-test-project", "live-test-engineering-lead")
    client = ChangeSocietyClient(args.base_url, scope, timeout=600.0 if args.live_all_roles else 120.0)
    run_id = summary["run_id"]
    tickets = client.list_agent_tickets(run_id)
    trace = export_trace(client, run_id, tickets)
    trace_path = output_dir / f"{args.scenario}-interaction-trace.json"
    trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "suite": "astloom-langgraph-qwen-live-all-roles" if args.live_all_roles else "astloom-langgraph-integrator-real",
        "executed_at": datetime.now(UTC).isoformat(),
        "test_family": "live_integrator_langgraph_qwen" if args.live_all_roles else "real_integrator_langgraph",
        "verification_profile": "integrator-live-all" if args.live_all_roles else "integrator-langgraph",
        "scenario_id": args.scenario,
        "run_id": run_id,
        "report_path": str(report_path.relative_to(PACK)),
        "interaction_trace_path": str(trace_path.relative_to(PACK)),
        "langgraph_integrator": json.loads(report_path.read_text()).get("langgraph_integrator"),
        "secrets_included": False,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "manifest": str(manifest_path), "run_id": run_id}, indent=2))
    client.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(exc.stdout or "", file=sys.stdout)
        print(exc.stderr or "", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
