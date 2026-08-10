"""Docs audit eligibility helpers (no CLI command imports — sync_config-safe).

Module contract:
- Role: basename skips + default/operator audit exclude globs for Full-tier checks.
- Source of truth: built-in README/AGENTS/skill/tests defaults; operators add more via
  ``docs.audit.exclude`` in ``astloom.sync.yaml``.
- Failures: never raise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

# Fallback scan roots when no astloom.sync.yaml is present (Astloom layout).
FULL_TIER_DOC_ROOTS: tuple[str, ...] = (
    "docs",
    "backend/docs",
    "frontend/docs",
    "deploy-toolkit",
)
DEFAULT_DOC_ROOTS = FULL_TIER_DOC_ROOTS

DEFAULT_DOCS_AUDIT_EXCLUDE_GLOBS: tuple[str, ...] = (
    "**/README.md",
    "**/README.mdx",
    "**/AGENTS.md",
    "**/SKILL.md",
    "**/.agents/skills/**",
    "**/seed_mcp_first_prompts/**",
    "**/tests/**",
    "**/test/**",
)

_AUDIT_SKIP_NAMES: frozenset[str] = frozenset(
    {
        "readme.md",
        "readme.mdx",
        "agents.md",
    }
)


def normalize_repo_rel(path: str) -> str:
    return str(path or "").strip().replace("\\", "/").lstrip("./")


def is_docs_audit_basename_skipped(relative_path: str) -> bool:
    """True for README / AGENTS basenames (never Full-tier-audited)."""
    name = Path(normalize_repo_rel(relative_path)).name.casefold()
    return name in _AUDIT_SKIP_NAMES


def merge_docs_audit_exclude_globs(extra: Iterable[str] | None = None) -> list[str]:
    """Defaults + operator globs, de-duplicated (order: defaults first)."""
    seen: set[str] = set()
    out: list[str] = []
    for item in (*DEFAULT_DOCS_AUDIT_EXCLUDE_GLOBS, *(extra or ())):
        text = normalize_repo_rel(str(item or ""))
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def is_docs_audit_path(
    relative_path: str,
    *,
    audit_exclude_globs: Iterable[str] | None = None,
) -> bool:
    """Return True when a discovered Markdown path should be Full-tier-audited."""
    rel = normalize_repo_rel(relative_path)
    if not rel:
        return False
    lower = rel.casefold()
    if not (lower.endswith(".md") or lower.endswith(".mdx")):
        return False
    if is_docs_audit_basename_skipped(rel):
        return False
    try:
        from code_graph_service.domain.repo_discovery import path_matches_glob
    except Exception:  # noqa: BLE001
        path_matches_glob = None  # type: ignore[assignment]
    for pattern in merge_docs_audit_exclude_globs(audit_exclude_globs):
        if path_matches_glob is not None:
            if path_matches_glob(rel, pattern):
                return False
        elif pattern.casefold() in {rel.casefold(), f"**/{Path(rel).name.casefold()}"}:
            return False
    return True


def is_full_tier_doc_path(relative_path: str) -> bool:
    """Legacy: under default Astloom roots and audit-eligible."""
    rel = normalize_repo_rel(relative_path)
    if not is_docs_audit_path(rel):
        return False
    for root in FULL_TIER_DOC_ROOTS:
        if rel == root or rel.startswith(f"{root}/"):
            return True
    return False


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
