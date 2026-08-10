from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .bootstrap import ServiceContainer, build_container
from .core import AdapterError, AdapterService, Scope, ValidationError


class ConnectorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: str
    name: str
    capabilities: list[str]
    auth_profile: str
    trust_level: str = "standard"
    credential: str = "unset"
    vendor_schema_version: str = "1.0.0"
    field_map: dict[str, str] = Field(default_factory=dict)
    status_map: dict[str, str] = Field(default_factory=dict)
    reopen_policy: str = "allow_remote"
    unknown_status_policy: str = "reject"
    fallback_status: str = "open"
    mapping_version: int = Field(default=1, ge=1)


class CredentialRequest(BaseModel):
    credential: str


class SubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    subscriber_type: str
    endpoint: str
    filter_intents: list[str] = Field(default_factory=list)
    filter_domains: list[str] = Field(default_factory=list)
    fail_mode: str = "none"


class VendorEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    vendor_payload: dict[str, Any]


class PublishRequest(BaseModel):
    message: dict[str, Any]


class ReplayRequest(BaseModel):
    channel: str | None = None


class TicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    title: str
    department: str
    external_ref: str | None = None
    source_event_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    description_summary: str | None = Field(default=None, max_length=4000)
    priority: str | None = Field(default=None, max_length=100)
    severity: str | None = Field(default=None, max_length=100)
    assignee_ref: str | None = Field(default=None, max_length=500)
    due_at: str | None = None
    labels: list[str] = Field(default_factory=list)
    remote_url: str | None = Field(default=None, max_length=2048)
    extension: dict[str, Any] = Field(default_factory=dict)


class SyncStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    expected_version: int = Field(ge=1)
    external_updated_at: str
    source: str = "manual"
    reason: str | None = Field(default=None, max_length=2000)


class RetryDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=2000)


class DispatchResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    dispatch_status: str
    remote_url: str | None = Field(default=None, max_length=2048)
    external_ref: str | None = Field(default=None, max_length=500)
    error: str | None = Field(default=None, max_length=2000)


class PushStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    status: str | None = Field(default=None, max_length=100)


class ContextInjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_ref: str
    role: str = "tool"
    sensitivity_clearance: str = "public"
    task_assigned: bool = True
    tenant_id: str | None = None
    project_id: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)


def build_app(
    service: AdapterService | None = None,
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
    api = FastAPI(title="Astloom Adapter / Interop API", version="1.0.0")
    api.state.container = container

    @api.exception_handler(AdapterError)
    async def adapter_error(_: Request, exc: AdapterError):
        status_code = 400 if exc.category == "validation_error" else 409 if exc.category == "conflict_error" else 404
        return JSONResponse(
            {
                "error": {
                    "error_code": exc.code,
                    "category": exc.category,
                    "message": exc.message,
                    "retryable": False,
                    "correlation_id": None,
                    "details": exc.details,
                    "documentation_ref": "docs/05-interoperability-ecosystem",
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
                    "documentation_ref": "docs/05-interoperability-ecosystem",
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

    @api.post("/api/v1/projects/{project_id}/connectors", operation_id="register_connector")
    async def register_connector(
        project_id: str,
        body: ConnectorRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        connector = service.register_connector(scope, actor, correlation_id, idempotency_key or "", body.model_dump())
        return {"connector": connector.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/connectors/{connector_id}:validate", operation_id="validate_connector")
    async def validate_connector(
        project_id: str,
        connector_id: str,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        connector = service.validate_connector(scope, actor, correlation_id, idempotency_key or "", connector_id)
        return {"connector": connector.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/connectors/{connector_id}:rotate-credential", operation_id="rotate_connector_credential")
    async def rotate_credential(
        project_id: str,
        connector_id: str,
        body: CredentialRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        connector = service.rotate_credential(scope, actor, correlation_id, idempotency_key or "", connector_id, body.credential)
        return {"connector": connector.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/subscriptions", operation_id="create_subscription")
    async def subscribe(
        project_id: str,
        body: SubscribeRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        subscription = service.subscribe(scope, actor, correlation_id, idempotency_key or "", body.model_dump())
        return {"subscription": subscription.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/vendor-events:normalize", operation_id="normalize_vendor_event")
    async def normalize(
        project_id: str,
        body: VendorEventRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        result = service.normalize_vendor_event(scope, actor, correlation_id, idempotency_key or "", body.connector_id, body.vendor_payload)
        return {**result, "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/agent-events", operation_id="publish_agent_event")
    async def publish(
        project_id: str,
        body: PublishRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        result = service.publish_agent_event(scope, actor, correlation_id, idempotency_key or "", body.message)
        return {**result, "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/broker:replay", operation_id="replay_broker_events")
    async def replay(
        project_id: str,
        body: ReplayRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        result = service.replay(scope, actor, correlation_id, idempotency_key or "", body.channel)
        return {**result, "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/external-tickets", operation_id="create_external_ticket")
    async def create_ticket(
        project_id: str,
        body: TicketRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        ticket = service.create_external_ticket(scope, actor, correlation_id, idempotency_key or "", body.model_dump(exclude_none=True))
        return {"ticket": ticket.public(), "correlation_id": correlation_id}

    @api.get("/api/v1/projects/{project_id}/external-tickets", operation_id="list_external_tickets")
    async def list_external_tickets(
        project_id: str,
        connector_id: str | None = None,
        status: str | None = None,
        external_ref: str | None = None,
        department: str | None = None,
        updated_after: str | None = None,
        page_size: int = Query(default=50, ge=1, le=100),
        page_token: str | None = None,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        items, next_page_token = service.list_external_tickets(
            scope,
            connector_id=connector_id,
            status=status,
            external_ref=external_ref,
            department=department,
            updated_after=updated_after,
            page_size=page_size,
            page_token=page_token,
        )
        return {
            "items": [item.public() for item in items],
            "next_page_token": next_page_token,
            "correlation_id": None,
        }

    @api.get("/api/v1/projects/{project_id}/external-tickets/{ticket_id}", operation_id="get_external_ticket")
    async def get_external_ticket(
        project_id: str,
        ticket_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"ticket": service.get_external_ticket(scope, ticket_id).public(), "correlation_id": None}

    @api.post("/api/v1/projects/{project_id}/external-tickets/{ticket_id}:sync-status", operation_id="sync_external_status")
    async def sync_status(
        project_id: str,
        ticket_id: str,
        body: SyncStatusRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        ticket = service.sync_external_status(
            scope,
            actor,
            correlation_id,
            idempotency_key or "",
            ticket_id,
            body.status,
            body.expected_version,
            body.external_updated_at,
            body.source,
            body.reason,
        )
        return {"ticket": ticket.public(), "correlation_id": correlation_id}

    @api.post(
        "/api/v1/projects/{project_id}/external-tickets/{ticket_id}:retry-dispatch",
        operation_id="retry_external_ticket_dispatch",
    )
    async def retry_external_ticket_dispatch(
        project_id: str,
        ticket_id: str,
        body: RetryDispatchRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        ticket = service.retry_external_ticket_dispatch(
            scope,
            actor,
            correlation_id,
            idempotency_key or "",
            ticket_id,
            body.expected_version,
            body.reason,
        )
        return {"ticket": ticket.public(), "correlation_id": correlation_id}

    @api.post(
        "/api/v1/projects/{project_id}/external-tickets/{ticket_id}:record-dispatch-result",
        operation_id="record_external_ticket_dispatch_result",
    )
    async def record_external_ticket_dispatch_result(
        project_id: str,
        ticket_id: str,
        body: DispatchResultRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        ticket = service.record_external_ticket_dispatch_result(
            scope,
            actor,
            correlation_id,
            idempotency_key or "",
            ticket_id,
            body.expected_version,
            body.dispatch_status,
            body.remote_url,
            body.external_ref,
            body.error,
        )
        return {"ticket": ticket.public(), "correlation_id": correlation_id}

    @api.post(
        "/api/v1/projects/{project_id}/external-tickets/{ticket_id}:push-status",
        operation_id="push_external_ticket_status",
    )
    async def push_external_ticket_status(
        project_id: str,
        ticket_id: str,
        body: PushStatusRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        ticket = service.push_external_ticket_status(
            scope,
            actor,
            correlation_id,
            idempotency_key or "",
            ticket_id,
            body.expected_version,
            body.status,
        )
        return {"ticket": ticket.public(), "correlation_id": correlation_id}

    @api.post("/api/v1/projects/{project_id}/context:inject", operation_id="inject_context")
    async def inject_context(
        project_id: str,
        body: ContextInjectRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
        x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    ):
        scope, actor, correlation_id = ctx(project_id, x_tenant_id, x_workspace_id, x_actor_id, x_correlation_id)
        result = service.inject_context(scope, actor, correlation_id, idempotency_key or "", body.model_dump(exclude_none=True))
        return {**result, "correlation_id": correlation_id}

    @api.get("/api/v1/projects/{project_id}/capabilities", operation_id="discover_capabilities")
    async def capabilities(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"items": service.discover_capabilities(read_scope(project_id, x_tenant_id, x_workspace_id)), "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/connectors/{connector_id}/health", operation_id="get_connector_health")
    async def health(
        project_id: str,
        connector_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        return {"health": service.get_connector_health(read_scope(project_id, x_tenant_id, x_workspace_id), connector_id), "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/subscriptions", operation_id="list_subscriptions")
    async def list_subscriptions(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [item.public() for item in service.list_subscriptions(scope)], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/dead-letters", operation_id="get_dead_letter_queue")
    async def dead_letters(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [item.public() for item in service.get_dead_letter_queue(scope)], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/connectors/{connector_id}/mappings", operation_id="get_adapter_mapping")
    async def mappings(
        project_id: str,
        connector_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [item.public() for item in service.get_adapter_mapping(scope, connector_id)], "correlation_id": None}

    @api.get("/api/v1/projects/{project_id}/department-tasks", operation_id="list_department_tasks")
    async def department_tasks(
        project_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    ):
        scope = read_scope(project_id, x_tenant_id, x_workspace_id)
        return {"items": [item.public() for item in service.list_department_tasks(scope)], "correlation_id": None}

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
