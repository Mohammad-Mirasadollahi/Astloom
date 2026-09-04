"""Connect entrypoint: reachability + local / HTTP transport wiring.

Module contract:
- Role: orchestrate ``astloom connect`` end-to-end for one project dir.
- SoT / invariants: ``ConnectSettings`` + server API; prefer HTTP MCP when ready.
- Failures: reachability / missing transport fail closed. Dry-run never writes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from astloom_cli import ui
from astloom_cli.connect_config import ConnectSettings, write_or_merge_connect_yaml
from astloom_cli.connect_flow.api import api_bootstrap, api_health, api_ingest, mcp_http_smoke
from astloom_cli.connect_http import httpx_verify
from astloom_cli.connect_flow.ingest import local_ingest, remote_ingest, should_ingest
from astloom_cli.connect_flow.summary import (
    guidance_connect_notes,
    local_register,
    materialize_mcp_first_guidance,
    print_connect_summary,
    write_clients,
)
from astloom_cli.connect_security import validate_connect_settings
from astloom_cli.local_mcp import materialize_local_stdio_fragment
from astloom_cli.mcp_client_targets import materialize_http_mcp_fragment
from astloom_cli.util import repo_root


def reachability_check(settings: ConnectSettings) -> None:
    if settings.local:
        return
    if settings.api_url and not api_health(settings):
        raise SystemExit(f"error: API health check failed for {settings.api_url}/health")


def run_connect(
    settings: ConnectSettings,
    *,
    project_dir: Path | None = None,
    dry_run: bool = False,
) -> int:
    work = project_dir or Path.cwd()
    for line in validate_connect_settings(settings):
        print(line, file=sys.stderr)
    reachability_check(settings)
    ui.blank()
    print(f"{ui.accent('→')}  Connecting {ui.scope_line(settings.tenant, settings.workspace, settings.project)}")
    print(
        f"   {ui.dim('Agents sharing this scope use the same store; each IDE session is its own MCP client.')}"
    )

    bootstrap: dict[str, Any] = {}
    registered_via_api = False
    # Env-supplied keys win over bootstrap mint; a stale ``.astloom/access_token``
    # file must not block persisting a freshly minted bootstrap token (reconnect).
    token_env_name = (settings.token_env or "ASTLOOM_TOKEN").strip() or "ASTLOOM_TOKEN"
    operator_env_token = bool(
        os.environ.get(token_env_name, "").strip()
        or os.environ.get("ASTLOOM_CONNECT_TOKEN", "").strip()
    )
    if settings.api_url and settings.register:
        bootstrap = api_bootstrap(settings)
        registered_via_api = True
        if bootstrap:
            print(f"   {ui.ok('✔')} API bootstrap OK")
            access_token = str(bootstrap.get("access_token") or "").strip()
            if access_token and not operator_env_token:
                settings.api_token = access_token
                from astloom_cli.connect_http import persist_access_token

                token_path = persist_access_token(settings.config_path, access_token)
                if token_path is not None:
                    print(f"   {ui.ok('✔')} access token saved ({token_path.name}; mode 0600)")
            ca_pem = str(bootstrap.get("ca_pem") or "").strip()
            if ca_pem:
                from astloom_cli.connect_http import persist_ca_pem
                from dataclasses import replace

                ca_path = persist_ca_pem(settings.config_path, ca_pem)
                if ca_path is not None:
                    settings = replace(settings, ca_file=str(ca_path))
                    if not dry_run and settings.config_path is not None:
                        write_or_merge_connect_yaml(
                            settings, path=settings.config_path, prefer_http=settings.prefer_http
                        )
                    print(f"   {ui.ok('✔')} trusted CA saved ({ca_path})")


    mcp_info = bootstrap.get("mcp") if isinstance(bootstrap.get("mcp"), dict) else {}
    http_url = str(mcp_info.get("url") or settings.mcp_http_url or "").strip()
    if http_url and not http_url.endswith("/mcp"):
        http_url = http_url.rstrip("/") + "/mcp"
    http_headers = dict(mcp_info.get("headers") or {})
    # Prefer the operator API key (wizard / access_token file) over bootstrap-minted headers.
    if settings.prefer_http and http_url and settings.api_token:
        http_headers = {
            **http_headers,
            "Authorization": f"Bearer {settings.api_token}",
            "X-Tenant-Id": settings.tenant,
            "X-Workspace-Id": settings.workspace,
            "X-Project-Id": settings.project,
            "X-Usage-Profile": settings.usage_profile,
        }

    # --- Local stdio (dogfood same checkout) ---
    if settings.local and not (settings.prefer_http and http_url and http_headers):
        project_state: Path | None = None
        if settings.register and not dry_run:
            project_state = local_register(settings)
        fragment = materialize_local_stdio_fragment(
            tenant=settings.tenant,
            workspace=settings.workspace,
            project_id=settings.project,
            usage_profile=settings.usage_profile,
            root=repo_root(),
        )
        if dry_run:
            print(json.dumps(fragment, indent=2, sort_keys=True))
            return 0
        written = write_clients(work, fragment, settings)
        notes = ["Transport is local stdio (same-host dogfood; no HTTPS required)"]
        notes.extend(guidance_connect_notes(materialize_mcp_first_guidance(work)))
        if should_ingest(settings) and not dry_run:
            path = settings.source_server_path or str(work)
            code = local_ingest(settings, path)
            if code != 0:
                print(f"   {ui.warn('!')} sync exited non-zero ({code})", file=sys.stderr)
            else:
                notes.append(f"Ran local sync for {path}")
        print_connect_summary(
            settings=settings,
            transport="local-stdio",
            project_state=project_state,
            written=written,
            work=work,
            extra_notes=notes,
        )
        return 0

    if settings.prefer_http and http_url and http_headers:
        from astloom_cli.connect_http import resolve_ca_file

        ca_for_ide = resolve_ca_file(settings)
        if not ca_for_ide:
            auto_ca = work / ".astloom" / "certs" / "ca.pem"
            if auto_ca.is_file():
                ca_for_ide = str(auto_ca)
        fragment = materialize_http_mcp_fragment(
            url=http_url,
            headers=http_headers,
            ca_file=ca_for_ide or None,
        )
        if dry_run:
            print(json.dumps(fragment, indent=2, sort_keys=True))
            return 0
        written = write_clients(work, fragment, settings)
        notes = [f"Transport is Streamable HTTP ({http_url})"]
        if ca_for_ide:
            notes.append(
                "Cursor MCP uses stdio mcp-remote + NODE_EXTRA_CA_CERTS "
                "(native HTTPS url transport cannot trust Astloom private CA)"
            )
        # Cursor/IDE HTTP MCP verifies TLS even when CLI tls_verify is false.
        if http_url.lower().startswith("https://") and ca_for_ide:
            from astloom_cli.connect_http import ensure_ide_os_trusts_ca

            trust = ensure_ide_os_trusts_ca(ca_for_ide)
            if trust.get("ok"):
                notes.append(
                    "Installed Astloom CA into OS trust store "
                    f"({trust.get('action')}) + NODE_EXTRA_CA_CERTS for Cursor Remote"
                )
            else:
                notes.append(
                    "IDE TLS trust incomplete: "
                    f"{trust.get('action')}: {trust.get('detail') or 'see docs/52'}"
                )
                print(
                    f"   {ui.warn('!')} Cursor may show MCP fetch failed until the "
                    "Astloom CA is in the OS trust store "
                    f"({trust.get('detail') or trust.get('action')})",
                    file=sys.stderr,
                )
        elif http_url.lower().startswith("https://"):
            notes.append(
                "No ca.pem on client — Cursor HTTPS MCP may fail TLS verify "
                "(re-run connect after bootstrap writes .astloom/certs/ca.pem)"
            )
        notes.extend(guidance_connect_notes(materialize_mcp_first_guidance(work)))
        if settings.smoke_test and not mcp_http_smoke(
            http_url, http_headers, verify=httpx_verify(settings)
        ):
            print(
                f"   {ui.warn('!')} MCP HTTP smoke (initialize) failed; check serve-http and token",
                file=sys.stderr,
            )
        if should_ingest(settings):
            if settings.api_url and settings.source_server_path:
                result = api_ingest(settings)
                notes.append(f"Ingest: {json.dumps(result.get('ingest', result), sort_keys=True)}")
            elif (settings.graph_url or "").strip() and (settings.api_token or "").strip():
                try:
                    code = remote_ingest(settings, work=work)
                except SystemExit as exc:
                    msg = str(exc)
                    if "cloud LLM" in msg or "ALLOW_CLOUD_LLM" in msg or "allow-cloud-llm" in msg:
                        print(
                            f"   {ui.warn('!')} content-push deferred (cloud LLM consent); "
                            "run `astloom-client sync --allow-cloud-llm`",
                            file=sys.stderr,
                        )
                        notes.append(
                            "Ingest deferred: pass --allow-cloud-llm on sync after explicit consent"
                        )
                        code = 0
                    else:
                        raise
                if code != 0:
                    print(f"   {ui.warn('!')} content-push sync exited non-zero ({code})", file=sys.stderr)
                elif not any("deferred" in n for n in notes):
                    notes.append("Ran client content-push sync (HTTPS ingest-push)")

            elif settings.api_url:
                notes.append(
                    "Ingest deferred: set server.graph_url + token, then run "
                    "`astloom-client sync`"
                )
            else:
                code = remote_ingest(settings, work=work)
                if code != 0:
                    print(f"   {ui.warn('!')} sync exited non-zero ({code})", file=sys.stderr)
        print_connect_summary(
            settings=settings,
            transport=f"streamable_http ({http_url})",
            project_state=None,
            written=written,
            work=work,
            extra_notes=notes,
        )
        return 0

    raise SystemExit(
        "error: HTTP MCP unavailable; set server.mcp_http_url + auth.token_env "
        "(or server.url + register for the HTTPS wizard) in .astloom/connect.yaml"
    )
