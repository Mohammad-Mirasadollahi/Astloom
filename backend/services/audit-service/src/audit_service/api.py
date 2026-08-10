from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from .bootstrap import ServiceContainer, build_container
from .core import AuditError, AuditService, Scope


def build_app(
    service: AuditService | None = None,
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
    api = FastAPI(title="Astloom Audit API", version="1.0.0")
    api.state.container = container

    @api.exception_handler(AuditError)
    async def domain_error(_: Request, exc: AuditError):
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
                    "documentation_ref": "backend/services/audit-service/docs/phase-audit-api-contract.md",
                }
            },
            status_code=status_code,
        )

    @api.post("/api/v1/projects/{project_id}/audit/events")
    async def record_event(
        project_id: str,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        event = service.record_event(
            Scope(x_tenant_id, x_workspace_id, project_id),
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body,
        )
        return {"event": event}

    @api.get("/api/v1/projects/{project_id}/audit/timeline")
    async def timeline(
        project_id: str,
        correlation_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        items = service.timeline(Scope(x_tenant_id, x_workspace_id, project_id), correlation_id)
        return {"items": items, "read_model_id": "audit.timeline"}

    @api.get("/api/v1/projects/{project_id}/audit/events/{event_id}")
    async def get_event(
        project_id: str,
        event_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        event = service.get_event(Scope(x_tenant_id, x_workspace_id, project_id), event_id)
        return {"event": event}

    @api.get("/api/v1/projects/{project_id}/audit/evidence")
    async def evidence_trail(
        project_id: str,
        entity_ref: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        items = service.evidence_trail(Scope(x_tenant_id, x_workspace_id, project_id), entity_ref)
        return {"items": items}

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
