"""Server install/upgrade auth material: JWT signing secret, bootstrap secret, optional API key.

Preserve-on-upgrade: never overwrite an existing secret file or a non-placeholder
``.env`` / compose ``.env.local`` value. Missing material is created; present material
is reused.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astloom_cli.service_runtime.paths import mcp_secret_path

JWT_SECRET_ENV = "ASTLOOM_MCP_TOKEN_SECRET"
BOOTSTRAP_SECRET_ENV = "ASTLOOM_CONNECT_BOOTSTRAP_SECRET"
PLACEHOLDERS = frozenset(
    {
        "",
        "replace-with-a-local-secret",
        "replace-with-a-long-random-secret",
        "changeme",
    }
)


def bootstrap_secret_path(root: Path) -> Path:
    return root / ".astloom" / "connect-bootstrap.secret"


def api_key_once_path(root: Path) -> Path:
    """Optional one-time plaintext API key file (mode 0600); operator may delete after copy."""
    return root / ".astloom" / "install-api-key.secret"


def api_key_meta_path(root: Path) -> Path:
    return root / ".astloom" / "install-api-key.meta.json"


@dataclass(frozen=True)
class SecretEnsureResult:
    key: str
    path: Path
    action: str  # created | preserved | synced_env
    value_preview: str = ""  # never the full secret in logs; empty by default


def _is_placeholder(value: str | None) -> bool:
    return (value or "").strip() in PLACEHOLDERS


def _read_secret_file(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _write_secret_file(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip("\n") + "\n", encoding="utf-8")
    path.chmod(0o600)


def _parse_env_lines(text: str) -> list[str]:
    return text.splitlines()


def upsert_env_key(path: Path, key: str, value: str, *, force: bool = False) -> str:
    """Set ``key=value`` in an env file. Preserves non-placeholder values unless ``force``.

    Returns ``created`` | ``updated`` | ``preserved`` | ``skipped_missing_file``.
    """
    if not path.is_file():
        return "skipped_missing_file"
    raw = path.read_text(encoding="utf-8")
    lines = _parse_env_lines(raw)
    found = False
    out: list[str] = []
    action = "preserved"
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        cur_key, _, cur_val = stripped.partition("=")
        cur_key = cur_key.strip()
        cur_val = cur_val.strip().strip("'").strip('"')
        if cur_key != key:
            out.append(line)
            continue
        found = True
        if not force and not _is_placeholder(cur_val):
            out.append(line)
            continue
        out.append(f"{key}={value}")
        action = "updated"
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"# Set by Astloom install (do not commit)")
        out.append(f"{key}={value}")
        action = "created"
    if action != "preserved":
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return action


def _ensure_secret(
    *,
    root: Path,
    env_key: str,
    file_path: Path,
    env_files: list[Path],
) -> SecretEnsureResult:
    existing = _read_secret_file(file_path)
    env_existing = (os.environ.get(env_key) or "").strip()
    if existing:
        value = existing
        action = "preserved"
    elif env_existing and not _is_placeholder(env_existing):
        value = env_existing
        _write_secret_file(file_path, value)
        action = "synced_env"
    else:
        value = secrets.token_urlsafe(32)
        _write_secret_file(file_path, value)
        action = "created"

    os.environ[env_key] = value
    for env_path in env_files:
        upsert_env_key(env_path, env_key, value, force=False)
    return SecretEnsureResult(key=env_key, path=file_path, action=action)


def ensure_server_auth_secrets(root: Path) -> dict[str, Any]:
    """Ensure JWT signing + connect bootstrap secrets exist; preserve on upgrade.

    Also upserts into repo ``.env`` and compose ``.env.local`` when those files
    exist and the keys are missing/placeholder.
    """
    root = root.resolve()
    env_files = [
        root / ".env",
        root / "backend" / "deployments" / "compose" / ".env.local",
    ]
    jwt = _ensure_secret(
        root=root,
        env_key=JWT_SECRET_ENV,
        file_path=mcp_secret_path(root),
        env_files=env_files,
    )
    bootstrap = _ensure_secret(
        root=root,
        env_key=BOOTSTRAP_SECRET_ENV,
        file_path=bootstrap_secret_path(root),
        env_files=env_files,
    )
    return {
        "ok": True,
        "jwt": {
            "env": jwt.key,
            "path": str(jwt.path),
            "action": jwt.action,
        },
        "bootstrap": {
            "env": bootstrap.key,
            "path": str(bootstrap.path),
            "action": bootstrap.action,
        },
    }


def _postgres_url(root: Path) -> str:
    from astloom_cli.cli_defaults import load_dotenv_files

    load_dotenv_files(root=root)
    url = (os.environ.get("ASTLOOM_DATABASE_URL") or "").strip()
    if url:
        return url
    try:
        from astloom_cli.remote_client import apply_compose_env_to_os

        env = os.environ.copy()
        apply_compose_env_to_os(env, root)
        return (env.get("ASTLOOM_DATABASE_URL") or "").strip()
    except SystemExit:
        return ""


def mint_install_api_key(
    root: Path,
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    ttl_seconds: int = 0,
    write_once_file: bool = True,
) -> dict[str, Any]:
    """Mint a scoped ``as1.*`` API key into the durable token registry (Postgres when available)."""
    from astloom_auth import PostgresAccessTokenRegistry, mint_and_register_access_token
    from astloom_auth.token_registry import InMemoryAccessTokenRegistry
    from usage_profile.mcp_tokens import verify_connect_token

    root = root.resolve()
    ensure_server_auth_secrets(root)
    secret = _read_secret_file(mcp_secret_path(root)) or (os.environ.get(JWT_SECRET_ENV) or "").strip()
    if not secret:
        raise RuntimeError(f"missing JWT signing secret at {mcp_secret_path(root)}")

    database_url = _postgres_url(root)
    registry: Any
    store = "postgres"
    if database_url:
        registry = PostgresAccessTokenRegistry(database_url)
    else:
        registry = InMemoryAccessTokenRegistry()
        store = "memory"

    token = mint_and_register_access_token(
        registry,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        project_id=project_id,
        ttl_seconds=int(ttl_seconds),
        secret=secret,
    )
    claims = verify_connect_token(token, secret=secret)
    token_id = str(claims.get("jti") or "")
    once_path = api_key_once_path(root)
    meta = {
        "token_id": token_id,
        "expires_in": int(ttl_seconds),
        "scope": {
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "project_id": project_id,
        },
        "registry": store,
        "once_file": str(once_path) if write_once_file else "",
    }
    meta_path = api_key_meta_path(root)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    meta_path.chmod(0o600)
    if write_once_file:
        _write_secret_file(once_path, token)
    return {
        "ok": True,
        "access_token": token,
        "token_id": token_id,
        "expires_in": int(ttl_seconds),
        "scope": meta["scope"],
        "registry": store,
        "once_file": str(once_path) if write_once_file else "",
        "meta_file": str(meta_path),
    }


def print_auth_summary(report: dict[str, Any], *, mint: dict[str, Any] | None = None) -> None:
    """Operator-facing summary (secrets themselves are not re-printed except minted API key once)."""
    jwt = report.get("jwt") or {}
    boot = report.get("bootstrap") or {}
    print("Auth secrets (server):", flush=True)
    print(f"  JWT signing secret:  {jwt.get('path')}  [{jwt.get('action')}]", flush=True)
    print(f"  Connect bootstrap:   {boot.get('path')}  [{boot.get('action')}]", flush=True)
    print(
        f"  Env keys: {JWT_SECRET_ENV}, {BOOTSTRAP_SECRET_ENV} "
        "(written to .env / compose .env.local when missing)",
        flush=True,
    )
    if not mint:
        return
    print("API key (shown once — store securely, then delete the once-file):", flush=True)
    print(f"  token_id:     {mint.get('token_id')}", flush=True)
    print(f"  expires_in:   {mint.get('expires_in')}  (0 = non-expiring)", flush=True)
    print(f"  scope:        {mint.get('scope')}", flush=True)
    print(f"  access_token: {mint.get('access_token')}", flush=True)
    if mint.get("once_file"):
        print(f"  once_file:    {mint.get('once_file')}", flush=True)
    print("Client next (Quick Setup):", flush=True)
    print(
        "  Do not put the token in connect.yaml.",
        flush=True,
    )
    print(
        "  Prefer: write one line to <checkout>/.astloom/access_token (chmod 600),",
        flush=True,
    )
    print(
        "  or export ASTLOOM_TOKEN, or re-run astloom-client connect with the bootstrap secret.",
        flush=True,
    )
    print(
        "  Docs: 41-one-command-cross-platform-agent-onboarding.md "
        "(Quick Setup — where the access token goes).",
        flush=True,
    )
