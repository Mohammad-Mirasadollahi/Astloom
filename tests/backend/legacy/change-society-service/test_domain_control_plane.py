from __future__ import annotations

from change_society.domain.control_plane import AgentState, AgentTicket, ManagedAgent, TicketState
from change_society.domain.models import ConflictError, Scope, ValidationError


def agent(state: AgentState = AgentState.ONLINE) -> ManagedAgent:
    return ManagedAgent(
        "agent_1", Scope("t", "w", "p"), "Worker", "demo", "model", ("cap_a",), state, "t1", "t1",
    )


def test_managed_agent_supports_only_online_capabilities():
    assert agent().supports("cap_a") is True
    assert agent().supports("missing") is False
    assert agent(AgentState.PAUSED).supports("cap_a") is False


def test_managed_agent_requires_identity_fields():
    try:
        ManagedAgent("", Scope("t", "w", "p"), "Worker", "demo", "model", ("cap",), AgentState.ONLINE, "t1", "t1")
        raise AssertionError("expected validation error")
    except ValidationError:
        pass


def test_ticket_transition_records_events_and_blocks_invalid_moves():
    ticket = AgentTicket(
        "ticket_1", Scope("t", "w", "p"), "run_1", "Analyze", "cap_a", {}, ("schema",), TicketState.CREATED,
        50, "actor", "corr", "t1", "t1",
    )
    ticket.transition(TicketState.ASSIGNED, "router", "t2", "evt_1")
    assert ticket.state == TicketState.ASSIGNED
    assert len(ticket.events) == 1
    try:
        ticket.transition(TicketState.COMPLETED, "actor", "t3", "evt_2")
        raise AssertionError("expected invalid ticket transition")
    except ConflictError as exc:
        assert "invalid ticket transition" in exc.message
