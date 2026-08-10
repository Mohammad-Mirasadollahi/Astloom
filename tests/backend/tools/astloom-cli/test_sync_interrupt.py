"""Regression: Ctrl+C during astloom sync exits cleanly (no traceback)."""

from __future__ import annotations

from types import SimpleNamespace

from astloom_cli.commands import sync as sync_cmd
from astloom_cli.commands.sync import cmd as sync_cmd_impl


def test_cmd_sync_keyboard_interrupt_exits_clean(monkeypatch, capsys):
    monkeypatch.setattr(sync_cmd.ui, "_use_color", lambda: False)

    def boom(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(sync_cmd_impl, "_cmd_sync_body", boom)
    code = sync_cmd.cmd_sync(SimpleNamespace())
    assert code == 130
    out = capsys.readouterr().out
    assert "Sync stopped" in out
    assert "graceful shutdown complete" in out
    assert "Traceback" not in out
    assert "KeyboardInterrupt" not in out
