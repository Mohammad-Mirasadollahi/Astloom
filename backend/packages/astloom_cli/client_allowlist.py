"""Client-only top-level command allowlist (shared by thin entry + full-CLI gate)."""

from __future__ import annotations

from typing import Any

# Top-level commands permitted on install role=client (thin entry + defense-in-depth gate).
CLIENT_TOP_LEVEL_COMMANDS = frozenset(
    {
        "connect",
        "profile",
        "project",
        "sync",
        "purge",
        "status",
        "version",
        "doctor",
        "client",
        "path",
        "upgrade",
    }
)

# For ``upgrade``, only client-safe subcommands (refresh + install finalize stamp).
CLIENT_UPGRADE_SUBCOMMANDS = frozenset({"client", "finalize"})


def client_command_allowed(command: str | None, args: Any | None = None) -> bool:
    """Return True when *command* (and upgrade subcommand when relevant) is client-safe."""
    if not command:
        return False
    if command not in CLIENT_TOP_LEVEL_COMMANDS:
        return False
    if command == "upgrade":
        sub = getattr(args, "upgrade_command", None) if args is not None else None
        return sub in CLIENT_UPGRADE_SUBCOMMANDS
    return True


def deny_message_for_client_role(command: str | None) -> str:
    cmd = command or "(none)"
    return (
        f"error: command {cmd!r} is not available on install role=client "
        f"(use astloom-client for connect/profile/sync/purge/status/upgrade client|finalize, "
        f"or run server-admin commands on the Astloom server)"
    )
