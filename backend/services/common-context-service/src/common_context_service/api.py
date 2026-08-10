from typing import Any
from uuid import uuid4

from fastapi import Body, FastAPI, Header, Request
from fastapi.responses import JSONResponse

from .bootstrap import ServiceContainer, build_container
from .core import CommonContextService, CommonContextError, Scope, project_scope, resolve_authoring_scope


def _authoring_scope(
    project_id: str,
    *,
    tenant_id: str,
    workspace_id: str,
    actor_id: str,
    body: dict[str, Any],
) -> Scope:
    return resolve_authoring_scope(
        tenant_id,
        workspace_id,
        project_id,
        scope_kind=str(body.get("scope_kind") or "project"),
        user_id=str(body.get("user_id") or "").strip() or None,
        actor_id=actor_id,
    )


def _item_scope_from_headers(
    project_id: str,
    *,
    tenant_id: str,
    workspace_id: str,
    item: dict[str, Any] | None = None,
    scope_kind: str | None = None,
    user_id: str | None = None,
    actor_id: str | None = None,
) -> Scope:
    kind = scope_kind or (item or {}).get("scope_kind") or "project"
    uid = user_id or (item or {}).get("user_id") or actor_id
    return resolve_authoring_scope(
        tenant_id,
        workspace_id,
        project_id,
        scope_kind=str(kind),
        user_id=str(uid).strip() if uid else None,
        actor_id=actor_id,
    )


def build_app(
    service: CommonContextService | None = None,
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
    api = FastAPI(title="Astloom Common Context API", version="1.0.0")
    api.state.container = container

    @api.exception_handler(CommonContextError)
    async def domain_error(_: Request, exc: CommonContextError):
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
                    "documentation_ref": "backend/services/common-context-service/docs/phase-common-context-api-contract.md",
                }
            },
            status_code=status_code,
        )

    @api.post("/api/v1/projects/{project_id}/common-items")
    async def propose_item(
        project_id: str,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        scope = _authoring_scope(
            project_id,
            tenant_id=x_tenant_id,
            workspace_id=x_workspace_id,
            actor_id=x_actor_id,
            body=body,
        )
        item = service.propose_item(
            scope,
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body,
        )
        return {"item": item}

    @api.post("/api/v1/projects/{project_id}/common-items/{item_id}:approve")
    async def approve_item(
        project_id: str,
        item_id: str,
        body: dict[str, Any] = Body(default_factory=dict),
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        scope = _item_scope_from_headers(
            project_id,
            tenant_id=x_tenant_id,
            workspace_id=x_workspace_id,
            scope_kind=str(body.get("scope_kind") or "project"),
            user_id=str(body.get("user_id") or "").strip() or None,
            actor_id=x_actor_id,
        )
        item = service.approve_item(scope, item_id, x_actor_id)
        return {"item": item}

    @api.post("/api/v1/projects/{project_id}/common-items/{item_id}:suppress")
    async def suppress_item(
        project_id: str,
        item_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        body: dict[str, Any] = Body(default_factory=dict),
    ) -> dict[str, Any]:
        reason = str(body.get("reason") or "")
        scope = _item_scope_from_headers(
            project_id,
            tenant_id=x_tenant_id,
            workspace_id=x_workspace_id,
            scope_kind=str(body.get("scope_kind") or "project"),
            user_id=str(body.get("user_id") or "").strip() or None,
            actor_id=x_actor_id,
        )
        item = service.suppress_item(scope, item_id, x_actor_id, reason)
        return {"item": item}

    @api.post("/api/v1/projects/{project_id}/common-items/{item_id}:reject")
    async def reject_item(
        project_id: str,
        item_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        body: dict[str, Any] = Body(default_factory=dict),
    ) -> dict[str, Any]:
        reason = str(body.get("reason") or "")
        scope = _item_scope_from_headers(
            project_id,
            tenant_id=x_tenant_id,
            workspace_id=x_workspace_id,
            scope_kind=str(body.get("scope_kind") or "project"),
            user_id=str(body.get("user_id") or "").strip() or None,
            actor_id=x_actor_id,
        )
        item = service.reject_item(scope, item_id, x_actor_id, reason)
        return {"item": item}

    @api.get("/api/v1/projects/{project_id}/common-context/bundle")
    async def resolve_bundle(
        project_id: str,
        token_budget: int = 800,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        bundle = service.resolve_bundle(project_scope(x_tenant_id, x_workspace_id, project_id), token_budget)
        return {"bundle": bundle}

    @api.post("/api/v1/projects/{project_id}/guidance/resolve")
    async def resolve_guidance(
        project_id: str,
        body: dict[str, Any] = Body(default_factory=dict),
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        scope = project_scope(x_tenant_id, x_workspace_id, project_id)
        user_id = str(body.get("user_id") or x_actor_id or "").strip() or None
        bundle = service.resolve_guidance(
            scope,
            task_summary=str(body.get("task_summary") or ""),
            workflow_type=str(body.get("workflow_type") or "coding"),
            include_skill_bodies=bool(body.get("include_skill_bodies") or False),
            budget_overrides=body.get("budget_overrides") if isinstance(body.get("budget_overrides"), dict) else None,
            include_general_common_context=bool(body.get("include_general_common_context") or False),
            user_id=user_id,
            task_overrides=body.get("task_overrides") if isinstance(body.get("task_overrides"), dict) else None,
        )
        return {"bundle": bundle}

    @api.get("/api/v1/projects/{project_id}/guidance/skills")
    async def list_skills(
        project_id: str,
        query: str = "",
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        skills = service.list_skills(
            project_scope(x_tenant_id, x_workspace_id, project_id),
            query=query,
            user_id=x_actor_id,
        )
        return {"skills": skills}

    @api.get("/api/v1/projects/{project_id}/guidance/skills/{skill_id}")
    async def get_skill_by_id(
        project_id: str,
        skill_id: str,
        bundle_id: str | None = None,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        skill = service.get_skill(
            project_scope(x_tenant_id, x_workspace_id, project_id),
            skill_id=skill_id,
            bundle_id=bundle_id,
            user_id=x_actor_id,
        )
        return {"skill": skill}

    @api.post("/api/v1/projects/{project_id}/guidance/skills:get")
    async def get_skill(
        project_id: str,
        body: dict[str, Any] = Body(default_factory=dict),
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        user_id = str(body.get("user_id") or x_actor_id or "").strip() or None
        skill = service.get_skill(
            project_scope(x_tenant_id, x_workspace_id, project_id),
            skill_id=str(body.get("skill_id") or "").strip() or None,
            name=str(body.get("name") or "").strip() or None,
            bundle_id=str(body.get("bundle_id") or "").strip() or None,
            user_id=user_id,
        )
        return {"skill": skill}

    @api.post("/api/v1/projects/{project_id}/guidance/seed-mcp-first")
    async def seed_mcp_first(
        project_id: str,
        body: dict[str, Any] = Body(default_factory=dict),
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        scope_kind = str(body.get("scope_kind") or "project")
        scope = resolve_authoring_scope(
            x_tenant_id,
            x_workspace_id,
            project_id,
            scope_kind=scope_kind,
            actor_id=x_actor_id,
        )
        result = service.ensure_mcp_first_seed(
            scope,
            x_actor_id,
            x_correlation_id or str(uuid4()),
        )
        return result

    @api.post("/api/v1/projects/{project_id}/guidance/export")
    async def export_guidance(
        project_id: str,
        body: dict[str, Any] = Body(default_factory=dict),
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        result = service.export_guidance_layout(
            project_scope(x_tenant_id, x_workspace_id, project_id),
            layout=str(body.get("layout") or "cursor"),
            dry_run=bool(body.get("dry_run", True)),
            user_id=str(body.get("user_id") or x_actor_id or "").strip() or None,
            target_root=str(body.get("target_root") or "").strip() or None,
            force=bool(body.get("force", False)),
        )
        return {"export": result}

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
