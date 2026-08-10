"""Tests for CLI terminal styling helpers."""

from __future__ import annotations

from astloom_cli import ui


def test_paint_disabled_without_tty(monkeypatch):
    monkeypatch.setattr(ui, "_use_color", lambda: False)
    assert ui.ok("ready") == "ready"
    assert ui.scope_line("a", "b", "c") == "a / b / c"


def test_summarize_paths_relative():
    paths = ui.summarize_paths(
        ["/opt/Astloom/.cursor/mcp.json", "/opt/Astloom/.vscode/mcp.json"],
        relative_to="/opt/Astloom",
    )
    assert paths == [".cursor/mcp.json", ".vscode/mcp.json"]
