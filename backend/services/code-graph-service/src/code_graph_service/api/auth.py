"""Bearer auth for content-push HTTP endpoints (ingest-push / file-hashes)."""

from __future__ import annotations

import hmac
import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from usage_profile.mcp_tokens import extract_bearer, verify_connect_token

from .common import is_loopback_request

_TOKEN_ENVS = (
    "ASTLOOM_CODE_GRAPH_HTTP_TOKEN",
    "ASTLOOM_CONNECT_TOKEN",
    "ASTLOOM_GRAPH_HTTP_TOKEN",
)


def configured_graph_http_token() -> str:
    for key in _TOKEN_ENVS:
        value = str(os.environ.get(key) or "").strip()
        if value:
            return value
    return ""


def require_content_push_http_auth(
    request: Request,
    project_id: str = "",
    x_tenant_id: str = Header(default=""),
    x_workspace_id: str = Header(default=""),
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Enforce bearer auth for LAN content-push routes.

    - ``as1.*`` access token (astloom_auth / connect bootstrap) → verified via
      HMAC + scope claims, preferred path.
    - Static token configured → Bearer must match (constant-time), lab fallback.
    - Neither configured → loopback only (dogfood / local unit tests).
    """
    bearer = extract_bearer(authorization)
    if bearer.startswith("as1."):
        try:
            verify_connect_token(
                bearer,
                tenant_id=x_tenant_id or None,
                workspace_id=x_workspace_id or None,
                project_id=project_id or None,
            )
            return
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    expected = configured_graph_http_token()
    if not expected:
        if is_loopback_request(request):
            return
        host = (request.client.host if request.client else "") or ""
        # Starlette TestClient default peer name.
        if host in {"testclient", "testserver"}:
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "content-push HTTP requires ASTLOOM_CODE_GRAPH_HTTP_TOKEN "
                "(or ASTLOOM_CONNECT_TOKEN) when not on loopback"
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not bearer or not hmac.compare_digest(bearer, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


ContentPushHttpAuth = Annotated[None, Depends(require_content_push_http_auth)]
