"""Docs-sync domain enums."""

from __future__ import annotations

from enum import StrEnum


class DocumentState(StrEnum):
    INDEXED = "indexed"
    VALID = "valid"
    INVALID_FRONTMATTER = "invalid_frontmatter"
    STALE = "stale"
    MISSING_ANCHOR = "missing_anchor"
    ARCHIVED = "archived"


class DriftType(StrEnum):
    MISSING_DOC = "missing_doc"
    STALE_DOC = "stale_doc"


class DriftState(StrEnum):
    DETECTED = "detected"
    TRIAGED = "triaged"
    TASK_CREATED = "task_created"
    FIXED = "fixed"
    IGNORED = "ignored"


class DraftState(StrEnum):
    GENERATED = "generated"
    WAITING_FOR_REVIEW = "waiting_for_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
