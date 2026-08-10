"""Re-export docs audit scope (prefer ``astloom_cli.docs_audit_scope``)."""

from __future__ import annotations

from astloom_cli.docs_audit_scope import (
    DEFAULT_DOCS_AUDIT_EXCLUDE_GLOBS,
    DEFAULT_DOC_ROOTS,
    FULL_TIER_DOC_ROOTS,
    is_docs_audit_basename_skipped,
    is_docs_audit_path,
    is_full_tier_doc_path,
    merge_docs_audit_exclude_globs,
    normalize_repo_rel,
)

__all__ = [
    "DEFAULT_DOCS_AUDIT_EXCLUDE_GLOBS",
    "DEFAULT_DOC_ROOTS",
    "FULL_TIER_DOC_ROOTS",
    "is_docs_audit_basename_skipped",
    "is_docs_audit_path",
    "is_full_tier_doc_path",
    "merge_docs_audit_exclude_globs",
    "normalize_repo_rel",
]
