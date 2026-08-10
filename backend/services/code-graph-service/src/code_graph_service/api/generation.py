"""Generation-context and generated-code validation HTTP routes."""

from typing import Any

from fastapi import FastAPI, Header

from ..core import CodeGraphService
from .common import scope_from
from .schemas import GenerationContextRequest, ValidateGeneratedRequest


def register(api: FastAPI, service: CodeGraphService) -> None:
    @api.post("/api/v1/projects/{project_id}/graph/generation-context")
    async def generation_context(
        project_id: str,
        body: GenerationContextRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.build_generation_context(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            body.seed_symbol_id,
            body.max_symbols,
        )

    @api.post("/api/v1/projects/{project_id}/graph/generated-code:validate")
    async def validate_generated(
        project_id: str,
        body: ValidateGeneratedRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.validate_generated_code(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            body.source,
        )
