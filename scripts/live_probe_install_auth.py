#!/usr/bin/env python3
"""Live probe: preserve JWT/bootstrap, mint API key, HTTP create/revoke, MCP auth."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/opt/Astloom")
sys.path.insert(0, str(ROOT / "backend" / "packages"))
sys.path.insert(0, str(ROOT / "backend" / "services" / "project-profile-service" / "src"))

from astloom_cli.cli_defaults import load_dotenv_files
from astloom_cli.install_auth import ensure_server_auth_secrets, mint_install_api_key
from astloom_cli.remote_client import apply_compose_env_to_os
from astloom_cli.service_runtime.paths import mcp_secret_path
from astloom_cli.install_auth import bootstrap_secret_path


def _load_env() -> None:
    load_dotenv_files(root=ROOT)
    env = os.environ.copy()
    try:
        apply_compose_env_to_os(env, ROOT)
    except SystemExit:
        pass
    for key, value in env.items():
        if key.startswith("ASTLOOM_") and not (os.environ.get(key) or "").strip():
            os.environ[key] = value


def _http_json(method: str, url: str, *, headers: dict[str, str], body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=__import__("ssl")._create_unverified_context(), timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:500]}
        return exc.code, payload


def main() -> int:
    results: dict[str, object] = {"ok": True, "checks": []}

    def check(name: str, cond: bool, detail: object = None) -> None:
        results["checks"].append({"name": name, "ok": bool(cond), "detail": detail})
        if not cond:
            results["ok"] = False

    jwt_before = mcp_secret_path(ROOT).read_text(encoding="utf-8").strip()
    boot_before = bootstrap_secret_path(ROOT).read_text(encoding="utf-8").strip()
    _load_env()

    report = ensure_server_auth_secrets(ROOT)
    check("jwt_preserved", report["jwt"]["action"] == "preserved", report["jwt"])
    check("bootstrap_preserved", report["bootstrap"]["action"] == "preserved", report["bootstrap"])
    check(
        "jwt_bytes_unchanged",
        mcp_secret_path(ROOT).read_text(encoding="utf-8").strip() == jwt_before,
    )
    check(
        "bootstrap_bytes_unchanged",
        bootstrap_secret_path(ROOT).read_text(encoding="utf-8").strip() == boot_before,
    )

    mint = mint_install_api_key(
        ROOT,
        tenant_id="mir",
        workspace_id="dev",
        project_id="ThinkingSOC",
        ttl_seconds=0,
    )
    check("mint_ok", mint.get("ok") is True, {k: mint.get(k) for k in ("token_id", "expires_in", "registry")})
    check("mint_postgres", mint.get("registry") == "postgres", mint.get("registry"))
    check("mint_ac1", str(mint.get("access_token", "")).startswith("as1."))
    check("mint_non_expiring", mint.get("expires_in") == 0)

    token = str(mint["access_token"])
    jti = str(mint["token_id"])
    Path("/tmp/astloom-live-api-key.txt").write_text(token + "\n", encoding="utf-8")
    Path("/tmp/astloom-live-api-key.jti").write_text(jti + "\n", encoding="utf-8")

    # MCP health with Bearer
    mcp_req = urllib.request.Request(
        "http://127.0.0.1:32500/health",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(mcp_req, timeout=10) as resp:
            check("mcp_health_with_api_key", resp.status == 200, resp.status)
    except Exception as exc:  # noqa: BLE001
        check("mcp_health_with_api_key", False, str(exc))

    # Profile connect status with Bearer (HTTPS)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "mir",
        "X-Workspace-Id": "dev",
        "X-Actor-Id": "live-qa",
        "Content-Type": "application/json",
    }
    status, body = _http_json(
        "GET",
        "https://127.0.0.1:32194/api/v1/projects/ThinkingSOC/connect/status",
        headers=headers,
    )
    check("profile_status_bearer", status == 200, {"status": status, "keys": sorted(body.keys())[:12]})

    # Create another short-lived API key via HTTP
    status2, body2 = _http_json(
        "POST",
        "https://127.0.0.1:32194/api/v1/projects/ThinkingSOC/access-tokens",
        headers=headers,
        body={"ttl_seconds": 3600},
    )
    check(
        "http_create_access_token",
        status2 == 200 and str(body2.get("access_token", "")).startswith("as1."),
        {"status": status2, "token_id": body2.get("token_id"), "expires_in": body2.get("expires_in")},
    )
    created_id = str(body2.get("token_id") or "")

    # Create non-expiring via HTTP
    status3, body3 = _http_json(
        "POST",
        "https://127.0.0.1:32194/api/v1/projects/ThinkingSOC/access-tokens",
        headers=headers,
        body={"ttl_seconds": 0},
    )
    check(
        "http_create_ttl0",
        status3 == 200 and body3.get("expires_in") == 0,
        {"status": status3, "expires_in": body3.get("expires_in"), "token_id": body3.get("token_id")},
    )

    # Revoke the short-lived one
    if created_id:
        status4, body4 = _http_json(
            "DELETE",
            f"https://127.0.0.1:32194/api/v1/projects/ThinkingSOC/access-tokens/{created_id}",
            headers=headers,
        )
        check("http_revoke", status4 == 200 and body4.get("revoked") is True, {"status": status4, "body": body4})

        # Using revoked token should fail status
        revoked_token = str(body2.get("access_token") or "")
        bad_headers = dict(headers)
        bad_headers["Authorization"] = f"Bearer {revoked_token}"
        status5, _ = _http_json(
            "GET",
            "https://127.0.0.1:32194/api/v1/projects/ThinkingSOC/connect/status",
            headers=bad_headers,
        )
        check("revoked_token_rejected", status5 in (401, 403), status5)

    print(json.dumps(results, indent=2, ensure_ascii=True))
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
