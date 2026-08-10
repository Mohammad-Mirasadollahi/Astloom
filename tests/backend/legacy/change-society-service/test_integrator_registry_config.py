"""Integrator managed-agents JSON and registry behavior."""

from __future__ import annotations

import json

from integrator_worker_support import INTEGRATOR_AGENTS_JSON, load_integrator_registry


def test_integrator_example_json_is_valid_and_has_webhook_change_analyst():
    data = load_integrator_registry()
    assert data["contract_version"] == "1.0"
    agents = {item["key"]: item for item in data["agents"]}
    assert "change-analyst" in agents
    change = agents["change-analyst"]
    assert change["adapter_type"] == "webhook"
    assert change["endpoint"] == "http://localhost:32510"
    assert "interpret_ambiguous_software_change" in change["capabilities"]
    assert change["role"] == "change_analyst"
    other_roles = [a for a in data["agents"] if a["key"] != "change-analyst"]
    assert all(a["adapter_type"] == "model" for a in other_roles)


def test_integrator_json_matches_bootstrap_loader_shape():
    """Container expects agents[] with key, adapter_type, capabilities, optional endpoint."""
    raw = json.loads(INTEGRATOR_AGENTS_JSON.read_text(encoding="utf-8"))
    for item in raw["agents"]:
        assert "key" in item and "adapter_type" in item and "capabilities" in item
        if item["adapter_type"] == "webhook":
            assert item.get("endpoint"), f"webhook agent {item['key']} must define endpoint"


def test_managed_agent_public_does_not_expose_endpoint():
    from change_society.application.control_plane import AgentControlPlane, AgentTemplate, CapabilityRouter
    from change_society.infrastructure.agent_adapters import ModelAgentAdapter, StaticAgentAdapterRegistry, WebhookAgentAdapter
    from change_society.infrastructure.control_plane_repositories import InMemoryControlPlaneRepository
    from change_society.infrastructure.fake_model import DeterministicModelClient
    from change_society.domain.models import Scope

    class FixedClock:
        def now(self):
            return "2026-07-12T00:00:00+00:00"

    class SequenceIds:
        n = 0

        def new(self, prefix: str) -> str:
            SequenceIds.n += 1
            return f"{prefix}_{SequenceIds.n}"

    template = AgentTemplate(
        "change-analyst",
        "External",
        "langgraph-worker",
        "webhook",
        ("interpret_ambiguous_software_change",),
        "change_analyst",
        "desc",
        "http://localhost:32510",
    )
    plane = AgentControlPlane(
        InMemoryControlPlaneRepository(),
        StaticAgentAdapterRegistry(
            {"model": ModelAgentAdapter(DeterministicModelClient()), "webhook": WebhookAgentAdapter("secret", 5)}
        ),
        CapabilityRouter(),
        FixedClock(),
        SequenceIds(),
        (template,),
    )
    agent = plane.ensure_agents(Scope("t", "w", "p"))[0]
    public = agent.public()
    assert "endpoint" not in public
    assert public["adapter_type"] == "webhook"
