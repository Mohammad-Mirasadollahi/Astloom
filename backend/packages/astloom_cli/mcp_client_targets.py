"""MCP stdio config paths and merge rules for coding-agent / IDE clients."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

DEFAULT_SERVER_NAME = "Astloom-Programming"

MergeRoot = Callable[[dict[str, Any]], dict[str, Any]]


def _mcp_servers_root(doc: dict[str, Any]) -> dict[str, Any]:
    if "mcpServers" not in doc:
        doc["mcpServers"] = {}
    return doc


@dataclass(frozen=True)
class McpClientTarget:
    """Where to merge an ``mcpServers`` fragment for one coding-agent product."""

    client_id: str
    title: str
    scope: str  # project | user
    relative_path: str | None = None
    user_path: Callable[[], Path] | None = None
    prepare_root: MergeRoot = _mcp_servers_root
    servers_key: str = "mcpServers"

    def project_path(self, project_dir: Path) -> Path | None:
        if self.scope != "project" or not self.relative_path:
            return None
        return (project_dir / self.relative_path).resolve()

    def user_config_path(self) -> Path | None:
        if self.scope != "user" or self.user_path is None:
            return None
        return self.user_path().expanduser().resolve()


def _claude_desktop_config() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        return home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg else home / ".config"
    return base / "Claude" / "claude_desktop_config.json"


def _cursor_user_config() -> Path:
    return Path.home() / ".cursor" / "mcp.json"


MCP_CLIENT_TARGETS: tuple[McpClientTarget, ...] = (
    McpClientTarget(
        "cursor",
        "Cursor (workspace)",
        "project",
        relative_path=".cursor/mcp.json",
    ),
    McpClientTarget(
        "cursor-user",
        "Cursor (user global)",
        "user",
        user_path=_cursor_user_config,
    ),
    McpClientTarget(
        "windsurf",
        "Windsurf / Codeium (workspace)",
        "project",
        relative_path=".windsurf/mcp.json",
    ),
    McpClientTarget(
        "vscode",
        "VS Code (workspace MCP file)",
        "project",
        relative_path=".vscode/mcp.json",
    ),
    McpClientTarget(
        "claude-code",
        "Claude Code (project .mcp.json)",
        "project",
        relative_path=".mcp.json",
    ),
    McpClientTarget(
        "continue",
        "Continue (workspace fragment)",
        "project",
        relative_path=".continue/mcp.json",
    ),
    McpClientTarget(
        "claude-desktop",
        "Claude Desktop (user)",
        "user",
        user_path=_claude_desktop_config,
    ),
    McpClientTarget(
        "fragment",
        "Portable JSON fragment (commit-friendly)",
        "project",
        relative_path=".astloom/mcp-servers.json",
    ),
)

MCP_CLIENT_BY_ID: dict[str, McpClientTarget] = {t.client_id: t for t in MCP_CLIENT_TARGETS}

PROJECT_CLIENTS_ALL: tuple[str, ...] = (
    "cursor",
    "windsurf",
    "vscode",
    "claude-code",
    "continue",
    "fragment",
)


def list_mcp_client_targets() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for t in MCP_CLIENT_TARGETS:
        rows.append(
            {
                "client_id": t.client_id,
                "title": t.title,
                "scope": t.scope,
                "path_hint": t.relative_path or "(user config)",
            }
        )
    return rows


def resolve_client_ids(raw: str) -> list[str]:
    text = (raw or "all").strip().lower()
    if text in ("all", "*"):
        return list(PROJECT_CLIENTS_ALL)
    ids = [part.strip() for part in text.split(",") if part.strip()]
    unknown = [i for i in ids if i not in MCP_CLIENT_BY_ID]
    if unknown:
        raise SystemExit(
            f"error: unknown --clients {unknown!r}; run astloom client list-mcp-clients"
        )
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def config_paths_for_clients(
    project_dir: Path,
    client_ids: Sequence[str],
    *,
    include_user: bool = False,
) -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = []
    seen_paths: set[Path] = set()
    for cid in client_ids:
        target = MCP_CLIENT_BY_ID[cid]
        if target.scope == "user":
            if not include_user:
                continue
            p = target.user_config_path()
        else:
            p = target.project_path(project_dir)
        if p is None:
            continue
        if p in seen_paths:
            continue
        seen_paths.add(p)
        paths.append((cid, p))
    return paths


def merge_mcp_servers_file(
    path: Path,
    fragment: dict[str, Any],
    *,
    server_names: tuple[str, ...] = (DEFAULT_SERVER_NAME,),
    target: McpClientTarget | None = None,
) -> dict[str, Any]:
    """Merge ``fragment['mcpServers']`` into an MCP client config file."""
    t = target or MCP_CLIENT_BY_ID["cursor"]
    existing: dict[str, Any] = {}
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
    doc = t.prepare_root(dict(existing))
    servers = dict(doc.get(t.servers_key) or {})
    incoming = fragment.get("mcpServers") or {}
    for key in server_names:
        if key in incoming:
            servers[key] = incoming[key]
    for key, value in incoming.items():
        if key not in server_names:
            servers[key] = value
    doc[t.servers_key] = servers
    from astloom_cli.connect_security import atomic_write_text, file_lock, merge_lock_path

    lock = merge_lock_path(path)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    with file_lock(lock):
        atomic_write_text(path, payload, mode=0o644)
    return doc


def materialize_http_mcp_fragment(
    *,
    url: str,
    headers: dict[str, str],
    server_name: str = DEFAULT_SERVER_NAME,
    ca_file: str | None = None,
    tls_verify: bool = False,
) -> dict[str, Any]:
    """Build mcpServers entry for Streamable HTTP / URL-based MCP clients.

    Cursor's native HTTPS ``url`` transport always verifies certificates and
    cannot take a custom CA — private Astloom auto-TLS then fails with
    ``fetch failed``. Prefer stdio ``npx mcp-remote``:

    - ``tls_verify=False`` (lab default): ``NODE_TLS_REJECT_UNAUTHORIZED=0``
      so the IDE path ignores cert validation (same intent as CLI httpx).
    - ``tls_verify=True``: require ``ca_file`` and set ``NODE_EXTRA_CA_CERTS``.
    """
    verify = bool(tls_verify)
    ca = str(ca_file or "").strip()
    ca_path = Path(ca).expanduser() if ca else None
    ca_ok = bool(ca_path and ca_path.is_file())

    if verify and not ca_ok:
        raise SystemExit(
            "error: auth.tls_verify is true but no CA file for IDE MCP.\n"
            "  Set auth.ca_file to the Astloom ca.pem, or set auth.tls_verify: false "
            "to skip certificate verification for Cursor (lab)."
        )

    # Private auto-TLS labs always need mcp-remote (bare url cannot skip verify).
    # Also use mcp-remote when verifying with a CA path.
    if (not verify) or ca_ok:
        args: list[str] = ["-y", "mcp-remote", url]
        for key, value in headers.items():
            args.extend(["--header", f"{key}: {value}"])
        env: dict[str, str] = {}
        if verify and ca_ok and ca_path is not None:
            env["NODE_EXTRA_CA_CERTS"] = str(ca_path.resolve())
        else:
            # Lab / operator explicitly disabled verify — do not validate certs.
            env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
        return {
            "mcpServers": {
                server_name: {
                    "command": "npx",
                    "args": args,
                    "env": env,
                }
            }
        }

    entry: dict[str, Any] = {"url": url}
    if headers:
        entry["headers"] = dict(headers)
    return {"mcpServers": {server_name: entry}}


def write_fragment_to_clients(
    project_dir: Path,
    fragment: dict[str, Any],
    client_ids: Sequence[str],
    *,
    server_name: str = DEFAULT_SERVER_NAME,
    include_user_clients: bool = False,
) -> list[Path]:
    written: list[Path] = []
    for cid, path in config_paths_for_clients(
        project_dir, client_ids, include_user=include_user_clients
    ):
        target = MCP_CLIENT_BY_ID[cid]
        tagged = _with_client_id_env(fragment, cid, server_name=server_name)
        merge_mcp_servers_file(
            path,
            tagged,
            server_names=(server_name,),
            target=target,
        )
        written.append(path)
    return written


def _with_client_id_env(
    fragment: dict[str, Any],
    client_id: str,
    *,
    server_name: str,
) -> dict[str, Any]:
    """Stamp ASTLOOM_MCP_CLIENT_ID on stdio server env for usage attribution."""
    import copy

    out = copy.deepcopy(fragment)
    servers = out.get("mcpServers") or {}
    entry = servers.get(server_name)
    if isinstance(entry, dict) and isinstance(entry.get("env"), dict):
        entry["env"]["ASTLOOM_MCP_CLIENT_ID"] = client_id
    return out
