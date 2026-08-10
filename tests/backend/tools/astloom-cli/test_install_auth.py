"""Unit tests for install-time JWT/bootstrap ensure and API key mint."""

from __future__ import annotations

from pathlib import Path

from astloom_auth import verify_registered_access_token
from astloom_auth.token_registry import InMemoryAccessTokenRegistry
from astloom_auth.tokens import mint_and_register_access_token
from astloom_cli.install_auth import (
    BOOTSTRAP_SECRET_ENV,
    JWT_SECRET_ENV,
    api_key_once_path,
    bootstrap_secret_path,
    ensure_server_auth_secrets,
    mint_install_api_key,
    print_auth_summary,
    upsert_env_key,
)
from astloom_cli.service_runtime.paths import mcp_secret_path


def test_ensure_creates_jwt_and_bootstrap(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(JWT_SECRET_ENV, raising=False)
    monkeypatch.delenv(BOOTSTRAP_SECRET_ENV, raising=False)
    (tmp_path / ".env").write_text("# empty\n", encoding="utf-8")
    report = ensure_server_auth_secrets(tmp_path)
    assert report["ok"] is True
    assert report["jwt"]["action"] == "created"
    assert report["bootstrap"]["action"] == "created"
    jwt_path = mcp_secret_path(tmp_path)
    boot_path = bootstrap_secret_path(tmp_path)
    assert jwt_path.is_file()
    assert boot_path.is_file()
    jwt = jwt_path.read_text(encoding="utf-8").strip()
    boot = boot_path.read_text(encoding="utf-8").strip()
    assert len(jwt) >= 20
    assert len(boot) >= 20
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert f"{JWT_SECRET_ENV}={jwt}" in env_text
    assert f"{BOOTSTRAP_SECRET_ENV}={boot}" in env_text


def test_ensure_preserves_existing_secrets(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(JWT_SECRET_ENV, raising=False)
    monkeypatch.delenv(BOOTSTRAP_SECRET_ENV, raising=False)
    jwt_path = mcp_secret_path(tmp_path)
    boot_path = bootstrap_secret_path(tmp_path)
    jwt_path.parent.mkdir(parents=True, exist_ok=True)
    jwt_path.write_text("existing-jwt-secret-value\n", encoding="utf-8")
    boot_path.write_text("existing-bootstrap-secret\n", encoding="utf-8")
    (tmp_path / ".env").write_text(
        f"{JWT_SECRET_ENV}=existing-jwt-secret-value\n"
        f"{BOOTSTRAP_SECRET_ENV}=existing-bootstrap-secret\n",
        encoding="utf-8",
    )
    report = ensure_server_auth_secrets(tmp_path)
    assert report["jwt"]["action"] == "preserved"
    assert report["bootstrap"]["action"] == "preserved"
    assert jwt_path.read_text(encoding="utf-8").strip() == "existing-jwt-secret-value"
    assert boot_path.read_text(encoding="utf-8").strip() == "existing-bootstrap-secret"


def test_upsert_env_key_preserves_non_placeholder(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text("FOO=keep-me\n", encoding="utf-8")
    assert upsert_env_key(path, "FOO", "new") == "preserved"
    assert "FOO=keep-me" in path.read_text(encoding="utf-8")
    assert upsert_env_key(path, "BAR", "x") == "created"
    assert "BAR=x" in path.read_text(encoding="utf-8")


def test_mint_install_api_key_registers_and_writes_once_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(JWT_SECRET_ENV, raising=False)
    monkeypatch.delenv(BOOTSTRAP_SECRET_ENV, raising=False)
    monkeypatch.delenv("ASTLOOM_DATABASE_URL", raising=False)
    ensure_server_auth_secrets(tmp_path)
    mint = mint_install_api_key(
        tmp_path,
        tenant_id="t1",
        workspace_id="w1",
        project_id="p1",
        ttl_seconds=0,
    )
    assert mint["ok"] is True
    assert mint["expires_in"] == 0
    assert mint["token_id"]
    assert mint["access_token"].startswith("as1.")
    assert mint["registry"] == "memory"
    once = api_key_once_path(tmp_path)
    assert once.is_file()
    assert once.read_text(encoding="utf-8").strip() == mint["access_token"]

    # Second ensure must preserve JWT used for the mint.
    again = ensure_server_auth_secrets(tmp_path)
    assert again["jwt"]["action"] == "preserved"
    secret = mcp_secret_path(tmp_path).read_text(encoding="utf-8").strip()
    registry = InMemoryAccessTokenRegistry()
    token2 = mint_and_register_access_token(
        registry,
        tenant_id="t1",
        workspace_id="w1",
        project_id="p1",
        ttl_seconds=3600,
        secret=secret,
    )
    claims = verify_registered_access_token(
        token2,
        registry,
        tenant_id="t1",
        workspace_id="w1",
        project_id="p1",
        secret=secret,
    )
    assert claims.get("jti")


def test_print_auth_summary_includes_client_quick_setup(capsys):
    print_auth_summary(
        {
            "jwt": {"path": "/tmp/jwt", "action": "created"},
            "bootstrap": {"path": "/tmp/boot", "action": "created"},
        },
        mint={
            "token_id": "jti-1",
            "expires_in": 0,
            "scope": {"tenant_id": "t", "workspace_id": "w", "project_id": "p"},
            "access_token": "as1.test-token",
            "once_file": "/tmp/once",
        },
    )
    out = capsys.readouterr().out
    assert "Client next (Quick Setup):" in out
    assert ".astloom/access_token" in out
    assert "Do not put the token in connect.yaml" in out
