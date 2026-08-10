"""Bearer auth for connect HTTP routes (sources/ingest/status).

Access tokens are ``as1.*`` HMAC tokens minted via ``astloom_auth.mint_and_register_access_token``
(secret from ``ASTLOOM_MCP_TOKEN_SECRET`` / ``ASTLOOM_MCP_HTTP_TOKEN``). When no
secret is configured, connect routes stay open (dev/lab default) — matching the
content-push HTTP auth fallback in code-graph-service. Signature/scope is verified
first, then liveness (not revoked/expired) against ``app.state.token_registry``.
"""

from __future__ import annotations

from typing import Annotated

from astloom_auth.tokens import verify_registered_access_token
from fastapi import Depends, Header, HTTPException, Request, status
from usage_profile.mcp_tokens import extract_bearer, token_secret


def require_connect_bearer_auth(
    request: Request,
    project_id: str,
    x_tenant_id: str = Header(),
    x_workspace_id: str = Header(),
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not token_secret():
        return
    provided = extract_bearer(authorization)
    if not provided:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization Bearer access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        verify_registered_access_token(
            provided,
            request.app.state.token_registry,
            tenant_id=x_tenant_id,
            workspace_id=x_workspace_id,
            project_id=project_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


ConnectBearerAuth = Annotated[None, Depends(require_connect_bearer_auth)]
