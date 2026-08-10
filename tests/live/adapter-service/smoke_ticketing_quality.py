#!/usr/bin/env python3
"""Small live quality smoke for ExternalTicket + AgentTicket against restarted services."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from uuid import uuid4

ADAPTER = "http://127.0.0.1:32170"
ORCH = "http://127.0.0.1:32192"
RUN = uuid4().hex[:10]
PROJECT = f"ticket-smoke-{RUN}"
TENANT = "live-smoke"
WORKSPACE = "astloom"


class Fail(Exception):
    pass


def call(method: str, base: str, path: str, *, body: dict | None = None, idem: str | None = None) -> dict:
    headers = {
        "X-Tenant-Id": TENANT,
        "X-Workspace-Id": WORKSPACE,
        "X-Actor-Id": "ticket-smoke",
        "X-Correlation-Id": f"smoke-{RUN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if idem:
        headers["Idempotency-Key"] = idem
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else {}
            payload["_http_status"] = resp.status
            return payload
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise Fail(f"{method} {path} -> HTTP {exc.code}: {detail[:500]}") from exc


def expect(cond: bool, msg: str) -> None:
    if not cond:
        raise Fail(msg)


def main() -> int:
    findings: list[str] = []
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # --- ExternalTicket path (correctness + quality) ---
    reg = call(
        "POST",
        ADAPTER,
        f"/api/v1/projects/{PROJECT}/connectors",
        body={
            "vendor": "local",
            "name": "smoke-local-tracker",
            "capabilities": ["tickets"],
            "auth_profile": "local",
            "trust_level": "local",
            "credential": "smoke",
            "status_map": {"Done": "done", "To Do": "open"},
            "reopen_policy": "allow_remote",
            "unknown_status_policy": "reject",
            "mapping_version": 2,
        },
        idem=f"reg-{RUN}",
    )
    expect(reg["_http_status"] == 200, "connector register failed")
    connector_id = reg["connector"]["id"]
    val = call(
        "POST",
        ADAPTER,
        f"/api/v1/projects/{PROJECT}/connectors/{connector_id}:validate",
        body={},
        idem=f"val-{RUN}",
    )
    expect(val["connector"]["status"] == "ready", "connector not ready")
    findings.append("connector ready")

    create_body = {
        "connector_id": connector_id,
        "title": f"Smoke ExternalTicket {RUN}",
        "department": "platform-engineering",
        "description_summary": "live smoke",
        "priority": "high",
        "labels": ["smoke", "ticketing"],
    }
    created = call(
        "POST",
        ADAPTER,
        f"/api/v1/projects/{PROJECT}/external-tickets",
        body=create_body,
        idem=f"create-{RUN}",
    )
    replay = call(
        "POST",
        ADAPTER,
        f"/api/v1/projects/{PROJECT}/external-tickets",
        body=create_body,
        idem=f"create-{RUN}",
    )
    ticket = created["ticket"]
    expect(created["_http_status"] == 200 and replay["ticket"]["id"] == ticket["id"], "idempotent create broken")
    expect(ticket["dispatch_status"] == "pending", "create should leave dispatch pending until handled")
    findings.append("external create+idempotency ok")

    # Same path as outbox TicketDispatchHandler: LocalTrackerAdapter.create_remote + record result.
    # Uses the live Postgres row created by the restarted HTTP service.
    import os

    os.environ["ASTLOOM_ADAPTER_SERVICE_DATABASE_URL"] = os.environ.get(
        "ASTLOOM_ADAPTER_SERVICE_DATABASE_URL"
    ) or "postgresql://astloom:astloom-local-dev-secret@127.0.0.1:32232/astloom"
    from adapter_service.bootstrap import build_container
    from adapter_service.core import Scope as AdapterScope

    container = build_container()
    try:
        dispatched_ticket = container.service.dispatch_external_ticket(
            AdapterScope(TENANT, WORKSPACE, PROJECT),
            "ticket-smoke",
            f"smoke-{RUN}",
            f"disp-{RUN}",
            ticket["id"],
        )
    finally:
        container.close()
    expect(dispatched_ticket.dispatch_status.value == "succeeded", "LocalTrackerAdapter create_remote failed")
    expect(bool(dispatched_ticket.external_ref), "dispatch did not set external_ref")
    expect(dispatched_ticket.version == ticket["version"] + 1, "version did not bump on dispatch")
    dispatched = call("GET", ADAPTER, f"/api/v1/projects/{PROJECT}/external-tickets/{ticket['id']}")
    expect(dispatched["ticket"]["dispatch_status"] == "succeeded", "HTTP get after dispatch mismatch")
    expect(dispatched["ticket"]["external_ref"] == dispatched_ticket.external_ref, "external_ref not durable")
    findings.append("LocalTrackerAdapter create_remote + durable HTTP read ok")

    # Concurrency conflict quality check
    try:
        call(
            "POST",
            ADAPTER,
            f"/api/v1/projects/{PROJECT}/external-tickets/{ticket['id']}:sync-status",
            body={
                "status": "done",
                "expected_version": 1,
                "external_updated_at": now,
                "source": "webhook",
            },
            idem=f"conflict-{RUN}",
        )
        raise Fail("expected version conflict")
    except Fail as exc:
        expect("409" in str(exc) or "version_conflict" in str(exc), f"wrong conflict: {exc}")
    findings.append("optimistic concurrency conflict ok")

    synced = call(
        "POST",
        ADAPTER,
        f"/api/v1/projects/{PROJECT}/external-tickets/{ticket['id']}:sync-status",
        body={
            "status": "Done",
            "expected_version": dispatched["ticket"]["version"],
            "external_updated_at": now,
            "source": "webhook",
            "reason": "smoke mapped Done",
        },
        idem=f"sync-{RUN}",
    )
    expect(synced["ticket"]["status"] == "done", "status_map Done->done failed")
    findings.append("status_map sync ok")

    listed = call(
        "GET",
        ADAPTER,
        f"/api/v1/projects/{PROJECT}/external-tickets?status=done&department=platform-engineering",
    )
    expect(any(item["id"] == ticket["id"] for item in listed.get("items", [])), "list filter missed ticket")
    got = call("GET", ADAPTER, f"/api/v1/projects/{PROJECT}/external-tickets/{ticket['id']}")
    expect(got["ticket"]["status"] == "done", "get item mismatch")
    findings.append("query list/get ok")

    pushed = call(
        "POST",
        ADAPTER,
        f"/api/v1/projects/{PROJECT}/external-tickets/{ticket['id']}:push-status",
        body={"expected_version": synced["ticket"]["version"], "status": "done"},
        idem=f"push-{RUN}",
    )
    expect(pushed["ticket"]["dispatch_status"] == "succeeded", "push-status failed")
    findings.append("push-status ok")

    # Cross-project isolation
    try:
        call("GET", ADAPTER, f"/api/v1/projects/other-{RUN}/external-tickets/{ticket['id']}")
        raise Fail("expected cross-project 404")
    except Fail as exc:
        expect("404" in str(exc) or "not_found" in str(exc), f"wrong isolation error: {exc}")
    findings.append("cross-project isolation ok")

    # --- AgentTicket path ---
    at = call(
        "POST",
        ORCH,
        f"/api/v1/projects/{PROJECT}/agent-tickets",
        body={"title": f"Smoke AgentTicket {RUN}", "agent_id": "agent-smoke", "task_id": f"task-{RUN}"},
        idem=f"atk-{RUN}",
    )
    expect(at["ticket"]["status"] == "assigned", "agent ticket create status")
    at_id = at["ticket"]["id"]
    claimed = call(
        "POST",
        ORCH,
        f"/api/v1/projects/{PROJECT}/agent-tickets/{at_id}:claim",
        body={"expected_version": 1},
        idem=f"atk-claim-{RUN}",
    )
    expect(claimed["ticket"]["status"] == "claimed", "claim failed")
    started = call(
        "POST",
        ORCH,
        f"/api/v1/projects/{PROJECT}/agent-tickets/{at_id}:start",
        body={"expected_version": 2},
        idem=f"atk-start-{RUN}",
    )
    expect(started["ticket"]["status"] == "in_progress", "start failed")
    findings.append("agent-ticket claim/start ok")

    print("LIVE_SMOKE_PASS")
    for item in findings:
        print(f"  - {item}")
    print(json.dumps({
        "project_id": PROJECT,
        "external_ticket_id": ticket["id"],
        "external_status": pushed["ticket"]["status"],
        "external_version": pushed["ticket"]["version"],
        "agent_ticket_id": at_id,
        "agent_status": started["ticket"]["status"],
        "adapter": ADAPTER,
        "orchestration": ORCH,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Fail as exc:
        print(f"LIVE_SMOKE_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
