from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from .bootstrap import ServiceContainer, build_container
from .core import IdentityAccessError, IdentityAccessService, Scope


def build_app(
    service: IdentityAccessService | None = None,
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
    api = FastAPI(title="Astloom Identity Access API", version="1.0.0")
    api.state.container = container

    @api.exception_handler(IdentityAccessError)
    async def domain_error(_: Request, exc: IdentityAccessError):
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
                    "documentation_ref": "backend/services/identity-access-service/docs/phase-identity-access-api-contract.md",
                }
            },
            status_code=status_code,
        )

    @api.post("/api/v1/projects/{project_id}/principals")
    async def upsert_principal(
        project_id: str,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        principal = service.upsert_principal(
            Scope(x_tenant_id, x_workspace_id, project_id),
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body,
        )
        return {"principal": principal}

    @api.post("/api/v1/projects/{project_id}/authorize")
    async def authorize(
        project_id: str,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        decision = service.authorize(
            Scope(x_tenant_id, x_workspace_id, project_id),
            str(body.get("subject") or ""),
            str(body.get("action") or ""),
            str(body.get("resource") or ""),
        )
        return {"decision": decision}

    @api.post("/api/v1/projects/{project_id}/principals/{principal_id}:revoke")
    async def revoke_principal(
        project_id: str,
        principal_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        principal = service.revoke_principal(
            Scope(x_tenant_id, x_workspace_id, project_id),
            principal_id,
            x_actor_id,
        )
        return {"principal": principal}

    @api.get("/api/v1/projects/{project_id}/principals")
    async def list_principals(
        project_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        items = service.list_principals(Scope(x_tenant_id, x_workspace_id, project_id))
        return {"items": items}

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
