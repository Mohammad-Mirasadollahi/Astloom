"""HTTP connect API helpers (bootstrap, ingest, health, MCP smoke)."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from astloom_cli.connect_config import ConnectSettings, http_error_message
from astloom_cli.connect_http import httpx_verify


def api_headers(settings: ConnectSettings) -> dict[str, str]:
    headers = {
        "X-Tenant-Id": settings.tenant,
        "X-Workspace-Id": settings.workspace,
        "X-Actor-Id": settings.actor_id,
        "Idempotency-Key": str(uuid.uuid4()),
    }
    if settings.api_token:
        headers["Authorization"] = f"Bearer {settings.api_token}"
    return headers


def api_bootstrap(settings: ConnectSettings) -> dict[str, Any]:
    if not settings.api_url:
        return {}
    body: dict[str, Any] = {
        "name": settings.project_name,
        "usage_profile": settings.usage_profile,
    }
    if settings.source_server_path:
        body["source_path"] = settings.source_server_path
    if settings.source_git_remote:
        body["git"] = {"remote": settings.source_git_remote, "branch": settings.source_git_branch}
    if settings.mcp_http_url:
        body["mcp_http_url"] = settings.mcp_http_url
    if settings.bootstrap_secret:
        body["bootstrap_secret"] = settings.bootstrap_secret
    url = f"{settings.api_url}/api/v1/projects/{settings.project}/connect/bootstrap"
    try:
        response = httpx.post(
            url,
            headers=api_headers(settings),
            json=body,
            timeout=30.0,
            verify=httpx_verify(settings),
        )
    except httpx.HTTPError as exc:
        raise SystemExit(f"error: connect bootstrap request failed: {exc}") from exc
    if response.status_code >= 400:
        raise SystemExit(f"error: bootstrap HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


def api_ingest(settings: ConnectSettings) -> dict[str, Any]:
    if not settings.api_url:
        return {}
    body: dict[str, Any] = {}
    if settings.source_server_path:
        body["source_path"] = settings.source_server_path
    url = f"{settings.api_url}/api/v1/projects/{settings.project}/connect/ingest"

    try:
        response = httpx.post(
            url,
            headers=api_headers(settings),
            json=body,
            timeout=120.0,
            verify=httpx_verify(settings),
        )
    except httpx.HTTPError as exc:
        raise SystemExit(f"error: connect ingest request failed: {exc}") from exc
    if response.status_code >= 400:
        raise SystemExit(http_error_message("ingest", response))
    return response.json()


def api_health(settings: ConnectSettings) -> bool:
    if not settings.api_url:
        return False
    try:
        response = httpx.get(
            f"{settings.api_url}/health",
            timeout=10.0,
            verify=httpx_verify(settings),
        )
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def mcp_http_smoke(url: str, headers: dict[str, str], *, verify: str | bool = True) -> bool:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=15.0, verify=verify)
    except httpx.HTTPError:
        return False
    if response.status_code >= 400:
        return False
    data = response.json()
    return isinstance(data, dict) and "result" in data


_api_headers = api_headers
