"""GAP-T05: LiteLLMJudge with FakeLlmGateway — structured verdicts + fail-closed."""

from __future__ import annotations

import json

import pytest
from llm_gateway import FakeLlmGateway

from rule_engine_service.bootstrap import Settings, build_judge
from rule_engine_service.core import HeuristicJudge
from rule_engine_service.domain.enums import EvaluationMode, RuleState, Severity, Verdict
from rule_engine_service.domain.models import Rule, Scope
from rule_engine_service.litellm_judge import LiteLLMJudge


SCOPE = Scope("t", "w", "p")


def _rule(**extra) -> Rule:
    base = dict(
        id="rule_1",
        scope=SCOPE,
        actor_id="agent",
        correlation_id="corr",
        title="Require approval for auth changes",
        natural_language_rule="Production auth changes require human approval",
        severity=Severity.CRITICAL,
        owner="security",
        evaluation_mode=EvaluationMode.HYBRID,
        state=RuleState.ACTIVE,
        domain="security",
        examples=["changed auth middleware"],
        counterexamples=["docs-only edit"],
        match_tags=["security", "auth"],
        required_approval_role="security-approver",
        precedence=100,
        version=1,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    base.update(extra)
    return Rule(**base)


def _verdict(**overrides) -> str:
    payload = {
        "verdict": "escalate",
        "confidence": 0.95,
        "rationale": "Subject matches production auth change example",
        "matched_examples": ["changed auth middleware"],
        "missing_evidence": [],
        "recommended_action": "request_human_approval",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_litellm_judge_parses_structured_verdict_and_replay():
    gateway = FakeLlmGateway(canned=_verdict())
    judge = LiteLLMJudge(gateway)
    result = judge.judge(
        _rule(),
        {
            "subject_ref": "change-1",
            "summary": "Update production auth middleware",
            "change_type": "code",
            "tags": ["security", "auth", "production"],
            "paths": ["src/auth/middleware.py"],
            "evidence_refs": ["diff-1"],
        },
    )
    assert result.verdict == Verdict.ESCALATE
    assert result.confidence == pytest.approx(0.95)
    assert "auth" in result.rationale.lower() or "auth" in result.matched_examples[0]
    assert gateway.calls, "gateway must be invoked"
    assert gateway.calls[0].temperature == 0.0
    assert gateway.calls[0].response_format_json is True
    replay = result.replay_metadata
    assert replay["model_id"]
    assert replay["route_profile_id"]
    assert replay["route_profile_version"]
    assert replay["prompt_template_version"]
    assert replay["generation_params"]["temperature"] == 0.0
    assert replay["generation_params"]["response_format_json"] is True
    assert replay["generation_params"]["task_class"] == "rules.judge"
    assert replay["raw_structured_response"]["verdict"] == "escalate"


def test_litellm_judge_low_confidence_escalates_non_low_severity():
    gateway = FakeLlmGateway(canned=_verdict(verdict="allow", confidence=0.4))
    judge = LiteLLMJudge(gateway, low_confidence_threshold=0.7)
    result = judge.judge(_rule(severity=Severity.HIGH), {"summary": "x", "tags": []})
    assert result.verdict == Verdict.ESCALATE
    assert "low-confidence" in result.rationale


def test_litellm_judge_malformed_json_fail_closed():
    gateway = FakeLlmGateway(canned="not-json")
    judge = LiteLLMJudge(gateway)
    result = judge.judge(_rule(), {"summary": "x", "tags": []})
    assert result.verdict == Verdict.ESCALATE
    assert result.confidence == 0.0
    assert "non-JSON" in result.rationale or "schema" in result.rationale.lower()


def test_litellm_judge_schema_invalid_fail_closed():
    gateway = FakeLlmGateway(canned=json.dumps({"verdict": "allow"}))
    judge = LiteLLMJudge(gateway)
    result = judge.judge(_rule(), {"summary": "x", "tags": []})
    assert result.verdict == Verdict.ESCALATE
    assert "schema" in result.rationale.lower()


def test_build_judge_selects_heuristic_by_default(monkeypatch):
    monkeypatch.delenv("ASTLOOM_RULE_JUDGE", raising=False)
    settings = Settings(database_url="postgresql://localhost/ac", rule_judge="heuristic")
    assert isinstance(build_judge(settings), HeuristicJudge)


def test_build_judge_selects_litellm(monkeypatch):
    monkeypatch.setenv("ASTLOOM_RULE_JUDGE", "litellm")
    settings = Settings(database_url="postgresql://localhost/ac", rule_judge="litellm")
    judge = build_judge(settings)
    assert isinstance(judge, LiteLLMJudge)


def test_build_judge_rejects_unknown():
    settings = Settings(database_url="postgresql://localhost/ac", rule_judge="openai")
    with pytest.raises(RuntimeError, match="Unsupported ASTLOOM_RULE_JUDGE"):
        build_judge(settings)


def test_settings_from_environment_reads_rule_judge(monkeypatch):
    monkeypatch.setenv("ASTLOOM_RULE_ENGINE_DATABASE_URL", "postgresql://localhost/ac")
    monkeypatch.setenv("ASTLOOM_RULE_JUDGE", "LiteLLM")
    settings = Settings.from_environment()
    assert settings.rule_judge == "litellm"
