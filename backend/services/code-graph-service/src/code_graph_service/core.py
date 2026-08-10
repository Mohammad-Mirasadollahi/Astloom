"""Compatibility facade for the modular Code-Knowledge Graph package.

Prefer importing from `code_graph_service.domain` / `code_graph_service.application`
for new code. This module re-exports the previous `core` public surface.
"""

from __future__ import annotations

from .application.service import CodeGraphService
from .domain.documentation import HeuristicDocGenerator
from .domain.embeddings import LocalEmbeddingStub, cosine, embed_text
from .domain.enums import CallConfidence, DocStatus, SymbolKind
from .domain.errors import (
    CodeGraphError,
    ConflictError,
    DatabaseCapacityError,
    NotFoundError,
    ValidationError,
)
from .domain.hashing import digest, normalize_source, now_iso
from .domain.languages import (
    LANGUAGE_MATRIX,
    REQUIRED_LANGUAGES,
    assert_language_supported,
    assert_required_languages_supported,
    detect_language_from_path,
    language_matrix,
    required_languages,
    supported_languages,
)
from .domain.models import (
    EmbeddingResult,
    GraphEdge,
    GraphSymbol,
    IngestResult,
    ParseResult,
    ParsedSymbol,
    RepoIngestResult,
    Scope,
    SyncRepoResult,
)
from .domain.parsers import parse_source, registered_parsers
from .domain.parsing import (
    builtin_names,
    defined_names,
    extract_call_refs,
    parse_python_source,
    resolve_call_target,
)
from .domain.ports import Store

__all__ = [
    "LANGUAGE_MATRIX",
    "REQUIRED_LANGUAGES",
    "CallConfidence",
    "CodeGraphError",
    "CodeGraphService",
    "ConflictError",
    "DatabaseCapacityError",
    "DocStatus",
    "EmbeddingResult",
    "GraphEdge",
    "GraphSymbol",
    "HeuristicDocGenerator",
    "IngestResult",
    "LocalEmbeddingStub",
    "NotFoundError",
    "ParseResult",
    "ParsedSymbol",
    "RepoIngestResult",
    "Scope",
    "Store",
    "SymbolKind",
    "SyncRepoResult",
    "ValidationError",
    "assert_language_supported",
    "assert_required_languages_supported",
    "builtin_names",
    "cosine",
    "defined_names",
    "detect_language_from_path",
    "digest",
    "embed_text",
    "extract_call_refs",
    "language_matrix",
    "normalize_source",
    "now_iso",
    "parse_python_source",
    "parse_source",
    "registered_parsers",
    "required_languages",
    "resolve_call_target",
    "supported_languages",
]
