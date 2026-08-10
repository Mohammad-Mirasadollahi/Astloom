from __future__ import annotations

import json

import httpx

from change_society.contracts.messages import RoleOutput
from change_society.domain.control_plane import ManagedAgent, AgentState
from change_society.domain.models import DependencyError, Scope
from change_society.infrastructure.agent_adapters import ModelAgentAdapter, StaticAgentAdapterRegistry, WebhookAgentAdapter
from change_society.infrastructure.fake_model import DeterministicModelClient


def test_static_registry_raises_for_unknown_adapter():
    registry = StaticAgentAdapterRegistry({"model": ModelAgentAdapter(DeterministicModelClient())})
    try:
        registry.get("missing")
        raise AssertionError("expected adapter not found")
    except DependencyError as exc:
        assert exc.code == "agent_adapter_not_found"


def test_webhook_adapter_executes_signed_request():
    seen = {}

    def handler(request):
        seen["signature"] = request.headers["X-Astloom-Signature"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"output": {
            "summary": "external", "risk_level": "medium", "findings": [], "impacts": [], "policies": [],
            "tasks": [], "evidence_refs": [], "assumptions": [], "unresolved_questions": [],
            "confidence": 0.8, "recommended_action": "review",
        }, "usage": {"input_tokens": 4, "completion_tokens": 6}, "duration_ms": 12, "runtime": "external", "execution_id": "ext:1"})

    agent = ManagedAgent(
        "agent_1", Scope("t", "w", "p"), "Webhook Worker", "external", "webhook", ("cap",), AgentState.ONLINE,
        "t1", "t1", endpoint="https://worker.example", role="worker",
    )
    adapter = WebhookAgentAdapter("secret", 5, httpx.Client(transport=httpx.MockTransport(handler)))
    from change_society.contracts.agent_adapter import AgentExecutionRequest

    result = adapter.execute(agent, AgentExecutionRequest(
        "ticket_1", "agent_1", "worker", "system", "user", RoleOutput, "corr",
    ))
    assert result.payload["summary"] == "external"
    assert seen["body"]["ticket_id"] == "ticket_1"
    assert len(seen["signature"]) == 64


def test_webhook_adapter_maps_qwen_auth_failure():
    def handler(_request):
        return httpx.Response(
            502,
            json={"detail": {"code": "qwen_authentication_failed", "message": "Qwen API rejected the API key (HTTP 401)."}},
        )

    agent = ManagedAgent(
        "agent_1", Scope("t", "w", "p"), "Webhook Worker", "external", "webhook", ("cap",), AgentState.ONLINE,
        "t1", "t1", endpoint="https://worker.example", role="worker",
    )
    adapter = WebhookAgentAdapter("secret", 5, httpx.Client(transport=httpx.MockTransport(handler)))
    from change_society.contracts.agent_adapter import AgentExecutionRequest

    try:
        adapter.execute(agent, AgentExecutionRequest(
            "ticket_1", "agent_1", "worker", "system", "user", RoleOutput, "corr",
        ))
        raise AssertionError("expected dependency error")
    except DependencyError as exc:
        assert exc.code == "qwen_authentication_failed"
        assert "Settings" in exc.message
