"""Compatibility facade for docs-sync domain + application types.

Prefer importing from ``enums``, ``errors``, ``models``, ``ports``, ``service``,
or ``util`` in new code. This module re-exports the former monolithic ``core``
surface so existing ``from docs_sync_service.core import …`` callers keep working.
"""

from __future__ import annotations

from .bloom import BloomFilter
from .enums import DocumentState, DraftState, DriftState, DriftType, Severity
from .errors import ConflictError, DocsSyncError, NotFoundError, ValidationError
from .models import (
    REQUIRED_FRONTMATTER,
    CodeSymbol,
    DocAnchor,
    Document,
    DocumentationDraft,
    DriftFinding,
    Scope,
)
from .ports import Store
from .service import DocsSyncService
from .util import (
    CRITICAL_TAGS,
    HIGH_TAGS,
    SECRET,
    digest,
    normalize_source,
    now,
    sanitize,
    severity_for,
)

__all__ = [
    "BloomFilter",
    "CRITICAL_TAGS",
    "CodeSymbol",
    "ConflictError",
    "DocAnchor",
    "DocsSyncError",
    "DocsSyncService",
    "Document",
    "DocumentState",
    "DocumentationDraft",
    "DraftState",
    "DriftFinding",
    "DriftState",
    "DriftType",
    "HIGH_TAGS",
    "NotFoundError",
    "REQUIRED_FRONTMATTER",
    "SECRET",
    "Scope",
    "Severity",
    "Store",
    "ValidationError",
    "digest",
    "normalize_source",
    "now",
    "sanitize",
    "severity_for",
]
