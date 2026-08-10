"""Compatibility facade for the modular rule-engine package.

Prefer ``rule_engine_service.domain`` / ``rule_engine_service.application`` for
new code. This module re-exports the previous ``core`` public surface.
"""

from __future__ import annotations

from .application.service import RuleEngineService
from .domain.constants import SECRET, SENSITIVE_DOMAINS, TASK_TRIGGERS
from .domain.enums import (
    ApprovalState,
    EvaluationMode,
    EvaluationState,
    RuleState,
    Severity,
    Verdict,
)
from .domain.errors import ConflictError, NotFoundError, RuleEngineError, ValidationError
from .domain.judge import HeuristicJudge, Judge
from .litellm_judge import LiteLLMJudge
from .domain.models import (
    AnomalySignal,
    ApprovalRequest,
    ImpactMap,
    JudgeResult,
    RoutedTask,
    Rule,
    RuleEvaluation,
    RuleFeedback,
    Scope,
)
from .domain.ports import Store
from .domain.util import digest, now, sanitize, severity_score, tokenize

__all__ = [
    "SECRET",
    "SENSITIVE_DOMAINS",
    "TASK_TRIGGERS",
    "AnomalySignal",
    "ApprovalRequest",
    "ApprovalState",
    "ConflictError",
    "EvaluationMode",
    "EvaluationState",
    "HeuristicJudge",
    "ImpactMap",
    "Judge",
    "JudgeResult",
    "NotFoundError",
    "RoutedTask",
    "Rule",
    "RuleEngineError",
    "RuleEngineService",
    "RuleEvaluation",
    "RuleFeedback",
    "RuleState",
    "Scope",
    "Severity",
    "Store",
    "ValidationError",
    "Verdict",
    "digest",
    "now",
    "sanitize",
    "severity_score",
    "tokenize",
]
