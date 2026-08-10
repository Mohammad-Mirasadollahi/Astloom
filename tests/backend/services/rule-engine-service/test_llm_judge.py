"""GAP-T05 LiteLLMJudge determinism tests (frozen gateway, schema, replay)."""

from __future__ import annotations

import json
from pathlib import Path

from llm_gateway import FakeLlmGateway, clear_routing_profile_cache
from rule_engine_service.bootstrap import Settings, build_judge
from rule_engine_service.domain.enums import EvaluationMode, RuleState, Severity, Verdict
from rule_engine_service.domain.judge import HeuristicJudge
from rule_engine_service.domain.models import Rule, Scope
from rule_engine_service.litellm_judge import PROMPT_TEMPLATE_VERSION, LiteLLMJudge

SCHEMA = (
    Path(__file__).resolve().parents[4]
    / "backend"
    / "configs"
    / "schemas"
    / "llm-judge-verdict.schema.json"
)


def _rule() -> Rule:
    return Rule(
        "rule-1",
        Scope("t", "w", "p"),
        "agent",
        "corr",
        "Block unsafe auth changes",
        "Production authentication changes require human approval",
        Severity.HIGH,
        "security-lead",
        EvaluationMode.SEMANTIC,
        RuleState.ACTIVE,
        "security",
        ["changed auth middleware without approval"],
        ["docs-only edit"],
        ["security", "auth"],
        "security-approver",
        200,
        1,
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00Z",
    )


def _subject() -> dict:
    return {
        "subject_ref": "change-auth-1",
        "summary": "Update production auth middleware",
        "change_type": "code",
        "tags": ["security", "auth", "ambiguous"],
        "paths": ["src/auth/middleware.py"],
        "evidence_refs": ["diff-1"],
    }


def _valid_verdict(**overrides) -> str:
    payload = {
        "verdict": "block",
        "confidence": 0.92,
        "rationale": "Auth middleware change matches sensitive policy examples",
        "matched_examples": ["changed auth middleware without approval"],
        "missing_evidence": [],
        "recommended_action": "request_human_approval",
    }
    payload.update(overrides)
    return json.dumps(payload)


def setup_function() -> None:
    clear_routing_profile_cache()


def teardown_function() -> None:
    clear_routing_profile_cache()


def test_frozen_gateway_returns_structured_verdict_and_replay_metadata():
    gateway = FakeLlmGateway(canned=_valid_verdict())
    judge = LiteLLMJudge(gateway, schema_path=SCHEMA)
    result = judge.judge(_rule(), _subject())

    assert result.verdict == Verdict.BLOCK
    assert result.confidence == 0.92
    assert "Auth middleware" in result.rationale
    assert result.matched_examples == ["changed auth middleware without approval"]

    replay = result.replay_metadata
    assert replay["model_id"]
    assert replay["route_profile_id"]
    assert replay["route_profile_version"]
    assert replay["prompt_template_version"] == PROMPT_TEMPLATE_VERSION
    assert replay["generation_params"]["temperature"] == 0.0
    assert replay["generation_params"]["response_format_json"] is True
    assert replay["generation_params"]["task_class"] == "rules.judge"
    assert replay["raw_structured_response"]["verdict"] == "block"

    assert len(gateway.calls) == 1
    assert gateway.calls[0].temperature == 0.0
    assert gateway.calls[0].response_format_json is True


def test_malformed_output_escalates_fail_closed():
    gateway = FakeLlmGateway(canned="not-json{{{")
    judge = LiteLLMJudge(gateway, schema_path=SCHEMA)
    result = judge.judge(_rule(), _subject())

    assert result.verdict == Verdict.ESCALATE
    assert result.confidence == 0.0
    assert "non-JSON" in result.rationale
    assert result.replay_metadata["raw_structured_response"]["malformed"] is True


def test_schema_invalid_output_escalates():
    gateway = FakeLlmGateway(canned=json.dumps({"verdict": "allow"}))
    judge = LiteLLMJudge(gateway, schema_path=SCHEMA)
    result = judge.judge(_rule(), _subject())

    assert result.verdict == Verdict.ESCALATE
    assert "schema validation failed" in result.rationale
    assert "raw_structured_response" in result.replay_metadata


def test_low_confidence_escalates_instead_of_allow():
    gateway = FakeLlmGateway(canned=_valid_verdict(verdict="allow", confidence=0.41))
    judge = LiteLLMJudge(gateway, schema_path=SCHEMA, low_confidence_threshold=0.7)
    result = judge.judge(_rule(), _subject())

    assert result.verdict == Verdict.ESCALATE
    assert result.confidence == 0.41
    assert "low-confidence escalation" in result.rationale
    assert result.replay_metadata["raw_structured_response"]["confidence"] == 0.41


def test_bootstrap_selects_judge_from_settings():
    assert isinstance(build_judge(Settings(database_url="postgresql://x", rule_judge="heuristic")), HeuristicJudge)
    assert isinstance(build_judge(Settings(database_url="postgresql://x", rule_judge="litellm")), LiteLLMJudge)


def test_evaluate_attaches_judge_replay_on_evaluation():
    from rule_engine_service.application.service import RuleEngineService
    from rule_engine_service.testing import InMemoryStore

    gateway = FakeLlmGateway(canned=_valid_verdict())
    service = RuleEngineService(InMemoryStore(), LiteLLMJudge(gateway, schema_path=SCHEMA))
    service.create_rule(
        Scope("t", "w", "p"),
        "agent",
        "corr",
        "rule-key",
        {
            "title": "Block unsafe auth changes",
            "natural_language_rule": "Production authentication changes require human approval",
            "severity": "high",
            "owner": "security-lead",
            "evaluation_mode": "semantic",
            "domain": "security",
            "match_tags": ["security", "auth"],
            "examples": ["changed auth middleware without approval"],
        },
    )
    result = service.evaluate_rules(
        Scope("t", "w", "p"),
        "agent",
        "corr",
        "eval-1",
        _subject(),
    )
    evaluation = result["evaluations"][0]
    assert evaluation["used_llm"] is True
    assert evaluation["judge_replay"]["prompt_template_version"] == PROMPT_TEMPLATE_VERSION
    assert evaluation["judge_replay"]["raw_structured_response"]["verdict"] == "block"
