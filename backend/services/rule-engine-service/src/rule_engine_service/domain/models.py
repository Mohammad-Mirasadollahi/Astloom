"""Rule-engine domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import (
    ApprovalState,
    EvaluationMode,
    EvaluationState,
    RuleState,
    Severity,
    Verdict,
)
from .errors import ConflictError, ValidationError


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    workspace_id: str
    project_id: str
    project_group_id: str | None = None

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.workspace_id.strip(), self.project_id.strip())):
            raise ValidationError("tenant_id, workspace_id, and project_id are required")


@dataclass
class Rule:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    title: str
    natural_language_rule: str
    severity: Severity
    owner: str
    evaluation_mode: EvaluationMode
    state: RuleState
    domain: str
    examples: list[str]
    counterexamples: list[str]
    match_tags: list[str]
    required_approval_role: str | None
    precedence: int
    version: int
    created_at: str
    updated_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "title": self.title,
            "natural_language_rule": self.natural_language_rule,
            "severity": self.severity.value,
            "owner": self.owner,
            "evaluation_mode": self.evaluation_mode.value,
            "state": self.state.value,
            "domain": self.domain,
            "examples": self.examples,
            "counterexamples": self.counterexamples,
            "match_tags": self.match_tags,
            "required_approval_role": self.required_approval_role,
            "precedence": self.precedence,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class RuleEvaluation:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    rule_id: str
    subject_ref: str
    verdict: Verdict
    confidence: float
    rationale: str
    evidence_refs: list[str]
    used_llm: bool
    state: EvaluationState
    shadow: bool
    risk_score: float
    created_at: str
    updated_at: str
    version: int = 1
    judge_replay: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "rule_id": self.rule_id,
            "subject_ref": self.subject_ref,
            "verdict": self.verdict.value,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs,
            "used_llm": self.used_llm,
            "state": self.state.value,
            "shadow": self.shadow,
            "risk_score": self.risk_score,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "judge_replay": self.judge_replay,
        }


@dataclass
class ApprovalRequest:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    evaluation_id: str
    rule_id: str
    approver: str
    status: ApprovalState
    options: list[str]
    deadline: str
    decision_reason: str | None
    evidence_refs: list[str]
    created_at: str
    updated_at: str
    version: int = 1

    def resolve(self, status: ApprovalState, reason: str, at: str) -> None:
        if self.status != ApprovalState.REQUESTED:
            raise ConflictError("approval is not open")
        if status not in {ApprovalState.APPROVED, ApprovalState.REJECTED, ApprovalState.CANCELED}:
            raise ValidationError("invalid approval resolution")
        self.status = status
        self.decision_reason = reason
        self.version += 1
        self.updated_at = at

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "evaluation_id": self.evaluation_id,
            "rule_id": self.rule_id,
            "approver": self.approver,
            "status": self.status.value,
            "options": self.options,
            "deadline": self.deadline,
            "decision_reason": self.decision_reason,
            "evidence_refs": self.evidence_refs,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class RoutedTask:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    subject_ref: str
    title: str
    assignee_type: str
    reason: str
    evidence_refs: list[str]
    created_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "subject_ref": self.subject_ref,
            "title": self.title,
            "assignee_type": self.assignee_type,
            "reason": self.reason,
            "evidence_refs": self.evidence_refs,
            "created_at": self.created_at,
        }


@dataclass
class AnomalySignal:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    subject_ref: str
    signal_type: str
    score: float
    rationale: str
    evidence_refs: list[str]
    created_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "subject_ref": self.subject_ref,
            "signal_type": self.signal_type,
            "score": self.score,
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs,
            "created_at": self.created_at,
        }


@dataclass
class RuleFeedback:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    evaluation_id: str
    label: str
    note: str
    created_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "evaluation_id": self.evaluation_id,
            "label": self.label,
            "note": self.note,
            "created_at": self.created_at,
        }


@dataclass
class ImpactMap:
    id: str
    scope: Scope
    change_ref: str
    affected_entities: list[dict[str, Any]]
    risk_level: Severity
    generated_task_refs: list[str]
    confidence: float
    created_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "change_ref": self.change_ref,
            "affected_entities": self.affected_entities,
            "risk_level": self.risk_level.value,
            "generated_task_refs": self.generated_task_refs,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


@dataclass
class JudgeResult:
    verdict: Verdict
    confidence: float
    rationale: str
    matched_examples: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    recommended_action: str = ""
    replay_metadata: dict[str, Any] = field(default_factory=dict)
