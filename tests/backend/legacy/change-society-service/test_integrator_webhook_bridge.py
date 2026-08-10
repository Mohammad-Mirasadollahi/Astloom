"""WebhookAgentAdapter ↔ reference worker app (integrator bridge unit test)."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from change_society.contracts.agent_adapter import AgentExecutionRequest
from change_society.contracts.messages import RoleOutput
from change_society.domain.control_plane import AgentState, ManagedAgent
from change_society.domain.models import Scope
from change_society.infrastructure.agent_adapters import WebhookAgentAdapter

from integrator_worker_support import DEFAULT_WEBHOOK_SECRET, ensure_worker_import_path

ensure_worker_import_path()

from worker.main import create_app  # noqa: E402
from worker.settings import Settings  # noqa: E402


def _httpx_client_for_worker_app() -> httpx.Client:
    """Sync httpx client backed by FastAPI TestClient (matches WebhookAgentAdapter usage)."""
    test_client = TestClient(create_app(Settings.load()))

    def handler(request: httpx.Request) -> httpx.Response:
        response = test_client.request(
            request.method,
            request.url.path,
            content=request.content,
            headers=dict(request.headers),
        )
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return httpx.Response(response.status_code, json=response.json(), headers=response.headers)
        return httpx.Response(response.status_code, content=response.content, headers=response.headers)

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://worker.test")


def _managed_webhook_agent() -> ManagedAgent:
    return ManagedAgent(
        "agent_ext",
        Scope("t", "w", "p"),
        "External Change Analyst",
        "langgraph-worker",
        "webhook",
        ("interpret_ambiguous_software_change",),
        AgentState.ONLINE,
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00:00+00:00",
        endpoint="http://worker.test",
        role="change_analyst",
    )


def test_webhook_adapter_calls_reference_worker():
    adapter = WebhookAgentAdapter(DEFAULT_WEBHOOK_SECRET, 10.0, _httpx_client_for_worker_app())
    request = AgentExecutionRequest(
        "ticket_bridge",
        "agent_ext",
        "change_analyst",
        "You are the change analyst.",
        "REQUEST:\nCheckout refactor\nEVIDENCE:\n[ev_api_diff] taxIncluded OpenAPI",
        RoleOutput,
        "corr_bridge",
    )
    result = adapter.execute(_managed_webhook_agent(), request)
    assert result.runtime == "langgraph-change-analyst"
    assert result.payload["risk_level"] in {"low", "medium", "high", "critical"}
    assert result.external_execution_id == "external:ticket_bridge"


def test_webhook_adapter_health_uses_worker_ready():
    adapter = WebhookAgentAdapter(DEFAULT_WEBHOOK_SECRET, 10.0, _httpx_client_for_worker_app())
    health = adapter.health(_managed_webhook_agent())
    assert health["ready"] is True
