from __future__ import annotations

from change_society.domain.models import AgentMessage, ConflictError, RiskLevel, Role, RunState, Scope, SocietyRun
from change_society.domain.policies import detect_risk_conflict, detect_specialist_conflict, requires_human_approval, stable_digest


def message(risk: RiskLevel, message_id: str = "msg_a") -> AgentMessage:
    scope = Scope("t", "w", "p")
    return AgentMessage(
        "1.0", message_id, "specialist_finding", scope, "run_1", "corr", None,
        Role.CHANGE_ANALYST, Role.COORDINATOR, "interpret_ambiguous_software_change", "ticket_1",
        "report", "completed", {"summary": "x"}, ["ev_1"], [], 0.9, risk, [], [], "none", "now", "idem",
    )


def test_stable_digest_is_order_insensitive():
    assert stable_digest({"b": 2, "a": 1}) == stable_digest({"a": 1, "b": 2})
    assert stable_digest({"scenario_id": "pricing-refactor", "request_text": "hello"}) != stable_digest(
        {"scenario_id": "pricing-refactor", "request_text": "other"},
    )


def test_detect_risk_conflict_requires_material_disagreement():
    assert detect_risk_conflict(message(RiskLevel.LOW), message(RiskLevel.MEDIUM, "msg_b"), "c_1") is None
    conflict = detect_risk_conflict(message(RiskLevel.LOW), message(RiskLevel.HIGH, "msg_b"), "c_1")
    assert conflict is not None
    assert conflict.topic == "risk_level"
    assert conflict.claim_a_risk == RiskLevel.LOW
    assert conflict.claim_b_risk == RiskLevel.HIGH


def test_detect_specialist_conflict_when_required_policy_tags_and_risk_gap():
    change = message(RiskLevel.MEDIUM)
    change.payload["recommended_action"] = "Proceed with refactor."
    policy = message(RiskLevel.HIGH, "msg_b")
    policy.payload["policies"] = ["revenue-impacting-change"]
    policy.payload["recommended_action"] = "Escalate for Product and Finance approval."
    conflict = detect_specialist_conflict(change, policy, "c_2", ("revenue-impacting-change",))
    assert conflict is not None
    assert conflict.topic == "required_policy_risk_gap"


def test_detect_specialist_conflict_on_action_disagreement_at_same_risk():
    change = message(RiskLevel.HIGH)
    change.payload["policies"] = ["revenue-impacting-change"]
    change.payload["recommended_action"] = "Safe to merge after tests."
    policy = message(RiskLevel.HIGH, "msg_b")
    policy.payload["policies"] = ["revenue-impacting-change"]
    policy.payload["recommended_action"] = "Escalate for human approval."
    conflict = detect_specialist_conflict(change, policy, "c_3", ("revenue-impacting-change",))
    assert conflict is not None
    assert conflict.topic == "recommended_action"


def test_detect_specialist_conflict_when_change_omits_required_policy_tags():
    change = message(RiskLevel.HIGH)
    change.payload["policies"] = []
    change.payload["recommended_action"] = "Escalate for approval."
    policy = message(RiskLevel.HIGH, "msg_b")
    policy.payload["policies"] = ["revenue-impacting-change"]
    policy.payload["recommended_action"] = "Escalate for Product and Finance approval."
    conflict = detect_specialist_conflict(change, policy, "c_4", ("revenue-impacting-change",))
    assert conflict is not None
    assert conflict.topic == "policy_tag_asymmetry"


def test_requires_human_approval_for_high_risk_and_protected_policies():
    assert requires_human_approval(RiskLevel.LOW, False, []) is False
    assert requires_human_approval(RiskLevel.HIGH, False, []) is True
    assert requires_human_approval(RiskLevel.MEDIUM, True, []) is True
    assert requires_human_approval(RiskLevel.LOW, False, ["security-sensitive-change"]) is True


def test_society_run_rejects_invalid_transition():
    run = SocietyRun("run_1", Scope("t", "w", "p"), "actor", "corr", "request", "pricing-refactor", RunState.ACCEPTED, "t1", "t1")
    run.transition(RunState.GATHERING_CONTEXT, "t2")
    try:
        run.transition(RunState.COMPLETED, "t3")
        raise AssertionError("expected invalid transition")
    except ConflictError as exc:
        assert "invalid run transition" in exc.message
