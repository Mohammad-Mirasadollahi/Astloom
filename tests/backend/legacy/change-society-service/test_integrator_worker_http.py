"""HTTP contract tests for the reference external change-analyst worker."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from integrator_worker_support import DEFAULT_WEBHOOK_SECRET, ensure_worker_import_path

ensure_worker_import_path()

from worker.main import create_app  # noqa: E402
from worker.settings import Settings  # noqa: E402


@pytest.fixture
def client():
    return TestClient(create_app(Settings.load()))


def _signed(body: dict, secret: str = DEFAULT_WEBHOOK_SECRET) -> tuple[bytes, str]:
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), encoded, hashlib.sha256).hexdigest()
    return encoded, signature


def test_ready_and_health(client):
    assert client.get("/health").json()["status"] == "ok"
    ready = client.get("/ready").json()
    assert ready["status"] == "ok"
    assert ready["runtime"] == "langgraph-change-analyst"


def test_execute_rejects_invalid_signature(client):
    body = {
        "contract_version": "1.0",
        "ticket_id": "t1",
        "agent_id": "a1",
        "role": "change_analyst",
        "system_prompt": "s",
        "user_prompt": "u",
        "output_schema": {"title": "RoleOutput"},
        "correlation_id": "c1",
    }
    payload, _ = _signed(body)
    response = client.post(
        "/api/v1/agent-tickets:execute",
        content=payload,
        headers={"Content-Type": "application/json", "X-Astloom-Signature": "deadbeef"},
    )
    assert response.status_code == 401


def test_execute_change_analyst_returns_runtime_and_duration(client):
    body = {
        "contract_version": "1.0",
        "ticket_id": "ticket_demo",
        "agent_id": "agent_demo",
        "role": "change_analyst",
        "system_prompt": "Return JSON RoleOutput",
        "user_prompt": "EVIDENCE:\n[ev_api_diff] removed taxIncluded\n[ev_openapi] taxIncluded required",
        "output_schema": {"title": "RoleOutput", "type": "object"},
        "correlation_id": "corr_demo",
    }
    payload, signature = _signed(body)
    response = client.post(
        "/api/v1/agent-tickets:execute",
        content=payload,
        headers={"Content-Type": "application/json", "X-Astloom-Signature": signature},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["runtime"] == "langgraph-change-analyst"
    assert data["duration_ms"] >= 0
    assert "summary" in data["output"]


def test_execute_rebuttal_high_risk(client):
    body = {
        "contract_version": "1.0",
        "ticket_id": "ticket_rebuttal",
        "agent_id": "agent_demo",
        "role": "change_analyst",
        "system_prompt": "Return JSON RoleOutput",
        "user_prompt": "ONE BOUNDED REBUTTAL\nEVIDENCE:\n[ev_api_diff] taxIncluded OpenAPI",
        "output_schema": {"title": "RoleOutput", "type": "object"},
        "correlation_id": "corr_rebuttal",
    }
    payload, signature = _signed(body)
    response = client.post(
        "/api/v1/agent-tickets:execute",
        content=payload,
        headers={"Content-Type": "application/json", "X-Astloom-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json()["output"]["risk_level"] == "high"
