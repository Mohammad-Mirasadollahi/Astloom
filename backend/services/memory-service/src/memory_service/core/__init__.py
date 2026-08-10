"""
Role: Memory domain model and MemoryService orchestration (retrieve, consolidate, decay, FAQ).
SoT: Scoped MemoryItem / QuestionMemory / WorkBatch / ContextBundle; WeightProfile thresholds.
Allowed: typed MemoryError subclasses; skip restricted on consolidate/decay; emit outbox events.
Forbidden: cross-scope retrieval; restricted memory in ContextBundle items; inventing weights.
"""

from __future__ import annotations

from .constants import HISTORY_TERMS, SECRET
from .enums import BatchState, MemoryKind, MemoryState, QuestionState
from .errors import ConflictError, MemoryError, NotFoundError, ValidationError
from .helpers import (
    digest,
    documentation_outcome,
    estimate_tokens,
    normalize_optional_timestamp,
    normalize_question,
    now,
    parse_timestamp,
    sanitize,
    slug,
    tokenize,
)
from .models import ContextBundle, MemoryItem, QuestionMemory, Scope, WeightProfile, WorkBatch
from .protocols import Store
from .service import MemoryService

__all__ = [
    "HISTORY_TERMS",
    "SECRET",
    "BatchState",
    "ConflictError",
    "ContextBundle",
    "MemoryError",
    "MemoryItem",
    "MemoryKind",
    "MemoryService",
    "MemoryState",
    "NotFoundError",
    "QuestionMemory",
    "QuestionState",
    "Scope",
    "Store",
    "ValidationError",
    "WeightProfile",
    "WorkBatch",
    "digest",
    "documentation_outcome",
    "estimate_tokens",
    "normalize_optional_timestamp",
    "normalize_question",
    "now",
    "parse_timestamp",
    "sanitize",
    "slug",
    "tokenize",
]
