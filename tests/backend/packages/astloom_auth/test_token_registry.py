"""At-rest access token registry: SHA-256 hash only, never plaintext."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from astloom_auth.token_registry import InMemoryAccessTokenRegistry, hash_access_token
from astloom_auth.tokens import mint_and_register_access_token, verify_registered_access_token
from usage_profile.mcp_tokens import verify_connect_token

SECRET = "unit-test-secret-key-32chars!!"


def _registry_with(jti: str, token_hash: str, *, expires_at: datetime) -> InMemoryAccessTokenRegistry:
    registry = InMemoryAccessTokenRegistry()
    registry.register(
        jti=jti,
        token_hash=token_hash,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        expires_at=expires_at,
    )
    return registry


def test_hash_access_token_is_sha256_hex() -> None:
    raw = "as1.example-payload.signature"
    assert hash_access_token(raw) == hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_register_and_assert_active() -> None:
    token_hash = hash_access_token("raw-token-value")
    registry = _registry_with("jti-1", token_hash, expires_at=datetime.now(UTC) + timedelta(days=1))
    registry.assert_active("jti-1", token_hash)


def test_assert_active_rejects_unknown_jti() -> None:
    with pytest.raises(ValueError):
        InMemoryAccessTokenRegistry().assert_active("missing", "any-hash")


def test_assert_active_rejects_hash_mismatch() -> None:
    token_hash = hash_access_token("raw-token-value")
    registry = _registry_with("jti-1", token_hash, expires_at=datetime.now(UTC) + timedelta(days=1))
    with pytest.raises(ValueError):
        registry.assert_active("jti-1", hash_access_token("a-different-token"))


def test_assert_active_rejects_expired_token() -> None:
    token_hash = hash_access_token("raw-token-value")
    registry = _registry_with("jti-1", token_hash, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    with pytest.raises(ValueError):
        registry.assert_active("jti-1", token_hash)


def test_revoke_blocks_future_assert_active() -> None:
    token_hash = hash_access_token("raw-token-value")
    registry = _registry_with("jti-1", token_hash, expires_at=datetime.now(UTC) + timedelta(days=1))
    registry.revoke("jti-1")
    with pytest.raises(ValueError):
        registry.assert_active("jti-1", token_hash)


def test_revoke_rejects_unknown_jti() -> None:
    with pytest.raises(ValueError):
        InMemoryAccessTokenRegistry().revoke("missing")


def test_in_memory_registry_never_stores_raw_token() -> None:
    raw_token = "as1.super-secret-payload-should-never-be-stored.sig-value"
    registry = _registry_with(
        "jti-1", hash_access_token(raw_token), expires_at=datetime.now(UTC) + timedelta(days=1)
    )
    dump = "".join(repr(vars(record)) for record in registry._records.values())
    assert raw_token not in dump
    assert "super-secret-payload-should-never-be-stored" not in dump


def test_mint_and_register_then_verify_registered() -> None:
    registry = InMemoryAccessTokenRegistry()
    token = mint_and_register_access_token(
        registry, tenant_id="t", workspace_id="w", project_id="p", secret=SECRET
    )
    claims = verify_registered_access_token(
        token, registry, tenant_id="t", workspace_id="w", project_id="p", secret=SECRET
    )
    assert claims["tenant_id"] == "t"
    assert claims["jti"]


def test_verify_registered_access_token_fails_after_revoke() -> None:
    registry = InMemoryAccessTokenRegistry()
    token = mint_and_register_access_token(
        registry, tenant_id="t", workspace_id="w", project_id="p", secret=SECRET
    )
    jti = verify_connect_token(token, secret=SECRET)["jti"]
    registry.revoke(jti)
    with pytest.raises(ValueError):
        verify_registered_access_token(token, registry, secret=SECRET)


def test_mint_ttl_zero_is_non_expiring(monkeypatch) -> None:
    from usage_profile.mcp_tokens import mint_connect_token, verify_connect_token

    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", SECRET)
    token = mint_connect_token(
        tenant_id="t", workspace_id="w", project_id="p", ttl_seconds=0, secret=SECRET
    )
    claims = verify_connect_token(token, secret=SECRET, now=2_000_000_000_000)
    assert claims["jti"]


def test_mint_and_register_ttl_zero_registry_has_null_expiry() -> None:
    registry = InMemoryAccessTokenRegistry()
    token = mint_and_register_access_token(
        registry,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        ttl_seconds=0,
        secret=SECRET,
    )
    jti = verify_connect_token(token, secret=SECRET)["jti"]
    record = registry.get(jti)
    assert record is not None
    assert record.expires_at is None
    registry.assert_active(jti, hash_access_token(token))


def test_revoke_access_token_in_scope_rejects_wrong_project() -> None:
    from astloom_auth.tokens import revoke_access_token_in_scope

    registry = InMemoryAccessTokenRegistry()
    token = mint_and_register_access_token(
        registry, tenant_id="t", workspace_id="w", project_id="p", secret=SECRET
    )
    jti = verify_connect_token(token, secret=SECRET)["jti"]
    with pytest.raises(ValueError, match="not found"):
        revoke_access_token_in_scope(
            registry, jti=jti, tenant_id="t", workspace_id="w", project_id="other"
        )
