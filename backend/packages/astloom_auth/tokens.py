"""Long-lived scoped access token minting.

No refresh tokens: a single access token is issued at bootstrap/connect and
re-minted by re-running bootstrap once it expires. ``ttl_seconds=0`` issues a
non-expiring token (claim ``exp=0``; registry ``expires_at=None``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from usage_profile.mcp_tokens import mint_connect_token, verify_connect_token

from .token_registry import AccessTokenRegistry, hash_access_token

DEFAULT_ACCESS_TTL_SECONDS = 86400 * 30


def mint_access_token(
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    ttl_seconds: int = DEFAULT_ACCESS_TTL_SECONDS,
    secret: str | None = None,
    iat: int | None = None,
    nonce: str | None = None,
) -> str:
    return mint_connect_token(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        project_id=project_id,
        ttl_seconds=ttl_seconds,
        secret=secret,
        iat=iat,
        nonce=nonce,
    )


def mint_and_register_access_token(
    registry: AccessTokenRegistry,
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    ttl_seconds: int = DEFAULT_ACCESS_TTL_SECONDS,
    secret: str | None = None,
) -> str:
    """Mint a scoped access token, register its SHA-256 hash at rest, return plaintext once."""
    ttl = int(ttl_seconds)
    if ttl < 0:
        raise ValueError("ttl_seconds must be >= 0 (0 = non-expiring)")
    token = mint_access_token(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        project_id=project_id,
        ttl_seconds=ttl,
        secret=secret,
    )
    claims = verify_connect_token(token, secret=secret)
    jti = claims.get("jti")
    if not jti:
        raise ValueError("minted token is missing jti")
    expires_at = None if ttl == 0 else datetime.now(UTC) + timedelta(seconds=ttl)
    registry.register(
        jti=jti,
        token_hash=hash_access_token(token),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        project_id=project_id,
        expires_at=expires_at,
    )
    return token


def verify_registered_access_token(
    token: str,
    registry: AccessTokenRegistry,
    *,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    secret: str | None = None,
) -> dict[str, str]:
    """Verify signature/scope, then assert liveness in the registry.

    Static shared MCP HTTP tokens (non-``as1.*``) carry no ``jti`` and skip the
    registry check — lab/dev fallback, matching ``verify_connect_token``.
    """
    claims = verify_connect_token(
        token,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        project_id=project_id,
        secret=secret,
    )
    jti = claims.get("jti")
    if jti:
        registry.assert_active(jti, hash_access_token(token))
    return claims


def revoke_access_token_in_scope(
    registry: AccessTokenRegistry,
    *,
    jti: str,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
) -> None:
    """Revoke by ``jti`` only when the registry row matches the request scope."""
    record = registry.get(jti)
    if record is None:
        raise ValueError("access token not found")
    if (
        record.tenant_id != tenant_id
        or record.workspace_id != workspace_id
        or record.project_id != project_id
    ):
        raise ValueError("access token not found")
    registry.revoke(jti)
