"""Domain models and value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import CallConfidence, DocStatus, SymbolKind
from .errors import ValidationError


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    workspace_id: str
    project_id: str
    project_group_id: str | None = None

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.workspace_id.strip(), self.project_id.strip())):
            raise ValidationError("tenant_id, workspace_id, and project_id are required")


@dataclass
class GraphSymbol:
    id: str
    scope: Scope
    kind: SymbolKind
    file_path: str
    name: str
    qualified_name: str
    signature: str
    body: str
    hash_value: str
    ai_documentation: str
    doc_status: DocStatus
    embedding: list[float]
    visibility: str = "public"
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    language: str = ""
    hash_version: str = ""
    parser_version: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    id: str
    scope: Scope
    rel_type: str
    source_id: str
    target_id: str
    confidence: CallConfidence = CallConfidence.EXACT
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestResult:
    file_id: str
    symbols_indexed: int
    symbols_changed: int
    symbols_documented: int
    edges_written: int
    changed_symbol_ids: list[str]


@dataclass
class RepoIngestFileOutcome:
    relative_path: str
    language: str
    status: str  # ok | skipped | failed
    detail: str = ""
    file_id: str = ""
    symbols_indexed: int = 0
    symbols_changed: int = 0
    symbols_documented: int = 0
    edges_written: int = 0


@dataclass
class RepoIngestResult:
    root_path: str
    files_discovered: int
    files_ingested: int
    files_failed: int
    files_skipped: int
    symbols_indexed: int
    symbols_changed: int
    symbols_documented: int
    edges_written: int
    truncated: bool
    outcomes: list[RepoIngestFileOutcome]
    embedding_refresh: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_path": self.root_path,
            "files_discovered": self.files_discovered,
            "files_ingested": self.files_ingested,
            "files_failed": self.files_failed,
            "files_skipped": self.files_skipped,
            "symbols_indexed": self.symbols_indexed,
            "symbols_changed": self.symbols_changed,
            "symbols_documented": self.symbols_documented,
            "edges_written": self.edges_written,
            "truncated": self.truncated,
            "embedding_refresh": dict(self.embedding_refresh),
            "outcomes": [
                {
                    "relative_path": item.relative_path,
                    "language": item.language,
                    "status": item.status,
                    "detail": item.detail,
                    "file_id": item.file_id,
                    "symbols_indexed": item.symbols_indexed,
                    "symbols_changed": item.symbols_changed,
                    "symbols_documented": item.symbols_documented,
                    "edges_written": item.edges_written,
                }
                for item in self.outcomes
            ],
        }


@dataclass
class SyncRepoResult:
    """User-facing sync outcome; mode is chosen by the service, never by the caller."""

    mode: str  # full | incremental | noop
    root_path: str
    hint: str
    files_discovered: int
    files_ingested: int
    files_failed: int
    files_skipped: int
    symbols_indexed: int
    symbols_changed: int
    symbols_documented: int
    edges_written: int
    truncated: bool
    freshness: dict[str, Any]
    outcomes: list[RepoIngestFileOutcome] = field(default_factory=list)
    embedding_refresh: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_ingest(
        cls,
        *,
        mode: str,
        ingest: RepoIngestResult,
        freshness: dict[str, Any],
        hint: str = "",
    ) -> "SyncRepoResult":
        return cls(
            mode=mode,
            root_path=ingest.root_path,
            hint=hint,
            files_discovered=ingest.files_discovered,
            files_ingested=ingest.files_ingested,
            files_failed=ingest.files_failed,
            files_skipped=ingest.files_skipped,
            symbols_indexed=ingest.symbols_indexed,
            symbols_changed=ingest.symbols_changed,
            symbols_documented=ingest.symbols_documented,
            edges_written=ingest.edges_written,
            truncated=ingest.truncated,
            freshness=freshness,
            outcomes=list(ingest.outcomes),
            embedding_refresh=dict(ingest.embedding_refresh),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "mode": self.mode,
            "root_path": self.root_path,
            "hint": self.hint,
            "files_discovered": self.files_discovered,
            "files_ingested": self.files_ingested,
            "files_failed": self.files_failed,
            "files_skipped": self.files_skipped,
            "symbols_indexed": self.symbols_indexed,
            "symbols_changed": self.symbols_changed,
            "symbols_documented": self.symbols_documented,
            "edges_written": self.edges_written,
            "truncated": self.truncated,
            "freshness": self.freshness,
            "embedding_refresh": dict(self.embedding_refresh),
            "outcomes": [
                {
                    "relative_path": item.relative_path,
                    "language": item.language,
                    "status": item.status,
                    "detail": item.detail,
                    "file_id": item.file_id,
                    "symbols_indexed": item.symbols_indexed,
                    "symbols_changed": item.symbols_changed,
                    "symbols_documented": item.symbols_documented,
                    "edges_written": item.edges_written,
                }
                for item in self.outcomes
            ],
        }
        return payload


@dataclass
class ParsedSymbol:
    kind: SymbolKind
    name: str
    qualified_name: str
    signature: str
    body: str
    calls: list[str]
    imports: list[str]
    bases: list[str]
    visibility: str = "public"
    import_aliases: dict[str, str] = field(default_factory=dict)
    # Call names observed via getattr / reflection (capped by confidence_policy).
    reflection_calls: list[str] = field(default_factory=list)


@dataclass
class ParseResult:
    symbols: list[ParsedSymbol]
    import_aliases: dict[str, str]
    module_prefix: str


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    status: str
    model: str
    dims: int
