from __future__ import annotations

import pytest
from pydantic import ValidationError

from change_society.contracts.messages import RoleOutput, UniversalAgentJson


def test_role_output_rejects_extra_fields():
    with pytest.raises(ValidationError):
        RoleOutput.model_validate({
            "summary": "ok", "risk_level": "low", "confidence": 0.5, "recommended_action": "review", "unexpected": True,
        })


def test_universal_agent_json_requires_non_blank_scope_fields():
    with pytest.raises(ValidationError):
        UniversalAgentJson.model_validate({
            "protocol_version": "1.0", "message_id": "msg_1", "message_type": "task_assignment",
            "tenant_id": " ", "workspace_id": "w", "project_id": "p", "run_id": "run", "correlation_id": "corr",
            "sender_role": "coordinator", "recipient_role": "worker", "capability": "cap", "task_ref": "t1",
            "intent": "assign", "status": "assigned", "payload": {}, "confidence": 1.0, "risk_level": "low",
            "requested_next_action": "complete", "created_at": "now", "idempotency_key": "idem",
        })
