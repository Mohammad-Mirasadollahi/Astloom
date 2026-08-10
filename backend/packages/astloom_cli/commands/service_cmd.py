"""`astloom service` and `astloom boot` command handlers."""

from __future__ import annotations

import argparse
from pathlib import Path

from astloom_cli import service_runtime as runtime
from astloom_cli import ui
from astloom_cli.sync_progress import format_duration
from astloom_cli.util import print_json, repo_root


def _print_log_block(title: str, payload: dict) -> None:
    ui.blank()
    ui.section(title)
    path = payload.get("path")
    if path:
        ui.kv("File", str(path))
    if payload.get("exists") is False:
        ui.kv("Content", ui.warn("log file not created yet (process never started)"))
        return
    if payload.get("error"):
        ui.kv("Error", ui.err(str(payload["error"])))
        return
    lines = list(payload.get("lines") or [])
    if not lines:
        ui.kv("Content", ui.dim("(empty)"))
        return
    shown = payload.get("shown")
    total = payload.get("line_count")
    if shown is not None and total is not None:
        ui.kv("Tail", f"last {shown} of {total} lines")
    ui.blank()
    for line in lines:
        print(line)


def _docker_mark(text: str, *, ok: bool) -> str:
    msg = f"docker · {text}"
    return ui.ok(msg) if ok else ui.err(msg)


def _print_compose_started(compose: dict) -> None:
    ui.blank()
    ui.section("Docker")
    if compose.get("ok") is False:
        ui.kv("State", ui.err("failed"))
    service_times = compose.get("service_started_at") or {}
    names = list(compose.get("services") or []) or list(service_times)
    for name in names:
        ts = service_times.get(name) or compose.get("started_at") or "?"
        detail = f"started at {ts}" if compose.get("ok") else f"failed ({ts})"
        ui.kv(str(name), _docker_mark(detail, ok=bool(compose.get("ok"))))


def _print_mcp_started(mcp: dict) -> None:
    ui.blank()
    ui.section("MCP HTTP")
    if not mcp.get("ok"):
        ui.kv("State", ui.err(str(mcp.get("action") or "failed")))
        if mcp.get("log"):
            ui.kv("Log", str(mcp["log"]))
        return
    ts = mcp.get("started_at") or "?"
    bits = [f"started at {ts}"]
    if mcp.get("pid"):
        bits.append(f"pid {mcp['pid']}")
    if mcp.get("host") is not None and mcp.get("port") is not None:
        bits.append(f"{mcp['host']}:{mcp['port']}")
    ui.kv("Process", ui.ok("  ".join(bits)))
    if mcp.get("log"):
        ui.kv("Log", str(mcp["log"]))


def _print_compose_stopped(compose: dict) -> None:
    ui.blank()
    ui.section("Docker")
    names = list(compose.get("services") or [])
    if not names:
        ui.kv("State", _docker_mark("stopped" if compose.get("ok") else "failed", ok=bool(compose.get("ok"))))
        return
    suffix = " (forced)" if compose.get("forced") else ""
    for name in names:
        text = f"stopped{suffix}" if compose.get("ok") else "failed"
        ui.kv(str(name), _docker_mark(text, ok=bool(compose.get("ok"))))


def _print_mcp_stopped(mcp: dict) -> None:
    ui.blank()
    ui.section("MCP HTTP")
    action = str(mcp.get("action") or ("stopped" if mcp.get("ok") else "failed"))
    if action == "already_stopped":
        ui.kv("Process", ui.dim("already stopped"))
        return
    if mcp.get("ok"):
        pid = mcp.get("pid")
        ui.kv("Process", ui.ok(f"stopped (was pid {pid})" if pid else "stopped"))
    else:
        ui.kv("Process", ui.err(action))


def _print_start_report(report: dict) -> None:
    _print_compose_started(report.get("compose") or {})
    _print_mcp_started(report.get("mcp") or {})
    ui.blank()


def _print_stop_report(report: dict) -> None:
    _print_mcp_stopped(report.get("mcp") or {})
    _print_compose_stopped(report.get("compose") or {})
    ui.blank()


def _print_restart_report(report: dict) -> None:
    stop = report.get("stop") or {}
    start = report.get("start") or {}
    ui.blank()
    ui.section("Stopped")
    mcp_stop = stop.get("mcp") or {}
    compose_stop = stop.get("compose") or {}
    action = str(mcp_stop.get("action") or "")
    if action == "already_stopped":
        ui.kv("MCP HTTP", ui.dim("already stopped"))
    elif mcp_stop.get("ok"):
        pid = mcp_stop.get("pid")
        ui.kv("MCP HTTP", ui.ok(f"stopped (was pid {pid})" if pid else "stopped"))
    else:
        ui.kv("MCP HTTP", ui.err(action or "failed"))
    for name in compose_stop.get("services") or []:
        text = "stopped" if compose_stop.get("ok") else "failed"
        if compose_stop.get("forced"):
            text += " (forced)"
        ui.kv(str(name), _docker_mark(text, ok=bool(compose_stop.get("ok"))))

    ui.blank()
    ui.section("Started")
    compose = start.get("compose") or {}
    service_times = compose.get("service_started_at") or {}
    for name in compose.get("services") or []:
        detail = f"started at {service_times.get(name) or compose.get('started_at') or '?'}"
        ui.kv(str(name), _docker_mark(detail if compose.get("ok") else "failed", ok=bool(compose.get("ok"))))
    mcp = start.get("mcp") or {}
    if mcp.get("ok"):
        ts = mcp.get("started_at") or "?"
        bits = [f"started at {ts}"]
        if mcp.get("pid"):
            bits.append(f"pid {mcp['pid']}")
        if mcp.get("host") is not None and mcp.get("port") is not None:
            bits.append(f"{mcp['host']}:{mcp['port']}")
        ui.kv("MCP HTTP", ui.ok("  ".join(bits)))
    else:
        ui.kv("MCP HTTP", ui.err(str(mcp.get("action") or "failed")))
        if mcp.get("log"):
            ui.kv("Log", str(mcp["log"]))
    ui.blank()


def _print_service_status(report: dict, *, detail: dict | None = None) -> None:
    state = str(report.get("status") or "")
    okish = state == "all running"
    ui.blank()
    ui.heading("Service", success=okish)
    ui.blank()
    ui.kv("State", ui.status_badge(state))
    ui.kv("Root", str(report.get("repo_root")))
    if report.get("restarted_at"):
        ui.kv("Restarted", str(report["restarted_at"]))
    if report.get("uptime_sec") is not None:
        ui.kv("UpTime", format_duration(float(report["uptime_sec"])))

    compose = report.get("compose") or {}
    ui.blank()
    ui.section("Docker")
    for name, info in (compose.get("services") or {}).items():
        health = str(info.get("health") or "unknown")
        ui.kv(str(name), _docker_mark(health, ok=health == "healthy"))

    mcp = report.get("mcp") or {}
    ui.blank()
    ui.section("MCP HTTP")
    if mcp.get("running"):
        if mcp.get("managed", mcp.get("pid") is not None):
            ui.kv("Process", ui.ok(f"pid {mcp.get('pid')}"))
        else:
            ui.kv("Process", ui.warn("reachable (pid unavailable)"))
    else:
        ui.kv("Process", ui.err("stopped"))
    ui.kv("Listen", f"{mcp.get('host')}:{mcp.get('port')}")
    reach = ui.ok("yes") if mcp.get("reachable") else ui.err("no")
    ui.kv("Reachable", reach)
    if mcp.get("log"):
        ui.kv("Log", str(mcp["log"]))

    boot = report.get("boot") or {}
    modes = boot.get("modes") or {}
    ui.blank()
    ui.section("Boot")
    for label, info in modes.items():
        enabled = bool(info.get("enabled"))
        present = bool(info.get("unit_file_present"))
        text = "enabled" if enabled else ("unit present" if present else "disabled")
        ui.kv(str(label), ui.ok(text) if enabled else ui.dim(text))

    if detail is not None:
        _print_log_block("Detail — MCP HTTP log", detail.get("mcp_http") or {})
        for name, payload in (detail.get("compose") or {}).items():
            title = f"Detail — Compose {name} log"
            if payload.get("text") is not None and not payload.get("path"):
                ui.blank()
                ui.section(title)
                lines = list(payload.get("lines") or [])
                if payload.get("error"):
                    ui.kv("Error", ui.err(str(payload["error"])))
                elif not lines:
                    ui.kv("Content", ui.dim("(empty)"))
                else:
                    ui.kv("Tail", f"last {len(lines)} lines")
                    ui.blank()
                    for line in lines:
                        print(line)
            else:
                _print_log_block(title, payload)
    elif not okish:
        ui.blank()
        ui.section("Hints")
        ui.bullet("astloom service detail")
        ui.bullet("astloom service start")

    ui.blank()


def _print_mcp_start_failure(root: Path, exc: BaseException) -> int:
    """Surface start/restart failure with log tail (even when empty) and next steps."""
    print(str(exc), flush=True)
    log_path = runtime.mcp_log_path(root)
    ui.blank()
    ui.section("MCP HTTP log (tail)")
    if not log_path.is_file():
        ui.kv("Content", ui.warn(f"log file missing ({log_path})"))
    else:
        tail = runtime.read_log_tail(log_path, lines=80)
        if tail.get("error"):
            ui.kv("Error", ui.err(str(tail["error"])))
        elif not tail.get("text"):
            ui.kv(
                "Content",
                ui.dim("(empty — process may have failed before writing)"),
            )
        else:
            ui.kv("File", str(log_path))
            shown = tail.get("shown")
            total = tail.get("line_count")
            if shown is not None and total is not None:
                ui.kv("Tail", f"last {shown} of {total} lines")
            ui.blank()
            print(tail["text"])
    ui.blank()
    ui.section("Hints")
    ui.bullet("astloom service detail")
    ui.bullet("astloom service start")
    ui.blank()
    return 1


def cmd_service_start(args: argparse.Namespace) -> int:
    root = repo_root()
    ui.blank()
    ui.heading("Starting Astloom")
    try:
        report = runtime.start_all(root)
    except SystemExit as exc:
        return _print_mcp_start_failure(root, exc)
    ui.blank()
    ui.heading(
        "Astloom is up" if report.get("ok") else "Start finished with errors",
        success=bool(report.get("ok")),
    )
    if args.json:
        print_json(report)
    else:
        _print_start_report(report)
    return 0 if report.get("ok") else 1


def cmd_service_stop(args: argparse.Namespace) -> int:
    root = repo_root()
    ui.blank()
    ui.heading("Stopping Astloom", success=False)
    report = runtime.stop_all(root)
    ui.blank()
    ui.heading(
        "Astloom is stopped" if report.get("ok") else "Stop finished with errors",
        success=bool(report.get("ok")),
    )
    if args.json:
        print_json(report)
    else:
        _print_stop_report(report)
    return 0 if report.get("ok") else 1


def cmd_service_restart(args: argparse.Namespace) -> int:
    root = repo_root()
    ui.blank()
    ui.heading("Restarting Astloom")
    try:
        report = runtime.restart_all(root)
    except SystemExit as exc:
        return _print_mcp_start_failure(root, exc)
    ui.blank()
    ui.heading(
        "Astloom restarted — now up" if report.get("ok") else "Restart finished with errors",
        success=bool(report.get("ok")),
    )
    if args.json:
        print_json(report)
    else:
        _print_restart_report(report)
    return 0 if report.get("ok") else 1


def cmd_service_status(args: argparse.Namespace) -> int:
    root = repo_root()
    report = runtime.status_all(root)
    if args.json:
        print_json(report)
    else:
        _print_service_status(report)
    return 0 if report.get("status") == "all running" else 1


def cmd_service_detail(args: argparse.Namespace) -> int:
    root = repo_root()
    report = runtime.status_all(root)
    detail = runtime.collect_detail(root, report, lines=80)
    if args.json:
        print_json({**report, "detail": detail})
    else:
        _print_service_status(report, detail=detail)
    return 0 if report.get("status") == "all running" else 1
def cmd_boot_enable(args: argparse.Namespace) -> int:
    root = repo_root()
    report = runtime.boot_enable(root, user=bool(args.user))
    print_json(report)
    return 0 if report.get("ok") else 1


def cmd_boot_disable(args: argparse.Namespace) -> int:
    report = runtime.boot_disable(user=bool(args.user))
    print_json(report)
    return 0 if report.get("ok") else 1
