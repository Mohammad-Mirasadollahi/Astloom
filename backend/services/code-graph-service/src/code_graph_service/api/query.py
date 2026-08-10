"""Symbol lookup, neighbors, semantic search, and store capability routes."""

from typing import Any

from fastapi import FastAPI, Header

from ..core import CodeGraphService
from .common import scope_from
from .schemas import SemanticSearchRequest


def register(api: FastAPI, service: CodeGraphService) -> None:
    @api.get("/api/v1/projects/{project_id}/graph/symbols/{symbol_id}")
    async def get_symbol(
        project_id: str,
        symbol_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        symbol = service.get_symbol(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            symbol_id,
        )
        return service._symbol_view(symbol)

    @api.get("/api/v1/projects/{project_id}/graph/symbols/{symbol_id}/neighbors")
    async def neighbors(
        project_id: str,
        symbol_id: str,
        rel_type: str | None = None,
        max_depth: int = 1,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.structural_query(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            symbol_id,
            rel_type,
            max_depth=max(1, min(max_depth, 5)),
        )

    @api.get("/api/v1/projects/{project_id}/graph/neo4j-capabilities")
    async def neo4j_capabilities(
        project_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _ = scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        store = service.store
        caps = getattr(store, "capabilities", None)
        if not callable(caps):
            return {
                "backend": type(store).__name__,
                "apoc": False,
                "gds": False,
                "fulltext": False,
            }
        return {"backend": type(store).__name__, **caps()}

    @api.post("/api/v1/projects/{project_id}/graph/search:semantic")
    async def semantic_search(
        project_id: str,
        body: SemanticSearchRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        hits = service.semantic_search(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            body.query,
            body.top_k,
        )
        return {"hits": hits}
