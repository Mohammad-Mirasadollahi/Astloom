"""Rule-engine domain enums."""

from __future__ import annotations

from enum import StrEnum


class RuleState(StrEnum):
    DRAFT = "draft"
    SHADOW = "shadow"
    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"


class EvaluationMode(StrEnum):
    DETERMINISTIC = "deterministic"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    MANUAL = "manual"


class Verdict(StrEnum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    ESCALATE = "escalate"


class EvaluationState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ESCALATED = "escalated"
    ERRORED = "errored"


class ApprovalState(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELED = "canceled"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
