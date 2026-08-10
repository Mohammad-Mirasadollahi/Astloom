"""Memory domain enums."""

from __future__ import annotations

from enum import StrEnum


class MemoryKind(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    RESTRICTED = "restricted"
    DEPRECATED = "deprecated"


class MemoryState(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    RESTRICTED = "restricted"
    STALE = "stale"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class QuestionState(StrEnum):
    OBSERVED = "observed"
    SEARCHING = "searching"
    ANSWERED = "answered"
    DRAFT_GENERATED = "draft_generated"
    APPROVED_FAQ = "approved_faq"
    BLOCKED_BY_GAP = "blocked_by_gap"


class BatchState(StrEnum):
    OPEN = "open"
    ACTIVE = "active"
    READY = "ready_for_consolidation"
    CONSOLIDATING = "consolidating"
    COMPLETED = "completed"
