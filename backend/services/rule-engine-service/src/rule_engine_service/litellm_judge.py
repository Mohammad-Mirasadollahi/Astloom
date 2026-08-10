"""
Module contract: LiteLLM Judge adapter (trust boundary).
Role: Judge protocol → LiteLLM gateway with temperature 0 + JSON object mode.
SoT: verdict schema under backend/configs/schemas/llm-judge-verdict.schema.json;
     operating standard docs/04-rule-engine-orchestration/11-llm-judge-operating-standard.md.
Allowed failure: malformed/schema-invalid/gateway errors and low confidence → escalate (fail-closed).
Forbidden: inventing evidence; returning allow on invalid JSON; non-zero temperature.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm_gateway import (
    ChatMessage,
    CompletionRequest,
    LlmGateway,
    load_routing_profile,
    resolve_route,
)

from .domain.enums import Severity, Verdict
from .domain.models import JudgeResult, Rule

PROMPT_TEMPLATE_VERSION = "llm-judge-prompt-v1"
DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.7
_TASK_CLASS = "rules.judge"

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4] / "configs" / "schemas" / "llm-judge-verdict.schema.json"
)


def _severity_risk(severity: Severity) -> str:
    if severity in {Severity.HIGH, Severity.CRITICAL}:
        return "high"
    if severity == Severity.MEDIUM:
        return "medium"
    return "low"


def _load_schema(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"LLM judge schema must be an object: {path}")
    return data


def _validate_verdict(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    import jsonschema

    jsonschema.Draft202012Validator(schema).validate(payload)


class LiteLLMJudge:
    """LLM-backed Judge adapter — structured JSON only; HeuristicJudge remains the default."""

    def __init__(
        self,
        gateway: LlmGateway,
        *,
        schema_path: Path | None = None,
        low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
        prompt_template_version: str = PROMPT_TEMPLATE_VERSION,
    ) -> None:
        self.gateway = gateway
        self.schema_path = schema_path or _SCHEMA_PATH
        self.schema = _load_schema(self.schema_path)
        self.low_confidence_threshold = float(low_confidence_threshold)
        self.prompt_template_version = prompt_template_version

    def judge(self, rule: Rule, subject: dict[str, Any]) -> JudgeResult:
        risk = _severity_risk(rule.severity)
        route = resolve_route(_TASK_CLASS, risk_level=risk)
        profile = load_routing_profile()
        generation_params = {
            "temperature": 0.0,
            "max_tokens": route.max_tokens,
            "response_format_json": True,
            "task_class": _TASK_CLASS,
            "risk_level": route.risk_level,
        }
        request = CompletionRequest(
            messages=(
                ChatMessage(
                    "system",
                    (
                        "You are the Astloom LLM Judge. Return one JSON object only. "
                        "Do not invent evidence. Use only supplied policy and subject facts."
                    ),
                ),
                ChatMessage("user", self._prompt_body(rule, subject)),
            ),
            model=route.primary_model or None,
            temperature=0.0,
            max_tokens=route.max_tokens,
            response_format_json=True,
            reasoning_enabled=False,
        )

        try:
            completion = self.gateway.complete(request)
        except Exception as exc:  # noqa: BLE001 — fail-closed at trust boundary
            return self._escalate(
                f"LLM judge gateway failure: {type(exc).__name__}",
                replay={
                    "model_id": route.primary_model or "",
                    "route_profile_id": str(profile.get("profile_id") or route.profile_id),
                    "route_profile_version": str(profile.get("version") or ""),
                    "prompt_template_version": self.prompt_template_version,
                    "generation_params": generation_params,
                    "raw_structured_response": {"error": type(exc).__name__, "detail": str(exc)[:300]},
                },
            )

        raw_text = (completion.content or "").strip()
        replay_base = {
            "model_id": completion.model,
            "route_profile_id": str(profile.get("profile_id") or route.profile_id),
            "route_profile_version": str(profile.get("version") or ""),
            "prompt_template_version": self.prompt_template_version,
            "generation_params": generation_params,
            "usage": dict(completion.usage or {}),
        }

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return self._escalate(
                "LLM judge returned non-JSON content; fail-closed escalate",
                replay={**replay_base, "raw_structured_response": {"malformed": True, "raw": raw_text[:2000]}},
            )

        if not isinstance(parsed, dict):
            return self._escalate(
                "LLM judge JSON root must be an object; fail-closed escalate",
                replay={**replay_base, "raw_structured_response": {"malformed": True, "raw": parsed}},
            )

        try:
            _validate_verdict(parsed, self.schema)
        except Exception as exc:  # noqa: BLE001 — schema / import failures fail closed
            return self._escalate(
                f"LLM judge schema validation failed: {type(exc).__name__}",
                replay={**replay_base, "raw_structured_response": parsed},
            )

        try:
            verdict = Verdict(str(parsed["verdict"]))
        except ValueError:
            return self._escalate(
                "LLM judge verdict enum invalid; fail-closed escalate",
                replay={**replay_base, "raw_structured_response": parsed},
            )

        confidence = float(parsed["confidence"])
        rationale = str(parsed["rationale"])
        matched = [str(item) for item in (parsed.get("matched_examples") or [])]
        missing = [str(item) for item in (parsed.get("missing_evidence") or [])]
        action = str(parsed.get("recommended_action") or "")

        if confidence < self.low_confidence_threshold:
            if rule.severity != Severity.LOW or verdict == Verdict.ALLOW:
                verdict = Verdict.ESCALATE
                rationale = f"{rationale}; low-confidence escalation (threshold={self.low_confidence_threshold})"
                action = action or "request_human_approval"

        return JudgeResult(
            verdict,
            confidence,
            rationale,
            matched,
            missing,
            action,
            replay_metadata={**replay_base, "raw_structured_response": parsed},
        )

    def _prompt_body(self, rule: Rule, subject: dict[str, Any]) -> str:
        payload = {
            "prompt_template_version": self.prompt_template_version,
            "rule": {
                "id": rule.id,
                "title": rule.title,
                "natural_language_rule": rule.natural_language_rule,
                "severity": rule.severity.value,
                "domain": rule.domain,
                "examples": rule.examples,
                "counterexamples": rule.counterexamples,
                "match_tags": rule.match_tags,
            },
            "subject": {
                "subject_ref": subject.get("subject_ref"),
                "summary": subject.get("summary"),
                "change_type": subject.get("change_type"),
                "tags": subject.get("tags") or [],
                "paths": subject.get("paths") or [],
                "evidence_refs": subject.get("evidence_refs") or [],
            },
            "required_json_keys": [
                "verdict",
                "confidence",
                "rationale",
                "matched_examples",
                "missing_evidence",
                "recommended_action",
            ],
        }
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)

    @staticmethod
    def _escalate(rationale: str, *, replay: dict[str, Any]) -> JudgeResult:
        return JudgeResult(
            Verdict.ESCALATE,
            0.0,
            rationale,
            [],
            ["structured_verdict"],
            "request_human_approval",
            replay_metadata=replay,
        )
