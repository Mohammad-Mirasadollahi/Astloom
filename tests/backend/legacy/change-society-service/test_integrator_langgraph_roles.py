"""LangGraph role registry (SDK-aligned task envelope)."""

from __future__ import annotations

import os

from integrator_worker_support import DEFAULT_WEBHOOK_SECRET, ensure_worker_import_path

ensure_worker_import_path()

from astloom_agent_sdk import AstloomExecutionTask  # noqa: E402
from worker.graph.society_role_graph import RoleGraphRegistry, task_to_graph_state  # noqa: E402
from worker.settings import Settings  # noqa: E402


def test_task_to_graph_state_includes_sdk_envelope():
    os.environ["ASTLOOM_WEBHOOK_SHARED_SECRET"] = DEFAULT_WEBHOOK_SECRET
    os.environ["WORKER_LIVE_MODE"] = "0"
    task = AstloomExecutionTask(
        contract_version="1.0",
        ticket_id="t1",
        agent_id="a1",
        role="change_analyst",
        system_prompt="sys",
        user_prompt="user",
        output_schema={"title": "RoleOutput"},
        correlation_id="c1",
    )
    state = task_to_graph_state(task)
    assert state["astloom_envelope"]["astloom"]["ticket_id"] == "t1"
    assert "messages" in state["astloom_envelope"]


def test_change_analyst_offline_langgraph_pipeline():
    os.environ["ASTLOOM_WEBHOOK_SHARED_SECRET"] = DEFAULT_WEBHOOK_SECRET
    os.environ["WORKER_LIVE_MODE"] = "0"
    registry = RoleGraphRegistry(Settings.load())
    task = AstloomExecutionTask(
        contract_version="1.0",
        ticket_id="t2",
        agent_id="a2",
        role="change_analyst",
        system_prompt="sys",
        user_prompt="EVIDENCE:\n[ev_api_diff] taxIncluded OpenAPI",
        output_schema={"title": "RoleOutput"},
        correlation_id="c2",
    )
    output = registry.invoke(task)
    assert output["risk_level"] in {"low", "medium", "high", "critical"}
