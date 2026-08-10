from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .bootstrap import ServiceContainer, build_container
from .errors import DocsSyncError, ValidationError
from .models import Scope
from .service import DocsSyncService


class SymbolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo: str
    file_path: str
    symbol_path: str
    kind: str
    body: str
    signature: str | None = None
    doc_required: bool = True
    tags: list[str] = Field(default_factory=list)


class DocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    frontmatter: dict[str, Any]
    body: str = ""


class FrontmatterRequest(BaseModel):
    frontmatter: dict[str, Any]


class AnchorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    symbol_id: str
    recorded_hash: str


class DriftRequest(BaseModel):
    symbol_ids: list[str] = Field(default_factory=list)


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol_id: str
    title: str
    body: str
    finding_id: str | None = None


class CiGateRequest(BaseModel):
    waived_finding_ids: list[str] = Field(default_factory=list)


def build_app(
    service: DocsSyncService | None = None,
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
    api = FastAPI(title="Astloom Docs Sync API", version="1.0.0")
    api.state.container = container

    @api.exception_handler(DocsSyncError)
    async def docs_error(_: Request, exc: DocsSyncError):
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
                    "documentation_ref": "docs/03-docs-as-code-sync",
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
                    "documentation_ref": "docs/03-docs-as-code-sync",
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

    @api.post("/api/v1/projects/{project_id}/symbols", operation_id="index_symbol")
    async def index_symbol(
        project_id: str,
        body: SymbolRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        symbol = service.index_symbol(scope, actor, correlation_id, idempotency_key or "", body.model_dump(exclude_none=True))
        return {"symbol": symbol.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/documents", operation_id="index_document")
    async def index_document(
        project_id: str,
        body: DocumentRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        document = service.index_document(scope, actor, correlation_id, idempotency_key or "", body.model_dump())
        return {"document": document.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/documents:validate-frontmatter", operation_id="validate_frontmatter")
    async def validate_frontmatter(project_id: str, body: FrontmatterRequest):
        errors = service.validate_frontmatter(body.frontmatter)
        return {"valid": not errors, "errors": errors, "project_id": project_id}

    @api.post("/api/v1/projects/{project_id}/anchors", operation_id="register_anchor")
    async def register_anchor(
        project_id: str,
        body: AnchorRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        anchor = service.register_anchor(scope, actor, correlation_id, idempotency_key or "", body.model_dump())
        return {"anchor": anchor.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/drift-detections", operation_id="detect_drift")
    async def detect_drift(
        project_id: str,
        body: DriftRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        findings = service.detect_drift(scope, actor, correlation_id, idempotency_key or "", body.symbol_ids or None)
        return {"findings": [finding.public() for finding in findings], "correlation_id": correlation_id}

    @api.get("/api/v1/projects/{project_id}/drift-findings", operation_id="list_drift_findings")
    async def list_findings(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [finding.public() for finding in service.list_drift_findings(scope)], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/symbols/{symbol_id}/docs", operation_id="find_docs_for_symbol")
    async def find_docs(
        project_id: str,
        symbol_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [document.public() for document in service.find_docs_for_symbol(scope, symbol_id)], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/coverage", operation_id="get_doc_coverage")
    async def coverage(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"coverage": service.get_doc_coverage(read_scope(project_id, x_tenant_id, x_workspace_id)), "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/missing-docs", operation_id="find_missing_docs")
    async def missing_docs(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"items": service.find_missing_docs(read_scope(project_id, x_tenant_id, x_workspace_id)), "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/impact:explain", operation_id="explain_doc_impact")
    async def explain(
        project_id: str,
        symbol_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"explanation": service.explain_doc_impact(read_scope(project_id, x_tenant_id, x_workspace_id), symbol_id), "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/bloom-lookups", operation_id="bloom_lookup")
    async def bloom_lookup(
        project_id: str,
        symbol_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"lookup": service.bloom_lookup(read_scope(project_id, x_tenant_id, x_workspace_id), symbol_id), "correlation_id": None}

    @api.post("/api/v1/projects/{project_id}/drafts", operation_id="create_documentation_draft")
    async def create_draft(
        project_id: str,
        body: DraftRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        draft = service.create_draft(scope, actor, correlation_id, idempotency_key or "", body.model_dump(exclude_none=True))
        return {"draft": draft.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/drafts/{draft_id}:approve", operation_id="approve_documentation_draft")
    async def approve_draft(
        project_id: str,
        draft_id: str,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        draft = service.approve_draft(scope, actor, correlation_id, idempotency_key or "", draft_id)
        return {"draft": draft.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/ci-gate", operation_id="evaluate_ci_gate")
    async def ci_gate(
        project_id: str,
        body: CiGateRequest,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"gate": service.evaluate_ci_gate(read_scope(project_id, x_tenant_id, x_workspace_id), body.waived_finding_ids), "correlation_id": None}

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
