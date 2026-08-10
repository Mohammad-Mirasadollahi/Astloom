"""Shared constants for unused-candidate detection."""

from __future__ import annotations

import re

from ..enums import SymbolKind

SCOPE_MODES = frozenset(
    {"task_neighborhood", "changed_symbols", "explicit_paths", "project_scan"}
)

ELIGIBLE_KINDS = frozenset(
    {
        SymbolKind.FUNCTION,
        SymbolKind.METHOD,
        SymbolKind.CLASS,
    }
)

TSOC_DEFER = re.compile(r"tsoc-defer\s*:", re.IGNORECASE)
STRING_REGISTRY_HINT = re.compile(
    r"(PERMISSION|ROUTE|FEATURE_FLAG|REGISTRY|HANDLERS)\s*=\s*[{\[]",
    re.IGNORECASE,
)
PUBLIC_HTTP_HINT = re.compile(
    r"@(?:app|router|blueprint)\.(?:get|post|put|delete|patch|route)\b|"
    r"APIRouter\(|FastAPI\(|@require_permission\b",
    re.IGNORECASE,
)
