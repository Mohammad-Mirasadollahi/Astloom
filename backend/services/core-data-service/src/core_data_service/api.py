from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .bootstrap import ServiceContainer, build_container
from .core import CoreData, CoreDataError, Kind, Scope, ValidationError


class CreateRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str | None = None
    action_summary: str | None = None
    session_id: str | None = None
    agent_id: str | None = None
    summary: str | None = None
    title: str | None = None
    context: str | None = None
    options_considered: list[str] = Field(default_factory=list)
    chosen_option: str | None = None
    consequences: list[str] = Field(default_factory=list)
    generated_rules: list[str] = Field(default_factory=list)
    linked_entities: list[str] = Field(default_factory=list)
    owner: str | None = None
    description: str | None = None
    severity: str | None = None
    escalation_reason: str | None = None
    task_specs: list[dict[str, Any]] = Field(default_factory=list)
    assignee_type: str | None = None
    instructions: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    status: str | None = None
    artifact_ref: str | None = None
    author_ref: str | None = None
    forbid_self_approval: bool | None = None
    changeset_id: str | None = None
    anchor_kind: str | None = None
    thread_id: str | None = None
    body: str | None = None
    target_kind: str | None = None
    target_id: str | None = None
    name: str | None = None
    task_id: str | None = None
    issue_id: str | None = None
    external_fingerprint: str | None = None
    verdict: str | None = None


class TransitionTaskStateRequest(BaseModel):
    status: str
    reason: str
    expected_version: int | None = None


def build_app(
    service: CoreData | None = None,
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
    api = FastAPI(title="Astloom Core Data API", version="1.0.0")
    api.state.container = container

    @api.exception_handler(CoreDataError)
    async def error(_: Request, exc: CoreDataError):
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
                    "documentation_ref": "docs/01-core-data-model",
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
                    "documentation_ref": "docs/01-core-data-model",
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

    def post(kind: Kind):
        async def handler(
            project_id: str,
            body: CreateRecordRequest,
            idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
            x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
            x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
            x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
            x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
        ):
            scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
            payload = body.model_dump(exclude_none=True)
            if kind == Kind.ISSUE:
                issue, tasks = service.create_issue(scope, actor, correlation_id, idempotency_key or "", payload)
                return {"record": issue.public(), "tasks": [task.public() for task in tasks], "correlation_id": correlation_id}
            if kind == Kind.CHANGESET:
                record = service.create_changeset(scope, actor, correlation_id, idempotency_key or "", payload)
                return {"record": record.public(), "correlation_id": correlation_id}
            return {
                "record": service.create(kind, scope, actor, correlation_id, idempotency_key or "", payload).public(),
                "correlation_id": correlation_id,
            }

        return handler

    def listing(kind: Kind):
        async def handler(
            project_id: str,
            page_size: int = 50,
            x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
            x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        ):
            if not 1 <= page_size <= 100:
                raise ValidationError("page_size must be between 1 and 100")
            scope = read_scope(project_id, x_tenant_id, x_workspace_id)
            records = service.store.list(kind, scope)
            return {
                "items": [record.public() for record in records[:page_size]],
                "page": {
                    "next_page_token": None,
                    "page_size": page_size,
                    "has_more": len(records) > page_size,
                },
                "correlation_id": None,
            }

        return handler

    for path, kind in {
        "activities": Kind.ACTIVITY,
        "work-logs": Kind.WORK_LOG,
        "decisions": Kind.DECISION,
        "issues": Kind.ISSUE,
        "tasks": Kind.TASK,
        "changesets": Kind.CHANGESET,
        "review-threads": Kind.REVIEW_THREAD,
        "review-comments": Kind.REVIEW_COMMENT,
        "discussion-comments": Kind.DISCUSSION_COMMENT,
        "work-labels": Kind.WORK_LABEL,
    }.items():
        api.post("/api/v1/projects/{project_id}/" + path, operation_id="create_" + kind.value)(post(kind))
        api.get("/api/v1/projects/{project_id}/" + path, operation_id="list_" + kind.value)(listing(kind))

    def transition_route(kind: Kind, field: str):
        async def handler(
            project_id: str,
            record_id: str,
            body: TransitionTaskStateRequest,
            idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
            x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
            x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
            x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
            x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
        ):
            scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
            record = service.transition(
                scope,
                actor,
                correlation_id,
                idempotency_key or "",
                record_id,
                body.status,
                body.reason,
                body.expected_version,
                kind,
            )
            return {field: record.public(), "correlation_id": correlation_id}

        return handler

    api.post("/api/v1/projects/{project_id}/tasks/{record_id}:transition", operation_id="transition_task_state")(
        transition_route(Kind.TASK, "task")
    )
    api.post("/api/v1/projects/{project_id}/issues/{record_id}:transition", operation_id="transition_issue_state")(
        transition_route(Kind.ISSUE, "issue")
    )
    api.post("/api/v1/projects/{project_id}/decisions/{record_id}:transition", operation_id="transition_decision_state")(
        transition_route(Kind.DECISION, "decision")
    )
    api.post("/api/v1/projects/{project_id}/changesets/{record_id}:transition", operation_id="transition_changeset_state")(
        transition_route(Kind.CHANGESET, "changeset")
    )

    @api.post("/api/v1/projects/{project_id}/changesets/{record_id}:approve", operation_id="approve_changeset")
    async def approve_changeset(
        project_id: str,
        record_id: str,
        body: TransitionTaskStateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        record = service.approve_changeset(
            scope,
            actor,
            correlation_id,
            idempotency_key or "",
            record_id,
            reason=body.reason,
            version=body.expected_version,
        )
        return {"changeset": record.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/decisions/{decision_id}:supersede", operation_id="supersede_decision")
    async def supersede_decision(
        project_id: str,
        decision_id: str,
        body: CreateRecordRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        decision = service.supersede(scope, actor, correlation_id, idempotency_key or "", decision_id, body.model_dump(exclude_none=True))
        return {"decision": decision.public(), "correlation_id": correlation_id}

    @api.get("/api/v1/projects/{project_id}/timeline", operation_id="get_timeline")
    async def timeline(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {
            "items": [record.public() for record in service.timeline(scope)],
            "page": {"next_page_token": None, "page_size": 100, "has_more": False},
            "correlation_id": None,
        }

    @api.get("/api/v1/projects/{project_id}/task-board", operation_id="get_task_board")
    async def task_board(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"board": service.task_board(read_scope(project_id, x_tenant_id, x_workspace_id)), "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/decision-history", operation_id="get_decision_history")
    async def decision_history(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [record.public() for record in service.decision_history(scope)], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/open-issues", operation_id="list_open_issues")
    async def open_issues(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [record.public() for record in service.open_issues(scope)], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/related-work", operation_id="find_related_work")
    async def related_work(
        project_id: str,
        correlation_id: str | None = None,
        entity_id: str | None = None,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [record.public() for record in service.find_related_work(scope, correlation_id, entity_id)], "correlation_id": correlation_id}

    @api.get("/api/v1/projects/{project_id}/evidence-bundles/{evidence_ref}", operation_id="get_evidence_bundle")
    async def evidence_bundle(
        project_id: str,
        evidence_ref: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [record.public() for record in service.evidence_bundle(scope, evidence_ref)], "correlation_id": None}

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
