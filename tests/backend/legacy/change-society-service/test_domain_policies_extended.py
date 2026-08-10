from __future__ import annotations

from change_society.domain.models import AgentMessage, RiskLevel, Role, Scope
from change_society.domain.policies import (
    detect_scenario_negotiation_gate,
    detect_specialist_conflict,
    requires_human_approval,
)


def message(risk: RiskLevel, message_id: str = "msg_a") -> AgentMessage:
    scope = Scope("t", "w", "p")
    return AgentMessage(
        "1.0", message_id, "specialist_finding", scope, "run_1", "corr", None,
        Role.CHANGE_ANALYST, Role.COORDINATOR, "interpret_ambiguous_software_change", "ticket_1",
        "report", "completed", {"summary": "x", "policies": []}, ["ev_1"], [], 0.9, risk, [], [], "none", "now", "idem",
    )


def test_detect_scenario_negotiation_gate_when_policy_reflects_required_tags():
    change = message(RiskLevel.HIGH)
    policy = message(RiskLevel.HIGH, "msg_b")
    policy.payload["policies"] = ["revenue-impacting-change"]
    policy.payload["summary"] = "Revenue policy applies"
    conflict = detect_scenario_negotiation_gate(
        change, policy, "c_gate", ("revenue-impacting-change",), True,
    )
    assert conflict is not None
    assert conflict.topic == "scenario_negotiation_gate"


def test_detect_scenario_negotiation_gate_skips_when_not_required():
    change = message(RiskLevel.HIGH)
    policy = message(RiskLevel.HIGH, "msg_b")
    assert detect_scenario_negotiation_gate(change, policy, "c", ("revenue-impacting-change",), False) is None


def test_detect_scenario_negotiation_gate_skips_when_policy_silent():
    change = message(RiskLevel.HIGH)
    policy = message(RiskLevel.LOW, "msg_b")
    policy.payload["policies"] = []
    policy.payload["summary"] = "Policy clear with no matching tags"
    assert detect_scenario_negotiation_gate(change, policy, "c", ("revenue-impacting-change",), True) is None


def test_detect_specialist_conflict_returns_none_without_required_policy_overlap():
    change = message(RiskLevel.LOW)
    policy = message(RiskLevel.MEDIUM, "msg_b")
    policy.payload["policies"] = ["custom-tag"]
    assert detect_specialist_conflict(change, policy, "c", ("revenue-impacting-change",)) is None


def test_requires_human_approval_when_unresolved():
    assert requires_human_approval(RiskLevel.LOW, True, []) is True


def test_requires_human_approval_privacy_policy_tag():
    assert requires_human_approval(RiskLevel.LOW, False, ["privacy-sensitive-change"]) is True
