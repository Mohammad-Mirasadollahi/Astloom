from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse

from .bootstrap import ServiceContainer, build_container
from .core import OrchestrationError, OrchestrationService, Scope


def build_app(
    service: OrchestrationService | None = None,
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
    api = FastAPI(title="Astloom Orchestration API", version="1.0.0")
    api.state.container = container

    @api.exception_handler(OrchestrationError)
    async def domain_error(_: Request, exc: OrchestrationError):
        status_code = 400 if exc.category == "validation_error" else 409 if exc.category == "conflict_error" else 404
        return JSONResponse(
            {
                "error": {
                    "error_code": exc.code,
                    "category": exc.category,
                    "message": exc.message,
                    "retryable": False,
                    "correlation_id": None,
                    "details": getattr(exc, "details", {}) or {},
                    "documentation_ref": "backend/services/orchestration-service/docs/phase-orchestration-api-contract.md",
                }
            },
            status_code=status_code,
        )

    @api.post("/api/v1/projects/{project_id}/work-batches")
    async def open_batch(
        project_id: str,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        batch = service.open_work_batch(
            Scope(x_tenant_id, x_workspace_id, project_id),
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body,
        )
        return {"batch": batch}

    @api.post("/api/v1/projects/{project_id}/assignments")
    async def route_task(
        project_id: str,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        assignment = service.route_task(
            Scope(x_tenant_id, x_workspace_id, project_id),
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body,
        )
        return {"assignment": assignment}

    @api.post("/api/v1/projects/{project_id}/work-batches/{batch_id}:close")
    async def close_batch(
        project_id: str,
        batch_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        batch = service.close_work_batch(Scope(x_tenant_id, x_workspace_id, project_id), batch_id)
        return {"batch": batch}

    @api.post("/api/v1/projects/{project_id}/assignments/{assignment_id}:complete")
    async def complete_assignment(
        project_id: str,
        assignment_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        assignment = service.complete_assignment(
            Scope(x_tenant_id, x_workspace_id, project_id),
            assignment_id,
            x_actor_id,
        )
        return {"assignment": assignment}

    @api.get("/api/v1/projects/{project_id}/assignments")
    async def list_assignments(
        project_id: str,
        batch_id: str | None = None,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        items = service.list_assignments(Scope(x_tenant_id, x_workspace_id, project_id), batch_id=batch_id)
        return {"items": items}

    @api.post("/api/v1/projects/{project_id}/agent-tickets")
    async def create_agent_ticket(
        project_id: str,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        ticket = service.create_agent_ticket(
            Scope(x_tenant_id, x_workspace_id, project_id),
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body,
        )
        return {"ticket": ticket}

    @api.get("/api/v1/projects/{project_id}/agent-tickets")
    async def list_agent_tickets(
        project_id: str,
        status: str | None = Query(default=None),
        agent_id: str | None = Query(default=None),
        task_id: str | None = Query(default=None),
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        items = service.list_agent_tickets(
            Scope(x_tenant_id, x_workspace_id, project_id),
            status=status,
            agent_id=agent_id,
            task_id=task_id,
        )
        return {"items": items}

    @api.get("/api/v1/projects/{project_id}/agent-tickets/{agent_ticket_id}")
    async def get_agent_ticket(
        project_id: str,
        agent_ticket_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        ticket = service.get_agent_ticket(Scope(x_tenant_id, x_workspace_id, project_id), agent_ticket_id)
        return {"ticket": ticket}

    def _transition(command: str):
        async def handler(
            project_id: str,
            agent_ticket_id: str,
            body: dict[str, Any],
            x_tenant_id: str = Header(),
            x_workspace_id: str = Header(),
            x_actor_id: str = Header(),
            x_correlation_id: str | None = Header(default=None),
            idempotency_key: str = Header(alias="Idempotency-Key"),
        ) -> dict[str, Any]:
            ticket = service.transition_agent_ticket(
                Scope(x_tenant_id, x_workspace_id, project_id),
                x_actor_id,
                x_correlation_id or str(uuid4()),
                idempotency_key,
                agent_ticket_id,
                command,
                body,
            )
            return {"ticket": ticket}

        return handler

    for command in ("claim", "start", "block", "submit-review", "complete", "fail", "cancel", "reassign"):
        api.add_api_route(
            f"/api/v1/projects/{{project_id}}/agent-tickets/{{agent_ticket_id}}:{command}",
            _transition(command),
            methods=["POST"],
            name=f"agent_ticket_{command.replace('-', '_')}",
        )

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
