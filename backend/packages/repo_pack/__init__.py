"""
Module contract: Repo pack / ignore / secret-scan helpers (Repomix + CBM ideas).

Role: Layered ignore, heuristic secret scan, token estimates, change-scoped review packs.
SoT/invariants: Local-only; fail closed on secrets for export; no cloud pack.
Allowed failures: missing ignore files; empty file lists; token budget exceeded → exit.
Forbidden: vendoring Repomix/CBM; skipping secret scan by default on export.
"""

from __future__ import annotations

from .layered_ignore import (
    IgnoreRule,
    collect_layered_ignore_globs,
    collect_layered_ignore_rules,
    collect_layered_reinclude_globs,
    load_ignore_file_patterns,
    path_is_ignored,
)
from .review_pack import ReviewPackResult, build_review_pack
from .secret_scan import SecretFinding, scan_text_for_secrets
from .tokens import estimate_tokens, tokens_from_chars

__all__ = [
    "IgnoreRule",
    "ReviewPackResult",
    "SecretFinding",
    "build_review_pack",
    "collect_layered_ignore_globs",
    "collect_layered_ignore_rules",
    "collect_layered_reinclude_globs",
    "estimate_tokens",
    "load_ignore_file_patterns",
    "path_is_ignored",
    "scan_text_for_secrets",
    "tokens_from_chars",
]
