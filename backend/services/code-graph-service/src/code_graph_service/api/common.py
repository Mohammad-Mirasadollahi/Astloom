"""Shared HTTP helpers for code-graph route modules."""

from ipaddress import ip_address

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..core import CodeGraphError, Scope


def is_loopback_request(request: Request) -> bool:
    if request.client is None:
        return False
    try:
        return ip_address(request.client.host).is_loopback
    except ValueError:
        return False


def scope_from(
    project_id: str,
    tenant_id: str,
    workspace_id: str,
    project_group_id: str | None = None,
) -> Scope:
    return Scope(tenant_id, workspace_id, project_id, project_group_id)


def install_exception_handlers(api: FastAPI) -> None:
    @api.exception_handler(CodeGraphError)
    async def graph_error(_: Request, exc: CodeGraphError):
        if exc.category == "validation_error":
            status_code = 400
            retryable = False
        elif exc.category == "conflict_error":
            status_code = 409
            retryable = False
        elif exc.category == "capacity_error":
            status_code = 503
            retryable = True
        elif exc.category == "cancelled":
            status_code = 499
            retryable = False
        elif exc.code == "not_found":
            status_code = 404
            retryable = False
        else:
            status_code = 404
            retryable = False
        return JSONResponse(
            {
                "error": {
                    "error_code": exc.code,
                    "category": exc.category,
                    "message": exc.message,
                    "retryable": retryable,
                    "correlation_id": None,
                    "details": {},
                    "documentation_ref": "docs/07-code-knowledge-graph",
                }
            },
            status_code=status_code,
        )
