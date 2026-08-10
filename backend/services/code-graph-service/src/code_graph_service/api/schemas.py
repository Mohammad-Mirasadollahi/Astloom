"""HTTP request bodies for the code-graph FastAPI surface."""

from pydantic import BaseModel, ConfigDict, Field


class IngestFileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str
    source: str
    language: str | None = None


class PurgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yes: bool = False


class IngestRepoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_path: str
    include_extensions: list[str] | None = None
    exclude_dirs: list[str] | None = None
    max_files: int = Field(default=2000, ge=1, le=20000)
    max_file_bytes: int = Field(default=1_500_000, ge=1024, le=20_000_000)
    include_outcomes: bool = True


class IngestPushFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(min_length=1, max_length=1024)
    source: str = Field(max_length=2_000_000)
    language: str | None = Field(default=None, max_length=64)


class IngestPushDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(min_length=1, max_length=512)
    relative_path: str = Field(min_length=1, max_length=1024)
    body: str = Field(default="", max_length=2_000_000)
    title: str | None = Field(default=None, max_length=512)
    linked_symbol_tokens: list[str] = Field(default_factory=list, max_length=500)
    file_path: str | None = Field(default=None, max_length=1024)


class IngestPushRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: list[IngestPushFile] = Field(default_factory=list, max_length=2000)
    present_paths: list[str] | None = Field(default=None, max_length=20_000)
    inventory_complete: bool = False
    docs: list[IngestPushDoc] | None = Field(default=None, max_length=2000)
    include_outcomes: bool = True
    embedding_refresh_mode: str = Field(default="touched", max_length=32)
    max_files: int = Field(default=2000, ge=1, le=20000)
    max_file_bytes: int = Field(default=1_500_000, ge=1024, le=20_000_000)


class IngestPushCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1, max_length=128)


class RuntimeTraceCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str | None = None
    caller: str | None = None
    target: str | None = None
    callee: str | None = None
    call_site: str = ""
    count: int = Field(default=1, ge=1)
    file_path: str = "runtime"
    rel_type: str = "CALLS"
    metadata: dict[str, object] | None = None


class IngestRuntimeTracesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calls: list[RuntimeTraceCall] = Field(min_length=1)


class SemanticSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    top_k: int = Field(default=5, ge=1, le=50)


class ExploreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    top_k: int = Field(default=12, ge=1, le=40)
    max_depth: int = Field(default=2, ge=1, le=4)
    budget_chars: int | None = Field(default=None, ge=2000, le=100000)


class DetectChangesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changed_files: list[str] = Field(min_length=1)
    include_flows: bool = True


class ArchitectureOverviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_n: int = Field(default=10, ge=1, le=50)


class CallersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_k: int = Field(default=20, ge=1, le=200)
    max_depth: int = Field(default=1, ge=1, le=8)
    min_confidence: str | None = Field(
        default="probable",
        description="Confidence floor for structural edges (GAP-T02 default: probable).",
    )
    rel_types: list[str] | None = None


class ImpactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: str = Field(default="both")
    max_depth: int = Field(default=3, ge=1, le=8)
    min_confidence: str | None = Field(
        default="probable",
        description="Confidence floor for structural edges (GAP-T02 default: probable).",
    )
    rel_types: list[str] | None = None
    top_k: int = Field(default=50, ge=1, le=500)


class CommunityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_limit: int = Field(default=30, ge=1, le=200)


class CallPathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_depth: int = Field(default=4, ge=1, le=8)
    max_nodes: int = Field(default=40, ge=2, le=200)


class SymbolPathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_id: str
    end_id: str
    max_depth: int = Field(default=12, ge=1, le=30)


class HybridSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    top_k: int = Field(default=10, ge=1, le=50)


class PendingSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str | None = None
    file_paths: list[str] | None = None


class ReconcileAfterEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_paths: list[str]
    root_path: str | None = None
    run_sync: bool = False
    actor_id: str = "agent"
    correlation_id: str | None = None
    idempotency_key: str | None = None


class IdeSessionPositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_path: str
    file_path: str
    line: int = Field(ge=0)
    character: int = Field(ge=0)
    language: str | None = None


class IdeRenameRequest(IdeSessionPositionRequest):
    new_name: str
    apply: bool = True
    run_sync: bool = True
    actor_id: str = "agent"
    correlation_id: str | None = None
    idempotency_key: str | None = None


class GenerationContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed_symbol_id: str
    max_symbols: int = Field(default=12, ge=1, le=50)


class ValidateGeneratedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str


class LlmCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    system: str = "You are a helpful assistant."
    model: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=128000)
    response_format_json: bool = False
    # None → gateway env (ASTLOOM_LITELLM_REASONING_*); True/False overrides per call.
    reasoning_enabled: bool | None = None
    reasoning_effort: str | None = Field(default=None, max_length=32)
