"""Domain enums for the Code-Knowledge Graph."""

from __future__ import annotations

from enum import StrEnum


class SymbolKind(StrEnum):
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    IMPORT = "import"
    DOCUMENTATION = "documentation"
    UNRESOLVED = "unresolved"
    EXTERNAL = "external"
    ROUTE = "route"
    RATIONALE = "rationale"


class RelType(StrEnum):
    """Canonical CODE_REL.rel_type values (logical vocabulary)."""

    CONTAINS = "CONTAINS"
    CALLS = "CALLS"
    IMPORTS = "IMPORTS"
    INHERITS_FROM = "INHERITS_FROM"
    DOCUMENTED_BY = "DOCUMENTED_BY"
    ROUTES_TO = "ROUTES_TO"
    TESTED_BY = "TESTED_BY"
    HTTP_CALLS = "HTTP_CALLS"
    ASYNC_CALLS = "ASYNC_CALLS"


class CallConfidence(StrEnum):
    EXACT = "exact"
    PROBABLE = "probable"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    EXTERNAL = "external"


class DocStatus(StrEnum):
    MISSING = "missing"
    GENERATED = "generated"
    UNCHANGED = "unchanged"
    HUMAN = "human"
