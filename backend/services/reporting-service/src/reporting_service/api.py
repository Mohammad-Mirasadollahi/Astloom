from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from .bootstrap import ServiceContainer, build_container
from .core import ReportingError, ReportingService, Scope


def build_app(
    service: ReportingService | None = None,
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
    api = FastAPI(title="Astloom Reporting API", version="1.0.0")
    api.state.container = container

    @api.exception_handler(ReportingError)
    async def domain_error(_: Request, exc: ReportingError):
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
                    "documentation_ref": "backend/services/reporting-service/docs/phase-reporting-api-contract.md",
                }
            },
            status_code=status_code,
        )

    @api.post("/api/v1/projects/{project_id}/kpi-samples")
    async def record_sample(
        project_id: str,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        sample = service.record_sample(
            Scope(x_tenant_id, x_workspace_id, project_id),
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body,
        )
        return {"sample": sample}

    @api.get("/api/v1/projects/{project_id}/kpi-compare")
    async def compare(
        project_id: str,
        kpi_name: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        report = service.compare(Scope(x_tenant_id, x_workspace_id, project_id), kpi_name)
        return {"report": report}

    @api.get("/api/v1/projects/{project_id}/kpi-benefit-summary")
    async def benefit_summary(
        project_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        summary = service.benefit_summary(Scope(x_tenant_id, x_workspace_id, project_id))
        return {"summary": summary}

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
