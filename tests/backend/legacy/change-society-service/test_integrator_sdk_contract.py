"""AstloomExecutionTask parsing (integrator SDK contract)."""

from __future__ import annotations

import pytest

from astloom_agent_sdk import AstloomExecutionTask, SignatureError, SignedWebhookWorker


def test_execution_task_parse_requires_v1_fields():
    task = AstloomExecutionTask.parse(
        {
            "contract_version": "1.0",
            "ticket_id": "t1",
            "agent_id": "a1",
            "role": "change_analyst",
            "system_prompt": "s",
            "user_prompt": "u",
            "output_schema": {"title": "RoleOutput"},
            "correlation_id": "c1",
        }
    )
    assert task.ticket_id == "t1"
    assert task.role == "change_analyst"


def test_execution_task_rejects_unsupported_contract_version():
    with pytest.raises(ValueError, match="unsupported"):
        AstloomExecutionTask.parse(
            {
                "contract_version": "2.0",
                "ticket_id": "t1",
                "agent_id": "a1",
                "role": "change_analyst",
                "system_prompt": "s",
                "user_prompt": "u",
                "output_schema": {},
                "correlation_id": "c1",
            }
        )


def test_signed_webhook_worker_rejects_bad_signature():
    worker = SignedWebhookWorker("secret", lambda task: {"summary": "ok"})
    with pytest.raises(SignatureError):
        worker.handle(b"{}", "not-a-valid-signature")
