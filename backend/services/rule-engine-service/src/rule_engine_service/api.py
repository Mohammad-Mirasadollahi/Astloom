from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .bootstrap import ServiceContainer, build_container
from .core import RuleEngineError, RuleEngineService, Scope, ValidationError


class RuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    natural_language_rule: str
    severity: str
    owner: str
    evaluation_mode: str
    state: str | None = None
    domain: str = "engineering"
    examples: list[str] = Field(default_factory=list)
    counterexamples: list[str] = Field(default_factory=list)
    match_tags: list[str] = Field(default_factory=list)
    required_approval_role: str | None = None
    precedence: int = 100


class RuleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    natural_language_rule: str | None = None
    severity: str | None = None
    state: str | None = None
    match_tags: list[str] | None = None
    examples: list[str] | None = None
    counterexamples: list[str] | None = None
    evaluation_mode: str | None = None
    required_approval_role: str | None = None


class SubjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_ref: str
    summary: str = ""
    change_type: str = ""
    tags: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    linked_task: str | None = None


class ApprovalRequestBody(BaseModel):
    evaluation_id: str
    approver: str | None = None


class ResolveApprovalRequest(BaseModel):
    status: str
    reason: str


class RouteTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_ref: str
    title: str
    assignee_type: str
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    evaluation_id: str
    label: str
    note: str = ""


def build_app(
    service: RuleEngineService | None = None,
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
    api = FastAPI(title="Astloom Rule Engine API", version="1.0.0")
    api.state.container = container

    @api.exception_handler(RuleEngineError)
    async def engine_error(_: Request, exc: RuleEngineError):
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
                    "documentation_ref": "docs/04-rule-engine-orchestration",
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
                    "documentation_ref": "docs/04-rule-engine-orchestration",
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

    @api.post("/api/v1/projects/{project_id}/rules", operation_id="create_rule")
    async def create_rule(
        project_id: str,
        body: RuleRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        rule = service.create_rule(scope, actor, correlation_id, idempotency_key or "", body.model_dump(exclude_none=True))
        return {"rule": rule.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/rules/{rule_id}:update-version", operation_id="update_rule_version")
    async def update_rule(
        project_id: str,
        rule_id: str,
        body: RuleUpdateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        rule = service.update_rule_version(scope, actor, correlation_id, idempotency_key or "", rule_id, body.model_dump(exclude_none=True))
        return {"rule": rule.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/evaluations", operation_id="evaluate_rules")
    async def evaluate(
        project_id: str,
        body: SubjectRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        result = service.evaluate_rules(scope, actor, correlation_id, idempotency_key or "", body.model_dump(exclude_none=True))
        return {**result, "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/evaluations:shadow", operation_id="run_rule_shadow_mode")
    async def shadow(
        project_id: str,
        body: SubjectRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        result = service.run_shadow(scope, actor, correlation_id, idempotency_key or "", body.model_dump(exclude_none=True))
        return {**result, "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/approvals", operation_id="request_approval")
    async def request_approval(
        project_id: str,
        body: ApprovalRequestBody,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        approval = service.request_approval(scope, actor, correlation_id, idempotency_key or "", body.evaluation_id, body.approver)
        return {"approval": approval.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/approvals/{approval_id}:resolve", operation_id="resolve_approval")
    async def resolve_approval(
        project_id: str,
        approval_id: str,
        body: ResolveApprovalRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        approval = service.resolve_approval(scope, actor, correlation_id, idempotency_key or "", approval_id, body.status, body.reason)
        return {"approval": approval.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/task-routes", operation_id="route_task")
    async def route_task(
        project_id: str,
        body: RouteTaskRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        task = service.route_task(scope, actor, correlation_id, idempotency_key or "", body.model_dump())
        return {"task": task.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/rule-feedback", operation_id="record_rule_feedback")
    async def feedback(
        project_id: str,
        body: FeedbackRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        item = service.record_feedback(scope, actor, correlation_id, idempotency_key or "", body.evaluation_id, body.label, body.note)
        return {"feedback": item.public(), "correlation_id": correlation_id}

    @api.get("/api/v1/projects/{project_id}/evaluations", operation_id="list_rule_evaluations")
    async def list_evaluations(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [item.public() for item in service.list_evaluations(scope)], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/evaluations/{evaluation_id}:explain", operation_id="explain_rule_decision")
    async def explain(
        project_id: str,
        evaluation_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"explanation": service.explain_decision(read_scope(project_id, x_tenant_id, x_workspace_id), evaluation_id), "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/approval-queue", operation_id="get_approval_queue")
    async def approval_queue(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [item.public() for item in service.get_approval_queue(scope)], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/anomalies", operation_id="list_anomalies")
    async def anomalies(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [item.public() for item in service.list_anomalies(scope)], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/rule-health", operation_id="get_rule_health")
    async def rule_health(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"health": service.get_rule_health(read_scope(project_id, x_tenant_id, x_workspace_id)), "correlation_id": None}

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
