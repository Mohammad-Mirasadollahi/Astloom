"""Shared operator guidance when searchable symbols lack embeddings."""

from __future__ import annotations

from typing import Any

from astloom_cli import ui


def missing_embedding_counts(summary: dict[str, Any] | None) -> tuple[int, int, int]:
    """Return ``(missing, indexed, eligible)`` from an inventory/stats summary."""
    emb = (summary or {}).get("embeddings") or {}
    missing = int(emb.get("missing_symbols") or 0)
    indexed = int(emb.get("indexed_symbols") or 0)
    eligible = int(emb.get("eligible_symbols") or 0)
    return missing, indexed, eligible


def format_embedding_heal_lines(
    summary: dict[str, Any] | None,
    *,
    sync_mode: str = "",
) -> list[str]:
    """Plain-text lines for stats save / scripts (empty when nothing to heal)."""
    missing, indexed, eligible = missing_embedding_counts(summary)
    if missing <= 0:
        return []
    lines = [
        (
            f"Need embedding heal: {missing} searchable symbols missing "
            f"(indexed={indexed}/{eligible})"
        ),
    ]
    if str(sync_mode or "").strip().lower() == "heal":
        lines.append("This run: astloom sync heal (full-project embedding refresh)")
    else:
        lines.append(
            "Plain astloom sync only heals embeddings for files touched this run"
        )
        lines.append("Do this: astloom sync heal")
    return lines


def print_embedding_heal_guidance(
    summary: dict[str, Any] | None,
    *,
    sync_mode: str = "",
) -> None:
    """Print a Need embedding heal section when the backlog is non-zero."""
    missing, indexed, eligible = missing_embedding_counts(summary)
    if missing <= 0:
        return
    ui.blank()
    ui.section("Need embedding heal")
    ui.kv(
        "Missing",
        f"{missing} of {eligible} searchable symbols  (indexed={indexed})",
    )
    if str(sync_mode or "").strip().lower() == "heal":
        ui.kv("This run", "full-project embedding heal after the incremental file pass")
    else:
        ui.kv(
            "Note",
            "Plain sync only refreshes embeddings for files touched this run "
            "(noop drains a small capped backlog)",
        )
        ui.kv("Do this", "astloom sync heal")


def print_remote_sync_heal_note(*, sync_mode: str = "") -> None:
    """Client remote (content-push) path has no local graph inventory — still guide embeddings mode."""
    ui.blank()
    ui.section("Embeddings (server)")
    if str(sync_mode or "").strip().lower() == "heal":
        ui.kv(
            "This run",
            "full-project embedding heal on the server after the incremental file pass",
        )
    else:
        ui.kv(
            "Note",
            "Plain sync only refreshes embeddings for files touched this run",
        )
        ui.kv(
            "If semantic search is incomplete",
            "re-run with: astloom sync heal",
        )
