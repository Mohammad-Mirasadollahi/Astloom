from __future__ import annotations

import pytest

from change_society.contracts.messages import ContextOutput, JudgeOutput, RoleOutput, UniversalAgentJson


def test_context_output_requires_included_evidence_lists():
    payload = {
        "summary": "ctx", "risk_level": "medium", "findings": [], "impacts": [], "policies": [],
        "tasks": [], "evidence_refs": ["ev_1"], "assumptions": [], "unresolved_questions": [],
        "confidence": 0.8, "recommended_action": "continue",
        "included_evidence": ["ev_1"], "excluded_evidence": [],
    }
    parsed = ContextOutput.model_validate(payload)
    assert parsed.included_evidence == ["ev_1"]


def test_judge_output_validates_verdict_enum():
    payload = {
        "verdict": "accept_high_risk", "final_risk_level": "high",
        "rationale": "Evidence supports guarded approval.", "accepted_evidence_refs": ["ev_1"],
        "rejected_position": "Low risk claim", "required_approvers": ["product"], "confidence": 0.9,
    }
    assert JudgeOutput.model_validate(payload).verdict == "accept_high_risk"


def test_universal_agent_json_rejects_invalid_message_type():
    with pytest.raises(Exception):
        UniversalAgentJson.model_validate({
            "protocol_version": "1.0", "message_id": "m1", "message_type": "invalid_type",
            "tenant_id": "t", "workspace_id": "w", "project_id": "p", "run_id": "r",
            "correlation_id": "c", "sender_role": "a", "recipient_role": "b",
            "capability": "cap", "task_ref": "t1", "intent": "i", "status": "completed",
            "payload": {}, "evidence_refs": [], "assumptions": [], "confidence": 0.5,
            "risk_level": "low", "conflicts": [], "unresolved_questions": [],
            "requested_next_action": "none", "created_at": "now", "idempotency_key": "k",
        })


def test_role_output_confidence_bounds():
    base = {
        "summary": "Valid summary text", "risk_level": "low", "findings": [], "impacts": [], "policies": [],
        "tasks": [], "evidence_refs": [], "assumptions": [], "unresolved_questions": [],
        "recommended_action": "Proceed with review.",
    }
    RoleOutput.model_validate({**base, "confidence": 0.0})
    RoleOutput.model_validate({**base, "confidence": 1.0})
    with pytest.raises(Exception):
        RoleOutput.model_validate({**base, "confidence": 1.5})
