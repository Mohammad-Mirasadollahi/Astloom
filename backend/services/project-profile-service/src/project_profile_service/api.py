import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from astloom_auth import (
    InMemoryAccessTokenRegistry,
    PostgresAccessTokenRegistry,
    hash_secret,
    mint_and_register_access_token,
    revoke_access_token_in_scope,
    verify_secret,
)
from astloom_auth.token_registry import AccessTokenRegistry
from astloom_auth.tokens import DEFAULT_ACCESS_TTL_SECONDS
from usage_profile.mcp_tokens import verify_connect_token

from .bootstrap import ServiceContainer, build_container
from .core import ProjectProfileError, ProjectProfileService, Scope
from .http_auth import ConnectBearerAuth
from .rate_limit import InProcessRateLimiter

BOOTSTRAP_SECRET_ENV = "ASTLOOM_CONNECT_BOOTSTRAP_SECRET"
BOOTSTRAP_RATE_LIMIT_PER_MINUTE = 10
TOKEN_MINT_RATE_LIMIT_PER_MINUTE = 20


def _require_bootstrap_secret(secret_hash: str | None, body: dict[str, Any]) -> None:
    """No-op when no operator secret is configured (dev/lab default)."""
    if secret_hash is None:
        return
    provided = str(body.get("bootstrap_secret") or "")
    if not provided or not verify_secret(provided, secret_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bootstrap_secret is required",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _client_ip(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host or "unknown"


def _enforce_rate_limit(request: Request, limiter_attr: str) -> None:
    limiter = getattr(request.app.state, limiter_attr)
    if not limiter.allow(_client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
        )


def _read_ca_pem() -> str:
    data_root = os.environ.get("ASTLOOM_DATA_ROOT", "").strip()
    if not data_root:
        return ""
    try:
        return (Path(data_root) / "certs" / "ca.pem").read_text(encoding="utf-8")
    except OSError:
        return ""


def _attach_auth_material(
    result: dict[str, Any], scope: Scope, registry: AccessTokenRegistry
) -> dict[str, Any]:
    """Mint a long-lived scoped access token for the bootstrapped scope, best-effort.

    Minting requires ``ASTLOOM_MCP_TOKEN_SECRET`` (or ``ASTLOOM_MCP_HTTP_TOKEN``);
    when unset, the token is empty so bootstrap still succeeds (matches existing
    graceful degradation for the ``mcp`` block's connect token). No refresh token
    is issued — clients re-run bootstrap/connect once the access token expires.
    The token's SHA-256 hash (never the plaintext) is registered at rest so it
    can be checked for liveness/revocation on every subsequent request.
    """
    try:
        result["access_token"] = mint_and_register_access_token(
            registry,
            tenant_id=scope.tenant_id,
            workspace_id=scope.workspace_id,
            project_id=scope.project_id,
        )
        result["expires_in"] = DEFAULT_ACCESS_TTL_SECONDS
    except ValueError:
        result["access_token"] = ""
        result["expires_in"] = 0
    result["ca_pem"] = _read_ca_pem()
    return result


def _build_token_registry(container: ServiceContainer) -> AccessTokenRegistry:
    """Postgres when a DSN is available (container settings or env); else in-memory (unit tests)."""
    database_url = (container.settings.database_url if container.settings else "") or os.environ.get(
        "ASTLOOM_PROJECT_PROFILE_DATABASE_URL", ""
    ).strip()
    return PostgresAccessTokenRegistry(database_url) if database_url else InMemoryAccessTokenRegistry()


def build_app(
    service: ProjectProfileService | None = None,
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
    api = FastAPI(title="Astloom Project Profile API", version="1.0.0")
    api.state.container = container
    api.state.bootstrap_rate_limiter = InProcessRateLimiter(
        max_events=BOOTSTRAP_RATE_LIMIT_PER_MINUTE,
    )
    api.state.token_mint_rate_limiter = InProcessRateLimiter(
        max_events=TOKEN_MINT_RATE_LIMIT_PER_MINUTE,
    )
    api.state.token_registry = _build_token_registry(container)
    bootstrap_secret = os.environ.get(BOOTSTRAP_SECRET_ENV, "").strip()
    api.state.bootstrap_secret_hash = hash_secret(bootstrap_secret) if bootstrap_secret else None

    @api.exception_handler(ProjectProfileError)
    async def domain_error(_: Request, exc: ProjectProfileError):
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
                    "documentation_ref": "backend/services/project-profile-service/docs/phase-project-profile-api-contract.md",
                }
            },
            status_code=status_code,
        )

    @api.post("/api/v1/projects/{project_id}/profile")
    async def register_project(
        project_id: str,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        project = service.register_project(
            Scope(x_tenant_id, x_workspace_id, project_id),
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body,
        )
        return {"project": project}

    @api.get("/api/v1/projects/{project_id}/profile")
    async def get_project(
        project_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        project = service.get_project(Scope(x_tenant_id, x_workspace_id, project_id))
        return {"project": project}

    @api.patch("/api/v1/projects/{project_id}/profile")
    async def update_feature_profile(
        project_id: str,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        project = service.update_feature_profile(
            Scope(x_tenant_id, x_workspace_id, project_id),
            x_actor_id,
            body,
        )
        return {"project": project}

    @api.get("/api/v1/usage-profiles")
    async def list_usage_profiles(
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = (x_tenant_id, x_workspace_id, x_actor_id)
        return {"items": service.list_usage_profiles()}

    @api.post("/api/v1/projects/{project_id}/usage-profile:activate")
    async def activate_usage_profile(
        project_id: str,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        profile_id = str(body.get("usage_profile") or "").strip()
        project = service.activate_usage_profile(
            Scope(x_tenant_id, x_workspace_id, project_id),
            x_actor_id,
            profile_id,
            apply_catalog_defaults=bool(body.get("apply_catalog_defaults", True)),
        )
        return {"project": project}

    @api.get("/api/v1/projects/{project_id}/usage-profile/effective")
    async def effective_usage_profile(
        project_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        effective = service.get_effective_usage_profile(Scope(x_tenant_id, x_workspace_id, project_id))
        return {"effective": effective}

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "project-profile-service"}

    @api.post("/api/v1/projects/{project_id}/connect/bootstrap")
    async def connect_bootstrap(
        project_id: str,
        body: dict[str, Any],
        request: Request,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key", default=""),
    ) -> dict[str, Any]:
        _require_bootstrap_secret(request.app.state.bootstrap_secret_hash, body)
        _enforce_rate_limit(request, "bootstrap_rate_limiter")
        scope = Scope(x_tenant_id, x_workspace_id, project_id)
        result = service.connect_bootstrap(
            scope,
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key or str(uuid4()),
            body,
        )
        return _attach_auth_material(result, scope, request.app.state.token_registry)

    @api.post("/api/v1/projects/{project_id}/connect/sources")
    async def connect_sources(
        project_id: str,
        _auth: ConnectBearerAuth,
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        scope = Scope(x_tenant_id, x_workspace_id, project_id)
        project = service.register_code_source(scope, x_actor_id, body)
        return {"project": project}

    @api.post("/api/v1/projects/{project_id}/connect/ingest")
    async def connect_ingest(
        project_id: str,
        _auth: ConnectBearerAuth,
        body: dict[str, Any] | None = None,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        scope = Scope(x_tenant_id, x_workspace_id, project_id)
        return service.request_ingest(scope, x_actor_id, body or {})

    @api.get("/api/v1/projects/{project_id}/connect/status")
    async def connect_status(
        project_id: str,
        _auth: ConnectBearerAuth,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        return service.connect_status(Scope(x_tenant_id, x_workspace_id, project_id))

    @api.post("/api/v1/projects/{project_id}/access-tokens")
    async def create_access_token(
        project_id: str,
        _auth: ConnectBearerAuth,
        body: dict[str, Any] | None,
        request: Request,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        """Mint a scoped access token (API key). ``ttl_seconds=0`` = non-expiring."""
        _ = x_actor_id
        _enforce_rate_limit(request, "token_mint_rate_limiter")
        payload = body or {}
        raw_ttl = payload.get("ttl_seconds", DEFAULT_ACCESS_TTL_SECONDS)
        try:
            ttl_seconds = int(raw_ttl)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ttl_seconds must be an integer >= 0 (0 = non-expiring)",
            ) from exc
        if ttl_seconds < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ttl_seconds must be an integer >= 0 (0 = non-expiring)",
            )
        try:
            token = mint_and_register_access_token(
                request.app.state.token_registry,
                tenant_id=x_tenant_id,
                workspace_id=x_workspace_id,
                project_id=project_id,
                ttl_seconds=ttl_seconds,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        claims = verify_connect_token(token)
        return {
            "access_token": token,
            "token_id": claims.get("jti") or "",
            "expires_in": ttl_seconds,
            "scope": {
                "tenant_id": x_tenant_id,
                "workspace_id": x_workspace_id,
                "project_id": project_id,
            },
        }

    @api.delete("/api/v1/projects/{project_id}/access-tokens/{token_id}")
    async def revoke_access_token(
        project_id: str,
        token_id: str,
        _auth: ConnectBearerAuth,
        request: Request,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        """Revoke an access token by ``token_id`` (``jti``)."""
        _ = x_actor_id
        jti = str(token_id or "").strip()
        if not jti:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="token_id is required",
            )
        try:
            revoke_access_token_in_scope(
                request.app.state.token_registry,
                jti=jti,
                tenant_id=x_tenant_id,
                workspace_id=x_workspace_id,
                project_id=project_id,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        return {"revoked": True, "token_id": jti}

    @api.get("/api/v1/projects/{project_id}/usage-profile/cursor-mcp")
    async def export_cursor_mcp(
        project_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
    ) -> dict[str, Any]:
        _ = x_actor_id
        return service.export_cursor_mcp_connection(Scope(x_tenant_id, x_workspace_id, project_id))

    @api.post("/api/v1/project-groups")
    async def create_group(
        body: dict[str, Any],
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        group = service.create_project_group(
            x_tenant_id,
            x_workspace_id,
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body,
        )
        return {"group": group}

    return api


# Backward-compatible alias used by tests and callers.
app = build_app
