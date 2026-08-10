"""Unit tests for WorkerExecutor and Settings (integrator example worker)."""

from __future__ import annotations

import os

from integrator_worker_support import DEFAULT_WEBHOOK_SECRET, ensure_worker_import_path

ensure_worker_import_path()

from astloom_agent_sdk import AstloomExecutionTask  # noqa: E402
from worker.executor import WorkerExecutor  # noqa: E402
from worker.schemas import RoleOutput  # noqa: E402
from worker.settings import Settings  # noqa: E402


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("ASTLOOM_WEBHOOK_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("WORKER_LIVE_MODE", "0")
    monkeypatch.delenv("WORKER_USE_LLM", raising=False)
    settings = Settings.load()
    assert settings.shared_secret == "test-secret"
    assert settings.port == 32510
    assert settings.runtime_name == "langgraph-change-analyst"
    assert settings.use_llm is False


def test_settings_requires_secret(monkeypatch):
    monkeypatch.delenv("ASTLOOM_WEBHOOK_SHARED_SECRET", raising=False)
    monkeypatch.delenv("CHANGE_SOCIETY_WEBHOOK_AGENT_SECRET", raising=False)
    try:
        Settings.load()
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "SECRET" in str(exc)


def test_executor_change_analyst_offline_graph():
    os.environ["ASTLOOM_WEBHOOK_SHARED_SECRET"] = DEFAULT_WEBHOOK_SECRET
    os.environ["WORKER_LIVE_MODE"] = "0"
    executor = WorkerExecutor(Settings.load())
    task = AstloomExecutionTask(
        contract_version="1.0",
        ticket_id="ticket_unit",
        agent_id="agent_unit",
        role="change_analyst",
        system_prompt="sys",
        user_prompt="EVIDENCE:\n[ev_api_diff] taxIncluded OpenAPI mobile clients",
        output_schema={"title": "RoleOutput", "type": "object"},
        correlation_id="corr_unit",
    )
    output = executor.execute(task)
    validated = RoleOutput.model_validate(output)
    assert validated.risk_level in {"low", "medium", "high", "critical"}
    assert executor.last_duration_ms >= 0


def test_executor_rejects_other_roles_without_live_mode():
    os.environ["ASTLOOM_WEBHOOK_SHARED_SECRET"] = DEFAULT_WEBHOOK_SECRET
    os.environ["WORKER_LIVE_MODE"] = "0"
    executor = WorkerExecutor(Settings.load())
    task = AstloomExecutionTask(
        contract_version="1.0",
        ticket_id="ticket_bad",
        agent_id="agent_bad",
        role="policy_guardian",
        system_prompt="sys",
        user_prompt="user",
        output_schema={"title": "RoleOutput", "type": "object"},
        correlation_id="corr_bad",
    )
    try:
        executor.execute(task)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "WORKER_LIVE_MODE" in str(exc) or "live" in str(exc).lower()
