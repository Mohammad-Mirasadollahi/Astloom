from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .bootstrap import ServiceContainer, build_container
from .core import MemoryError, MemoryService, Scope, ValidationError


class MemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    state: str | None = None
    pinned: bool = False
    expires_at: str | None = None


class MemoryPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    body: str | None = None
    tags: list[str] | None = None
    confidence: float | None = None
    pinned: bool | None = None
    expires_at: str | None = None
    expected_version: int | None = Field(default=None, ge=1)


class ConsolidateRequest(BaseModel):
    memory_ids: list[str]
    reason: str


class DecayRequest(BaseModel):
    memory_ids: list[str]
    reason: str


class PromoteMemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    memory_ids: list[str] | None = None


class DeprecateMemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    memory_ids: list[str] | None = None


class ContextRequest(BaseModel):
    query: str
    token_budget: int | None = None


class QuestionRequest(BaseModel):
    question: str
    evidence_refs: list[str] = Field(default_factory=list)


class PromoteFaqRequest(BaseModel):
    answer: str


class ResolveDocumentationRequest(BaseModel):
    confidence: float
    draft_content: str | None = None


class BatchRequest(BaseModel):
    title: str
    item_refs: list[str] = Field(default_factory=list)
    deferred_actions: list[str] = Field(default_factory=list)


class MarkReadyRequest(BaseModel):
    reason: str


def build_app(
    service: MemoryService | None = None,
    *,
    container: ServiceContainer | None = None,
) -> FastAPI:
    """Compose FastAPI with a process-scoped ``ServiceContainer`` on ``app.state``."""
    if container is not None and service is not None and service is not container.service:
        raise ValueError("pass either service or container, not conflicting both")
    if container is None:
        if service is not None:
            container = ServiceContainer(service=service, settings=None)
        else:
            container = build_container()
    service = container.service
    api = FastAPI(title="Astloom Memory Service API", version="1.0.0")
    api.state.container = container

    @api.exception_handler(MemoryError)
    async def memory_error(_: Request, exc: MemoryError):
        status_code = 400 if exc.category == "validation_error" else 409 if exc.category == "conflict_error" else 404
        return JSONResponse(
            {
                "error": {
                    "error_code": exc.code,
                    "category": exc.category,
                    "message": exc.message,
                    "retryable": False,
                    "correlation_id": None,
                    "details": {},
                    "documentation_ref": "docs/02-memory-and-context",
                }
            },
            status_code=status_code,
        )

    @api.exception_handler(RequestValidationError)
    async def validation(_: Request, exc: RequestValidationError):
        return JSONResponse(
            {
                "error": {
                    "error_code": "validation_error",
                    "category": "validation_error",
                    "message": "request validation failed",
                    "retryable": False,
                    "correlation_id": None,
                    "details": {"fields": exc.errors()},
                    "documentation_ref": "docs/02-memory-and-context",
                }
            },
            status_code=400,
        )

    def ctx(project_id: str, tenant_id: str | None, workspace_id: str | None, actor_id: str | None, correlation_id: str | None):
        if not actor_id:
            raise ValidationError("X-Actor-Id header is required")
        return Scope(tenant_id or "", workspace_id or "", project_id), actor_id, correlation_id or str(uuid4())

    def read_scope(project_id: str, tenant_id: str | None, workspace_id: str | None) -> Scope:
        return Scope(tenant_id or "", workspace_id or "", project_id)

    @api.post("/api/v1/projects/{project_id}/memory-items", operation_id="create_memory_item")
    async def create_memory(
        project_id: str,
        body: MemoryRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        record = service.create_memory(scope, actor, correlation_id, idempotency_key or "", body.model_dump(exclude_none=True))
        return {"memory": record.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/memory-consolidations", operation_id="consolidate_memory")
    async def consolidate(
        project_id: str,
        body: ConsolidateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        items = service.consolidate_memory(scope, actor, correlation_id, idempotency_key or "", body.memory_ids, body.reason)
        return {"items": [item.public() for item in items], "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/memory-decays", operation_id="decay_memory")
    async def decay(
        project_id: str,
        body: DecayRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        items = service.decay_memory(scope, actor, correlation_id, idempotency_key or "", body.memory_ids, body.reason)
        return {"items": [item.public() for item in items], "correlation_id": correlation_id}

    @api.get("/api/v1/projects/{project_id}/memory-items", operation_id="list_memory_items")
    async def list_memory(
        project_id: str,
        state: str | None = None,
        kind: str | None = None,
        pinned: bool | None = None,
        q: str | None = None,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        items = service.list_memories(scope, state=state, kind=kind, pinned=pinned, q=q)
        return {"items": [item.public() for item in items], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/memory-items/{memory_item_id}", operation_id="get_memory_item")
    async def get_memory(
        project_id: str,
        memory_item_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"memory": service.get_memory(scope, memory_item_id).public(), "correlation_id": None}

    @api.patch("/api/v1/projects/{project_id}/memory-items/{memory_item_id}", operation_id="update_memory_item")
    async def update_memory(
        project_id: str,
        memory_item_id: str,
        body: MemoryPatchRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        record = service.update_memory(
            scope,
            actor,
            correlation_id,
            idempotency_key or "",
            memory_item_id,
            body.model_dump(exclude_unset=True),
        )
        return {"memory": record.public(), "correlation_id": correlation_id}

    @api.post(
        "/api/v1/projects/{project_id}/memory-items/{memory_item_id}:promote",
        operation_id="promote_memory_item",
    )
    async def promote_memory_item(
        project_id: str,
        memory_item_id: str,
        body: PromoteMemoryRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        items = service.promote_memory(
            scope,
            actor,
            correlation_id,
            idempotency_key or "",
            [memory_item_id],
            body.reason,
        )
        return {"memory": items[0].public(), "correlation_id": correlation_id}

    @api.post(
        "/api/v1/projects/{project_id}/memory-items/{memory_item_id}:deprecate",
        operation_id="deprecate_memory_item",
    )
    async def deprecate_memory_item(
        project_id: str,
        memory_item_id: str,
        body: DeprecateMemoryRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        items = service.deprecate_memory(
            scope,
            actor,
            correlation_id,
            idempotency_key or "",
            [memory_item_id],
            body.reason,
        )
        return {"memory": items[0].public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/memory-promotions", operation_id="promote_memory_bulk")
    async def promote_memory_bulk(
        project_id: str,
        body: PromoteMemoryRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        if not body.memory_ids:
            raise ValidationError("memory_ids are required")
        items = service.promote_memory(
            scope,
            actor,
            correlation_id,
            idempotency_key or "",
            body.memory_ids,
            body.reason,
        )
        return {"items": [item.public() for item in items], "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/context-bundles", operation_id="build_context_bundle")
    async def context_bundle(
        project_id: str,
        body: ContextRequest,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        return {"bundle": service.retrieve_context(scope, actor, correlation_id, body.query, body.token_budget).public(), "correlation_id": correlation_id}

    @api.get("/api/v1/projects/{project_id}/context-bundles:explain", operation_id="explain_context_retrieval")
    async def explain(
        project_id: str,
        query: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"explanation": service.explain_retrieval(read_scope(project_id, x_tenant_id, x_workspace_id), query), "correlation_id": None}

    @api.post("/api/v1/projects/{project_id}/question-memories", operation_id="observe_question")
    async def observe_question(
        project_id: str,
        body: QuestionRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        item = service.observe_question(scope, actor, correlation_id, idempotency_key or "", body.question, body.evidence_refs)
        return {"question_memory": item.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/question-memories/{question_id}:promote-faq", operation_id="promote_faq")
    async def promote_faq(
        project_id: str,
        question_id: str,
        body: PromoteFaqRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        item = service.promote_faq(scope, actor, correlation_id, idempotency_key or "", question_id, body.answer)
        return {"question_memory": item.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/question-memories/{question_id}:resolve-documentation", operation_id="resolve_missing_documentation")
    async def resolve_documentation(
        project_id: str,
        question_id: str,
        body: ResolveDocumentationRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        result = service.resolve_missing_documentation(
            scope,
            actor,
            correlation_id,
            idempotency_key or "",
            question_id,
            body.confidence,
            body.draft_content,
        )
        return {**result, "correlation_id": correlation_id}

    @api.get("/api/v1/projects/{project_id}/repeated-questions", operation_id="list_repeated_questions")
    async def repeated_questions(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"items": [item.public() for item in service.list_repeated_questions(read_scope(project_id, x_tenant_id, x_workspace_id))], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/curious-questions", operation_id="list_curious_questions")
    async def curious_questions(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"items": service.list_curious_questions(read_scope(project_id, x_tenant_id, x_workspace_id)), "correlation_id": None}

    @api.post("/api/v1/projects/{project_id}/work-batches", operation_id="open_work_batch")
    async def open_batch(
        project_id: str,
        body: BatchRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        batch = service.open_batch(scope, actor, correlation_id, idempotency_key or "", body.title, body.item_refs, body.deferred_actions)
        return {"batch": batch.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/work-batches/{batch_id}:mark-ready", operation_id="mark_batch_ready")
    async def mark_ready(
        project_id: str,
        batch_id: str,
        body: MarkReadyRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        batch = service.mark_batch_ready(scope, actor, correlation_id, idempotency_key or "", batch_id, body.reason)
        return {"batch": batch.public(), "correlation_id": correlation_id}

    @api.get("/api/v1/projects/{project_id}/work-batches/{batch_id}", operation_id="get_batch_state")
    async def get_batch(
        project_id: str,
        batch_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"batch": service.store.get_batch(batch_id, read_scope(project_id, x_tenant_id, x_workspace_id)).public(), "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/stale-memory", operation_id="list_stale_memory")
    async def stale_memory(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"items": [item.public() for item in service.list_stale_memory(read_scope(project_id, x_tenant_id, x_workspace_id))], "correlation_id": None}

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
