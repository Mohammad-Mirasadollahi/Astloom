"""Human-friendly service start/stop/restart output."""

from __future__ import annotations

from astloom_cli.commands.service_cmd import (
    _print_restart_report,
    _print_start_report,
    _print_stop_report,
)


def test_print_start_report_shows_services_and_mcp(capsys):
    _print_start_report(
        {
            "ok": True,
            "compose": {
                "ok": True,
                "services": ["postgres", "neo4j"],
                "started_at": "2026-07-23 09:29:46",
                "service_started_at": {
                    "postgres": "2026-07-23 09:29:48",
                    "neo4j": "2026-07-23 09:29:48",
                },
            },
            "mcp": {
                "ok": True,
                "started_at": "2026-07-23 09:32:13",
                "pid": 2800080,
                "host": "0.0.0.0",
                "port": 32500,
                "log": "/opt/Astloom/.astloom/run/mcp-http.log",
            },
        }
    )
    out = capsys.readouterr().out
    assert "Docker" in out
    assert "docker · started at 2026-07-23 09:29:48" in out
    assert "postgres" in out
    assert "neo4j" in out
    assert "MCP HTTP" in out
    assert "pid 2800080" in out
    assert "0.0.0.0:32500" in out
    assert "{" not in out


def test_print_stop_report_shows_stopped(capsys):
    _print_stop_report(
        {
            "ok": True,
            "mcp": {"ok": True, "action": "stopped", "pid": 1239257},
            "compose": {
                "ok": True,
                "action": "compose_stop",
                "services": ["postgres", "neo4j"],
                "forced": False,
            },
        }
    )
    out = capsys.readouterr().out
    assert "stopped (was pid 1239257)" in out
    assert "Docker" in out
    assert "docker · stopped" in out
    assert "postgres" in out
    assert "neo4j" in out
    assert "{" not in out


def test_print_restart_report_groups_stop_and_start(capsys):
    _print_restart_report(
        {
            "ok": True,
            "stop": {
                "ok": True,
                "mcp": {"ok": True, "action": "stopped", "pid": 1239257},
                "compose": {
                    "ok": True,
                    "services": ["postgres", "neo4j"],
                    "forced": False,
                },
            },
            "start": {
                "ok": True,
                "compose": {
                    "ok": True,
                    "services": ["postgres", "neo4j"],
                    "service_started_at": {
                        "postgres": "2026-07-23 09:29:48",
                        "neo4j": "2026-07-23 09:29:48",
                    },
                },
                "mcp": {
                    "ok": True,
                    "started_at": "2026-07-23 09:32:13",
                    "pid": 2800080,
                    "host": "0.0.0.0",
                    "port": 32500,
                },
            },
        }
    )
    out = capsys.readouterr().out
    assert "Stopped" in out
    assert "Started" in out
    assert "was pid 1239257" in out
    assert "pid 2800080" in out
    assert "docker · stopped" in out
    assert "docker · started at 2026-07-23 09:29:48" in out
    assert "{" not in out


def test_print_mcp_start_failure_shows_empty_log_and_hints(tmp_path, capsys, monkeypatch):
    from astloom_cli.commands import service_cmd as cmd

    log = tmp_path / "mcp-http.log"
    log.write_text("", encoding="utf-8")
    monkeypatch.setattr(cmd.runtime, "mcp_log_path", lambda _r: log)
    code = cmd._print_mcp_start_failure(
        tmp_path,
        SystemExit(
            "error: MCP HTTP not reachable on 127.0.0.1:32500\n"
            "  next: astloom service detail"
        ),
    )
    assert code == 1
    out = capsys.readouterr().out
    assert "not reachable" in out
    assert "empty" in out.lower()
    assert "astloom service detail" in out
    assert "astloom service start" in out
