"""Code-Knowledge Graph domain package."""

from .documentation import HeuristicDocGenerator
from .embeddings import LocalEmbeddingStub, cosine, embed_text
from .enums import CallConfidence, DocStatus, SymbolKind
from .errors import (
    ClientDisconnected,
    CodeGraphError,
    ConflictError,
    DatabaseCapacityError,
    EmbeddingDimensionMismatchError,
    NotFoundError,
    ValidationError,
)
from .hashing import HASH_VERSION, content_hash, digest, normalize_source, now_iso, parser_version
from .languages import (
    LANGUAGE_MATRIX,
    REQUIRED_LANGUAGES,
    assert_language_supported,
    assert_required_languages_supported,
    detect_language_from_path,
    language_matrix,
    required_languages,
    supported_languages,
)
from .models import (
    EmbeddingResult,
    GraphEdge,
    GraphSymbol,
    IngestResult,
    ParseResult,
    ParsedSymbol,
    RepoIngestFileOutcome,
    RepoIngestResult,
    Scope,
)
from .parsers import parse_source, registered_parsers
from .repo_discovery import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_FILES,
    DiscoveredFile,
    discover_source_files,
)
from .parsing import (
    builtin_names,
    defined_names,
    extract_call_refs,
    parse_python_source,
    resolve_call_target,
)
from .ports import Store

__all__ = [
    "LANGUAGE_MATRIX",
    "REQUIRED_LANGUAGES",
    "HASH_VERSION",
    "CallConfidence",
    "CodeGraphError",
    "ConflictError",
    "DatabaseCapacityError",
    "DocStatus",
    "EmbeddingDimensionMismatchError",
    "EmbeddingResult",
    "GraphEdge",
    "GraphSymbol",
    "HeuristicDocGenerator",
    "IngestResult",
    "LocalEmbeddingStub",
    "NotFoundError",
    "ParseResult",
    "ParsedSymbol",
    "RepoIngestFileOutcome",
    "RepoIngestResult",
    "Scope",
    "Store",
    "SymbolKind",
    "ValidationError",
    "DEFAULT_EXCLUDE_DIRS",
    "DEFAULT_MAX_FILE_BYTES",
    "DEFAULT_MAX_FILES",
    "DiscoveredFile",
    "assert_language_supported",
    "assert_required_languages_supported",
    "builtin_names",
    "content_hash",
    "cosine",
    "defined_names",
    "detect_language_from_path",
    "digest",
    "discover_source_files",
    "embed_text",
    "extract_call_refs",
    "language_matrix",
    "normalize_source",
    "now_iso",
    "parse_python_source",
    "parse_source",
    "parser_version",
    "registered_parsers",
    "required_languages",
    "resolve_call_target",
    "supported_languages",
]
