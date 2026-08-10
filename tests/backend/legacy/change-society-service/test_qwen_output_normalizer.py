from __future__ import annotations

import pytest
from pydantic import ValidationError

from change_society.contracts.messages import ContextOutput, JudgeOutput, RoleOutput
from change_society.infrastructure.qwen_output_normalizer import extract_json_object, normalize_model_payload, validate_normalized_payload


def test_extract_json_object_strips_markdown_fence():
    parsed = extract_json_object('```json\n{"summary":"ok text","risk_level":"low"}\n```')
    assert parsed["risk_level"] == "low"


def test_normalize_role_output_coerces_confidence_and_strips_extra_keys():
    raw = {
        "summary": "x",
        "risk_level": "HIGH",
        "confidence": 92,
        "recommended_action": "ok",
        "unexpected": True,
    }
    normalized = normalize_model_payload(raw, RoleOutput)
    validated = RoleOutput.model_validate(normalized)
    assert validated.risk_level == "high"
    assert validated.confidence == 0.92
    assert validated.summary == "Evidence-backed specialist analysis."


def test_normalize_context_output_fills_included_evidence():
    raw = {
        "summary": "Context bundle ready",
        "risk_level": "medium",
        "confidence": 0.8,
        "recommended_action": "Proceed",
        "evidence_refs": ["ev_a", "ev_b"],
    }
    validated = validate_normalized_payload(raw, ContextOutput)
    assert validated.included_evidence == ["ev_a", "ev_b"]


def test_normalize_judge_output_maps_invalid_verdict():
    raw = {"verdict": "approve", "final_risk_level": "high", "confidence": 95}
    validated = validate_normalized_payload(raw, JudgeOutput)
    assert validated.verdict == "accept_high_risk"
    assert validated.confidence == 0.95
