"""Semantic judge port and local heuristic adapter."""

from __future__ import annotations

from typing import Any, Protocol

from .constants import SENSITIVE_DOMAINS
from .enums import Severity, Verdict
from .models import JudgeResult, Rule
from .util import tokenize


class Judge(Protocol):
    def judge(self, rule: Rule, subject: dict[str, Any]) -> JudgeResult: ...


class HeuristicJudge:
    """Local semantic judge adapter — no external model calls."""

    def judge(self, rule: Rule, subject: dict[str, Any]) -> JudgeResult:
        haystack = " ".join(
            [
                str(subject.get("summary") or ""),
                " ".join(subject.get("tags") or []),
                " ".join(subject.get("paths") or []),
                str(subject.get("change_type") or ""),
            ]
        ).lower()
        rule_text = (rule.natural_language_rule + " " + " ".join(rule.match_tags)).lower()
        overlap = len(set(tokenize(haystack)) & set(tokenize(rule_text)))
        sensitive = bool(set(subject.get("tags") or []) & SENSITIVE_DOMAINS) or rule.domain in SENSITIVE_DOMAINS
        if sensitive and overlap:
            return JudgeResult(
                Verdict.ESCALATE if rule.severity in {Severity.HIGH, Severity.CRITICAL} else Verdict.BLOCK,
                0.86,
                f"semantic judge matched sensitive policy '{rule.title}' with overlap={overlap}",
                matched_examples=rule.examples[:2],
                recommended_action="request_human_approval",
            )
        if overlap >= 2:
            return JudgeResult(
                Verdict.WARN,
                0.72,
                f"semantic judge found partial match for '{rule.title}'",
                rule.examples[:1],
                [],
                "warn",
            )
        return JudgeResult(
            Verdict.ALLOW,
            0.9,
            f"semantic judge found no material conflict with '{rule.title}'",
            [],
            [],
            "allow",
        )
