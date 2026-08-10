"""Remote purge from a client install (HTTPS graph_url only).

Security: effective scope is always connect.yaml; CLI scope flags must match or fail.
Never falls back to local GraphService.purge_scope.
"""

from __future__ import annotations

import argparse

from astloom_cli import ui
from astloom_cli.connect_config import ConnectSettings, http_error_message
from astloom_cli.util import print_json


def locked_scope_from_settings(settings: ConnectSettings) -> tuple[str, str, str]:
    tenant = (settings.tenant or "").strip()
    workspace = (settings.workspace or "").strip()
    project = (settings.project or "").strip()
    if not tenant or not workspace or not project:
        raise SystemExit(
            "error: connect.yaml must set scope.tenant, scope.workspace, and scope.project "
            "before client purge"
        )
    return tenant, workspace, project


def assert_cli_scope_matches_connect(args: argparse.Namespace, settings: ConnectSettings) -> None:
    """Hard-fail when CLI scope flags disagree with connect.yaml (no silent prefer)."""
    locked = locked_scope_from_settings(settings)
    pairs = (
        ("tenant", locked[0], str(getattr(args, "tenant", None) or "").strip()),
        ("workspace", locked[1], str(getattr(args, "workspace", None) or "").strip()),
        ("project", locked[2], str(getattr(args, "project", None) or "").strip()),
    )
    for name, want, got in pairs:
        if got and got != want:
            raise SystemExit(
                f"error: --{name} {got!r} does not match connect.yaml scope "
                f"({want!r}); client purge cannot change scope"
            )


def _graph_http_ready(settings: ConnectSettings) -> bool:
    return bool((settings.graph_url or "").strip() and (settings.api_token or "").strip())


def http_purge_from_args(settings: ConnectSettings, args: argparse.Namespace) -> int:
    """Purge over HTTPS (code-graph-service ``graph/purge``); only supported transport."""
    import httpx

    from astloom_cli.connect_http import httpx_verify

    assert_cli_scope_matches_connect(args, settings)
    tenant, workspace, project = locked_scope_from_settings(settings)
    url = f"{settings.graph_url.rstrip('/')}/api/v1/projects/{project}/graph/purge"
    headers = {
        "X-Tenant-Id": tenant,
        "X-Workspace-Id": workspace,
        "Content-Type": "application/json",
    }
    if settings.api_token:
        headers["Authorization"] = f"Bearer {settings.api_token}"

    try:
        response = httpx.post(
            url,
            headers=headers,
            json={"yes": True},
            timeout=60.0,
            verify=httpx_verify(settings),
        )
    except httpx.HTTPError as exc:
        raise SystemExit(f"error: remote purge request failed: {exc}") from exc
    if response.status_code >= 400:
        raise SystemExit(http_error_message("purge", response))

    ui.blank()
    print(f"   {ui.warn('…')} remote purge via HTTPS ({settings.graph_url})")
    ui.kv("Scope", f"{tenant}/{workspace}/{project}")
    print_json(response.json())
    return 0


def remote_purge_from_args(settings: ConnectSettings, args: argparse.Namespace) -> int:
    if not getattr(args, "yes", False):
        raise SystemExit("error: purge requires --yes (destructive: wipes project graph data)")
    if not _graph_http_ready(settings):
        raise SystemExit(
            "error: client purge requires server.graph_url + auth token (HTTPS)"
        )
    return http_purge_from_args(settings, args)
