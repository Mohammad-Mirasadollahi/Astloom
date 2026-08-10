from __future__ import annotations

import pytest

from change_society.application.control_plane import AgentControlPlane, AgentTemplate, CapabilityRouter
from change_society.domain.control_plane import AgentState
from change_society.domain.models import ConflictError, Scope
from change_society.infrastructure.agent_adapters import ModelAgentAdapter, StaticAgentAdapterRegistry
from change_society.infrastructure.control_plane_repositories import InMemoryControlPlaneRepository
from change_society.infrastructure.fake_model import DeterministicModelClient

from conftest import FixedClock, SequenceIds


def test_router_raises_when_no_capable_agent():
    router = CapabilityRouter()
    templates = (
        AgentTemplate("a", "Offline", "p", "model", ("only_capability",), "role_a", "d"),
    )
    control = AgentControlPlane(
        InMemoryControlPlaneRepository(),
        StaticAgentAdapterRegistry({"model": ModelAgentAdapter(DeterministicModelClient())}),
        router,
        FixedClock(),
        SequenceIds(),
        templates,
    )
    scope = Scope("t", "w", "p")
    agents = control.ensure_agents(scope)
    agents[0].state = AgentState.OFFLINE
    control.repository.save_agent(agents[0])
    with pytest.raises(ConflictError, match="no online agent"):
        control.create_ticket(scope, "run_1", "t", "missing_capability", {}, "actor", "corr")


def test_bootstrap_settings_qwen_role_tools_flags(monkeypatch):
    monkeypatch.setenv("CHANGE_SOCIETY_MODEL_PROVIDER", "fake")
    monkeypatch.setenv("CHANGE_SOCIETY_ENABLE_QWEN_ROLE_TOOLS", "0")
    monkeypatch.setenv("CHANGE_SOCIETY_QWEN_MAX_TOOL_ROUNDS", "5")
    from change_society.bootstrap.config import Settings

    settings = Settings.load()
    assert settings.enable_qwen_role_tools is False
    assert settings.qwen_max_tool_rounds == 5


def test_bootstrap_rejects_unsupported_store(monkeypatch):
    monkeypatch.setenv("CHANGE_SOCIETY_STORE", "redis")
    from change_society.bootstrap.config import Settings

    with pytest.raises(ValueError, match="unsupported"):
        Settings.load()
