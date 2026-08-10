"""Wave intelligence: explore, impact, hybrid search, freshness, pending sync."""

from typing import Any

from fastapi import FastAPI, Header

from ..core import CodeGraphService
from ..domain.errors import ValidationError
from .common import scope_from
from .schemas import (
    ArchitectureOverviewRequest,
    CallersRequest,
    CallPathRequest,
    CommunityRequest,
    DetectChangesRequest,
    ExploreRequest,
    HybridSearchRequest,
    ImpactRequest,
    PendingSyncRequest,
    SymbolPathRequest,
)


def register(api: FastAPI, service: CodeGraphService) -> None:
    @api.post("/api/v1/projects/{project_id}/graph/explore")
    async def explore(
        project_id: str,
        body: ExploreRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.explore(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            body.query,
            top_k=body.top_k,
            max_depth=body.max_depth,
            budget_chars=body.budget_chars,
        )

    @api.post("/api/v1/projects/{project_id}/graph/detect-changes")
    async def detect_changes(
        project_id: str,
        body: DetectChangesRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.detect_changes(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            body.changed_files,
            include_flows=body.include_flows,
        )

    @api.post("/api/v1/projects/{project_id}/graph/architecture-overview")
    async def architecture_overview(
        project_id: str,
        body: ArchitectureOverviewRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.architecture_overview(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            top_n=body.top_n,
        )

    @api.post("/api/v1/projects/{project_id}/graph/symbols/{symbol_id}/callers")
    async def callers(
        project_id: str,
        symbol_id: str,
        body: CallersRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.callers(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            symbol_id,
            top_k=body.top_k,
            max_depth=body.max_depth,
            min_confidence=body.min_confidence,
            rel_types=body.rel_types,
        )

    @api.post("/api/v1/projects/{project_id}/graph/symbols/{symbol_id}/impact")
    async def impact(
        project_id: str,
        symbol_id: str,
        body: ImpactRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.impact_analysis(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            symbol_id,
            direction=body.direction,
            max_depth=body.max_depth,
            min_confidence=body.min_confidence,
            rel_types=body.rel_types,
            top_k=body.top_k,
        )

    @api.post("/api/v1/projects/{project_id}/graph/symbols/{symbol_id}/community")
    async def community(
        project_id: str,
        symbol_id: str,
        body: CommunityRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.community_of_symbol(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            symbol_id,
            member_limit=body.member_limit,
        )

    @api.post("/api/v1/projects/{project_id}/graph/symbols/{symbol_id}/call-path")
    async def call_path(
        project_id: str,
        symbol_id: str,
        body: CallPathRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.call_path_pack(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            symbol_id,
            max_depth=body.max_depth,
            max_nodes=body.max_nodes,
        )

    @api.post("/api/v1/projects/{project_id}/graph/path")
    async def symbol_path(
        project_id: str,
        body: SymbolPathRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.symbol_path(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            body.start_id,
            body.end_id,
            max_depth=body.max_depth,
        )

    @api.post("/api/v1/projects/{project_id}/graph/search:hybrid")
    async def hybrid_search(
        project_id: str,
        body: HybridSearchRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.hybrid_search(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            body.query,
            top_k=body.top_k,
        )

    @api.post("/api/v1/projects/{project_id}/graph/pending-sync")
    async def pending_sync(
        project_id: str,
        body: PendingSyncRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _ = scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        paths = list(body.file_paths or [])
        if body.file_path:
            paths.append(body.file_path)
        if len(paths) > 1:
            return service.mark_files_pending(paths)
        if len(paths) == 1:
            return service.mark_file_pending(paths[0])
        raise ValidationError("file_path or file_paths is required")

    @api.get("/api/v1/projects/{project_id}/graph/freshness")
    async def freshness(
        project_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _ = scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        return service.freshness_status()
