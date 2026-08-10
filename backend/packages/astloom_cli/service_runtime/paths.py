"""Paths and constants for local Astloom process control."""

from __future__ import annotations

from pathlib import Path

UNIT_NAME = "astloom.service"
COMPOSE_SERVICES = ("postgres", "neo4j")
DEFAULT_MCP_HOST = "0.0.0.0"
DEFAULT_MCP_PORT = 32500
# Host MCP builds postgres/neo4j stores before uvicorn binds; cold start is ~4–8s
# and can exceed the old 6s poll budget under load after compose restart.
MCP_HTTP_READY_TIMEOUT_SEC = 60.0
# client = CLI-only; server = Compose+MCP; both = dogfood (server stack + client connect)
_VALID_INSTALL_ROLES = frozenset({"client", "server", "both"})


def run_dir(root: Path) -> Path:
    path = root / ".astloom" / "run"
    path.mkdir(parents=True, exist_ok=True)
    return path


def mcp_pid_path(root: Path) -> Path:
    return run_dir(root) / "mcp-http.pid"


def mcp_log_path(root: Path) -> Path:
    return run_dir(root) / "mcp-http.log"


def mcp_secret_path(root: Path) -> Path:
    return root / ".astloom" / "mcp-http.secret"


def compose_dir(root: Path) -> Path:
    return root / "backend" / "deployments" / "compose"


def compose_file(root: Path) -> Path:
    return compose_dir(root) / "compose.yaml"


def compose_env_file(root: Path) -> Path:
    return compose_dir(root) / ".env.local"


def install_role(root: Path) -> str | None:
    """Return ``client`` / ``server`` / ``both`` from ``.astloom/install-state.env`` when valid."""
    state = root / ".astloom" / "install-state.env"
    if not state.is_file():
        return None
    try:
        text = state.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("role="):
            continue
        value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
        if value in _VALID_INSTALL_ROLES:
            return value
    return None


def local_compose_stack_present(root: Path) -> bool:
    """True when this checkout should manage a local Compose/MCP stack.

    Pure ``client`` never counts as a local stack — even if compose files remain
    from an earlier server install — so ``astloom sync`` / ``service`` do not
    offer to start software on a CLI-only host. ``server`` and ``both`` use the
    local Compose files when present.
    """
    if install_role(root) == "client":
        return False
    return compose_file(root).is_file() and compose_env_file(root).is_file()


def missing_local_stack_message(root: Path) -> str:
    env = compose_env_file(root)
    role = install_role(root)
    role_note = f" (install role={role})" if role else ""
    if role == "client":
        reason = (
            "this checkout is install role=client, so local Compose sync is disabled"
        )
    elif not compose_env_file(root).is_file():
        reason = f"missing {env}"
    elif not compose_file(root).is_file():
        reason = f"missing {compose_file(root)}"
    else:
        reason = "local Compose stack not available"
    return (
        f"error: no local Astloom server stack{role_note} ({reason}).\n"
        "Client installs skip Compose (Postgres/Neo4j) on purpose.\n"
        "  • Run `astloom sync` on the Astloom server, or\n"
        "  • Configure `.astloom/connect.yaml` (`astloom connect`) "
        "so this CLI can sync over HTTPS, or\n"
        "  • Re-install with local stack: bash install.sh --role server "
        "(or --role both for dogfood client+server)"
    )
