from __future__ import annotations

from change_society.application.control_plane import AgentControlPlane, AgentTemplate, CapabilityRouter
from change_society.contracts.messages import RoleOutput
from change_society.domain.control_plane import AgentState, ManagedAgent
from change_society.domain.models import ConflictError, Scope
from change_society.infrastructure.agent_adapters import ModelAgentAdapter, StaticAgentAdapterRegistry
from change_society.infrastructure.control_plane_repositories import InMemoryControlPlaneRepository
from change_society.infrastructure.fake_model import DeterministicModelClient


class FixedClock:
    def __init__(self) -> None:
        self.value = 0

    def now(self) -> str:
        self.value += 1
        return f"2026-07-12T00:00:{self.value:02d}+00:00"


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def new(self, prefix: str) -> str:
        self.value += 1
        return f"{prefix}_{self.value}"


SCOPE = Scope("tenant", "workspace", "project")
TEMPLATES = (
    AgentTemplate("a", "Agent A", "demo", "model", ("cap_a",), "role_a", "first"),
    AgentTemplate("b", "Agent B", "demo", "model", ("cap_a",), "role_b", "second"),
)


def make_plane() -> AgentControlPlane:
    return AgentControlPlane(
        InMemoryControlPlaneRepository(),
        StaticAgentAdapterRegistry({"model": ModelAgentAdapter(DeterministicModelClient())}),
        CapabilityRouter(),
        FixedClock(),
        SequenceIds(),
        TEMPLATES,
    )


def test_capability_router_prefers_lowest_active_load():
    router = CapabilityRouter()
    heavy = ManagedAgent("agent_heavy", SCOPE, "Heavy", "demo", "model", ("cap_a",), AgentState.ONLINE, "t1", "t1", active_ticket_count=5)
    light = ManagedAgent("agent_light", SCOPE, "Light", "demo", "model", ("cap_a",), AgentState.ONLINE, "t1", "t1", active_ticket_count=1)
    selected = router.select([heavy, light], "cap_a")
    assert selected.agent_id == "agent_light"


def test_ensure_agents_registers_templates_once():
    plane = make_plane()
    first = plane.ensure_agents(SCOPE)
    second = plane.ensure_agents(SCOPE)
    assert len(first) == 2
    assert {agent.name for agent in second} == {"Agent A", "Agent B"}


def test_create_ticket_executes_full_lifecycle():
    plane = make_plane()
    ticket = plane.create_ticket(SCOPE, "run_1", "Analyze", "cap_a", {"request": "x"}, "actor", "corr")
    result = plane.execute_ticket(ticket, "system", "user", RoleOutput)
    assert result.payload["risk_level"] in {"low", "medium", "high", "critical"}
    persisted = plane.get_ticket(SCOPE, ticket.ticket_id)
    assert persisted.state.value == "completed"
    assert persisted.execution_metrics["input_tokens"] > 0


def test_heartbeat_rejects_stale_agent_version():
    plane = make_plane()
    agent = plane.ensure_agents(SCOPE)[0]
    try:
        plane.heartbeat(SCOPE, agent.agent_id, True, expected_version=agent.version + 5)
        raise AssertionError("expected stale version conflict")
    except ConflictError as exc:
        assert "stale" in exc.message


def test_set_agent_state_can_revoke_agent():
    plane = make_plane()
    agent = plane.ensure_agents(SCOPE)[0]
    revoked = plane.set_agent_state(SCOPE, agent.agent_id, AgentState.REVOKED, agent.version)
    assert revoked.state == AgentState.REVOKED
