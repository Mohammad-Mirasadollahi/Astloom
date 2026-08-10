"""ADR 48 reconcile and Feature 49 LSP edit-session HTTP routes."""

from typing import Any

from fastapi import FastAPI, Header

from ..core import CodeGraphService
from .common import scope_from
from .schemas import IdeRenameRequest, IdeSessionPositionRequest, ReconcileAfterEditRequest


def register(api: FastAPI, service: CodeGraphService) -> None:
    @api.post("/api/v1/projects/{project_id}/graph/reconcile-after-edit")
    async def reconcile_after_edit(
        project_id: str,
        body: ReconcileAfterEditRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """ADR 48: mark edited paths pending; optional AST re-ingest via sync_repo."""
        scope = scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        return service.reconcile_after_edit(
            list(body.file_paths or []),
            scope=scope if body.run_sync else None,
            root_path=body.root_path,
            actor_id=body.actor_id,
            correlation_id=body.correlation_id or "",
            idempotency_key=body.idempotency_key or "",
            run_sync=body.run_sync,
        )

    @api.post("/api/v1/projects/{project_id}/graph/edit-session/references")
    async def ide_references(
        project_id: str,
        body: IdeSessionPositionRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _ = scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        return service.ide_references(
            root_path=body.root_path,
            file_path=body.file_path,
            line=body.line,
            character=body.character,
            language=body.language or "",
        )

    @api.post("/api/v1/projects/{project_id}/graph/edit-session/definition")
    async def ide_definition(
        project_id: str,
        body: IdeSessionPositionRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _ = scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        return service.ide_definition(
            root_path=body.root_path,
            file_path=body.file_path,
            line=body.line,
            character=body.character,
            language=body.language or "",
        )

    @api.post("/api/v1/projects/{project_id}/graph/edit-session/rename")
    async def ide_rename(
        project_id: str,
        body: IdeRenameRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        scope = scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        return service.ide_rename(
            root_path=body.root_path,
            file_path=body.file_path,
            line=body.line,
            character=body.character,
            new_name=body.new_name,
            language=body.language or "",
            apply=body.apply,
            scope=scope,
            actor_id=body.actor_id,
            correlation_id=body.correlation_id or "",
            idempotency_key=body.idempotency_key or "",
            run_sync=body.run_sync,
        )
