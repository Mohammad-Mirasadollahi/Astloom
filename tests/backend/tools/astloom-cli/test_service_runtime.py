"""Tests for astloom service / boot process control."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from astloom_cli.parser import build_parser
from astloom_cli import service_runtime as runtime


def _stub_compose_stack(root: Path) -> None:
    compose = root / "backend" / "deployments" / "compose"
    compose.mkdir(parents=True, exist_ok=True)
    (compose / "compose.yaml").write_text("name: x\n", encoding="utf-8")
    (compose / ".env.local").write_text("A=1\n", encoding="utf-8")


def test_local_compose_stack_absent_for_client_role(tmp_path: Path):
    _stub_compose_stack(tmp_path)
    assert runtime.local_compose_stack_present(tmp_path) is True
    state = tmp_path / ".astloom"
    state.mkdir(parents=True, exist_ok=True)
    (state / "install-state.env").write_text("role=client\n", encoding="utf-8")
    assert runtime.install_role(tmp_path) == "client"
    assert runtime.local_compose_stack_present(tmp_path) is False


def test_local_compose_stack_present_for_both_role(tmp_path: Path):
    _stub_compose_stack(tmp_path)
    state = tmp_path / ".astloom"
    state.mkdir(parents=True, exist_ok=True)
    (state / "install-state.env").write_text("role=both\n", encoding="utf-8")
    assert runtime.install_role(tmp_path) == "both"
    assert runtime.local_compose_stack_present(tmp_path) is True


def test_ensure_running_client_role_exits_even_with_compose_files(tmp_path: Path):
    _stub_compose_stack(tmp_path)
    state = tmp_path / ".astloom"
    state.mkdir(parents=True, exist_ok=True)
    (state / "install-state.env").write_text("role=client\n", encoding="utf-8")
    try:
        runtime.ensure_running_or_offer_start(tmp_path, stdin_isatty=True)
        raised = False
    except SystemExit as exc:
        raised = True
        msg = str(exc)
        assert "Client installs" in msg
        assert "install role=client" in msg
        assert "local Compose sync is disabled" in msg
    assert raised


def test_missing_local_stack_message_client_role_not_missing_env(tmp_path: Path):
    _stub_compose_stack(tmp_path)
    state = tmp_path / ".astloom"
    state.mkdir(parents=True, exist_ok=True)
    (state / "install-state.env").write_text("role=client\n", encoding="utf-8")
    msg = runtime.missing_local_stack_message(tmp_path)
    assert "local Compose sync is disabled" in msg
    assert "missing " not in msg.split("(", 1)[1].split(")", 1)[0]


def test_parser_service_and_boot():
    parser = build_parser()
    start = parser.parse_args(["service", "start"])
    assert start.command == "service"
    assert start.service_command == "start"

    status = parser.parse_args(["service", "status", "--json"])
    assert status.service_command == "status"
    assert status.json is True

    detail = parser.parse_args(["service", "detail"])
    assert detail.service_command == "detail"

    enable = parser.parse_args(["boot", "enable", "--user"])
    assert enable.command == "boot"
    assert enable.boot_command == "enable"
    assert enable.user is True

    disable = parser.parse_args(["boot", "disable"])
    assert disable.boot_command == "disable"
    assert disable.user is False


def test_read_log_tail(tmp_path: Path):
    missing = runtime.read_log_tail(tmp_path / "no.log", lines=10)
    assert missing["exists"] is False
    assert missing["lines"] == []

    path = tmp_path / "mcp-http.log"
    path.write_text("\n".join(f"line-{i}" for i in range(1, 21)) + "\n", encoding="utf-8")
    tail = runtime.read_log_tail(path, lines=5)
    assert tail["exists"] is True
    assert tail["shown"] == 5
    assert tail["lines"] == ["line-16", "line-17", "line-18", "line-19", "line-20"]


def test_collect_detail_includes_mcp_log(tmp_path: Path, monkeypatch):
    log = runtime.mcp_log_path(tmp_path)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("boom\ntrace\n", encoding="utf-8")
    report = {
        "mcp": {"log": str(log), "running": False},
        "compose": {"services": {"postgres": {"health": "healthy"}, "neo4j": {"health": "unhealthy"}}},
    }
    monkeypatch.setattr(
        runtime,
        "compose_logs_tail",
        lambda _r, service, *, lines=80: {
            "service": service,
            "ok": True,
            "text": f"{service}-log",
            "lines": [f"{service}-log"],
        },
    )
    detail = runtime.collect_detail(tmp_path, report, lines=10)
    assert "boom" in detail["mcp_http"]["text"]
    assert "neo4j" in detail["compose"]
    assert "postgres" not in detail["compose"]

def test_compose_base_cmd_requires_files(tmp_path: Path):
    try:
        runtime.compose_base_cmd(tmp_path)
        raised = False
    except SystemExit as exc:
        raised = True
        assert "compose file" in str(exc)
    assert raised


def test_compose_base_cmd_missing_env_mentions_client(tmp_path: Path):
    compose = tmp_path / "backend" / "deployments" / "compose"
    compose.mkdir(parents=True)
    (compose / "compose.yaml").write_text("name: x\n", encoding="utf-8")
    try:
        runtime.compose_base_cmd(tmp_path)
        raised = False
    except SystemExit as exc:
        raised = True
        msg = str(exc)
        assert ".env.local" in msg
        assert "Client installs" in msg
        assert "run bash install.sh)" not in msg
    assert raised


def test_compose_status_without_stack_is_soft(tmp_path: Path):
    report = runtime.compose_status(tmp_path)
    assert report["ok"] is False
    assert report["stack_present"] is False
    assert report["services"]["postgres"]["health"] == "missing"
    assert report["services"]["neo4j"]["health"] == "missing"


def test_compose_base_cmd_ok(tmp_path: Path):
    _stub_compose_stack(tmp_path)
    cmd = runtime.compose_base_cmd(tmp_path)
    assert cmd[:2] == ["docker", "compose"]
    assert str(tmp_path / "backend" / "deployments" / "compose" / ".env.local") in cmd
    assert str(tmp_path / "backend" / "deployments" / "compose" / "compose.yaml") in cmd


def test_read_mcp_pid_clears_stale(tmp_path: Path, monkeypatch):
    pid_path = runtime.mcp_pid_path(tmp_path)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text("999999\n", encoding="utf-8")
    monkeypatch.setattr(runtime, "_pid_alive", lambda _pid: False)
    assert runtime.read_mcp_pid(tmp_path) is None
    assert not pid_path.is_file()


def test_start_all_calls_compose_https_and_mcp(tmp_path: Path, monkeypatch, capsys):
    from astloom_cli.service_runtime import lifecycle

    calls: list[str] = []

    def fake_compose(_root: Path):
        calls.append("compose")
        return {"ok": True}

    def fake_https(_root: Path):
        calls.append("https")
        return {"ok": True, "pid": 2}

    def fake_mcp(_root: Path):
        calls.append("mcp")
        return {"ok": True, "pid": 1}

    monkeypatch.setattr(runtime, "start_compose", fake_compose)
    monkeypatch.setattr(runtime, "start_https_apis", fake_https)
    monkeypatch.setattr(runtime, "start_mcp_http", fake_mcp)
    monkeypatch.setattr(lifecycle, "_run_port_preflight", lambda _root: None)
    report = runtime.start_all(tmp_path)
    assert report["ok"] is True
    assert calls == ["compose", "https", "mcp"]
    out = capsys.readouterr().out
    assert "Starting Astloom" in out
    assert "Astloom is up" in out
    assert "code-graph HTTPS" in out


def test_run_port_preflight_passes_repo_root(tmp_path: Path, monkeypatch):
    """Start preflight must hand the checkout root down so our own venv services are adopted."""
    import port_profile
    from astloom_cli.service_runtime import lifecycle

    captured: dict = {}

    def fake_run_preflight(_profile, **kwargs):
        captured.update(kwargs)
        return {"ok": True, "ports": {}, "resolved": {}, "conflicts": []}

    monkeypatch.setattr(port_profile, "run_preflight", fake_run_preflight)
    lifecycle._run_port_preflight(tmp_path)

    assert captured.get("repo_root") == tmp_path
    assert captured.get("allow_ours") is True


def test_restart_all_stop_then_start(tmp_path: Path, monkeypatch, capsys):
    order: list[str] = []

    def fake_stop(_r, *, as_part_of=None):
        order.append(("stop", as_part_of))
        return {"ok": True}

    def fake_start(_r, *, as_part_of=None):
        order.append(("start", as_part_of))
        return {"ok": True}

    monkeypatch.setattr(runtime, "stop_all", fake_stop)
    monkeypatch.setattr(runtime, "start_all", fake_start)
    report = runtime.restart_all(tmp_path)
    assert report["ok"] is True
    assert order == [("stop", "restart"), ("start", "restart")]
    out = capsys.readouterr().out
    assert "Restarting Astloom" in out
    assert "Restart complete — Astloom is up" in out


def test_stop_all_logs_shutdown_steps(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(runtime, "stop_mcp_http", lambda _r: {"ok": True, "action": "stopped"})
    monkeypatch.setattr(runtime, "stop_https_apis", lambda _r: {"ok": True, "action": "stopped"})
    monkeypatch.setattr(runtime, "stop_compose", lambda _r: {"ok": True, "action": "compose_stop"})
    report = runtime.stop_all(tmp_path)
    assert report["ok"] is True
    out = capsys.readouterr().out
    assert "Stopping Astloom" in out
    assert "Astloom is stopped" in out


def test_stop_compose_passes_docker_timeout(tmp_path: Path, monkeypatch, capsys):
    import subprocess

    from astloom_cli.service_runtime import compose as compose_mod

    compose = tmp_path / "backend" / "deployments" / "compose"
    compose.mkdir(parents=True)
    (compose / "compose.yaml").write_text("name: x\n", encoding="utf-8")
    (compose / ".env.local").write_text("A=1\n", encoding="utf-8")

    seen: list[list[str]] = []

    def fake_run(cmd, *, cwd, check=False, timeout=None):
        seen.append(list(cmd))
        assert timeout == compose_mod.COMPOSE_STOP_WAIT_SEC
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(compose_mod, "run_cmd", fake_run)
    report = compose_mod.stop_compose(tmp_path)
    assert report["ok"] is True
    assert report["forced"] is False
    assert "stop" in seen[0]
    t_idx = seen[0].index("--timeout")
    assert seen[0][t_idx + 1] == str(compose_mod.COMPOSE_STOP_TIMEOUT_SEC)
    out = capsys.readouterr().out
    assert "Databases: stopping" in out
    assert "Databases: stopped" in out


def test_stop_compose_force_kills_on_timeout(tmp_path: Path, monkeypatch, capsys):
    import subprocess

    from astloom_cli.service_runtime import compose as compose_mod

    compose = tmp_path / "backend" / "deployments" / "compose"
    compose.mkdir(parents=True)
    (compose / "compose.yaml").write_text("name: x\n", encoding="utf-8")
    (compose / ".env.local").write_text("A=1\n", encoding="utf-8")

    calls: list[str] = []

    def fake_run(cmd, *, cwd, check=False, timeout=None):
        if "stop" in cmd:
            calls.append("stop")
            raise subprocess.TimeoutExpired(cmd, timeout or 0)
        calls.append("kill")
        assert "kill" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(compose_mod, "run_cmd", fake_run)
    report = compose_mod.stop_compose(tmp_path)
    assert report["ok"] is True
    assert report["forced"] is True
    assert calls == ["stop", "kill"]
    out = capsys.readouterr().out
    assert "forcing kill" in out
    assert "stopped (forced)" in out


def test_main_keyboard_interrupt_is_clean(monkeypatch, capsys):
    from astloom_cli import main as main_mod

    def boom(_argv=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(main_mod, "_dispatch", boom)
    assert main_mod.main([]) == 130
    out = capsys.readouterr().out
    assert "Interrupted" in out
    assert "service status" in out


def test_unit_body_contains_start_stop(tmp_path: Path):
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    exe = venv / "astloom"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    body = runtime.unit_body(tmp_path, user=True)
    assert "service start" in body
    assert "service stop" in body
    assert str(exe) in body
    assert "WantedBy=default.target" in body


def test_boot_enable_writes_user_unit(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    root = tmp_path / "repo"
    (root / ".venv" / "bin").mkdir(parents=True)
    (root / ".venv" / "bin" / "astloom").write_text("x", encoding="utf-8")

    def fake_systemctl(args, *, user):
        assert user is True
        return SimpleNamespace(returncode=0, stdout="enabled\n", stderr="")

    monkeypatch.setattr(runtime, "_systemctl", fake_systemctl)
    report = runtime.boot_enable(root, user=True)
    unit = home / ".config" / "systemd" / "user" / runtime.UNIT_NAME
    assert unit.is_file()
    assert "ExecStart=" in unit.read_text(encoding="utf-8")
    assert report["ok"] is True
    assert report["user"] is True


def test_boot_disable_removes_user_unit(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    unit = home / ".config" / "systemd" / "user" / runtime.UNIT_NAME
    unit.parent.mkdir(parents=True)
    unit.write_text("[Unit]\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(
        runtime,
        "_systemctl",
        lambda *_a, **_k: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    report = runtime.boot_disable(user=True)
    assert report["ok"] is True
    assert not unit.is_file()


def test_prepare_mcp_env_creates_secret(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_MCP_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_HTTP_TOKEN", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_HTTP_PUBLIC_URL", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_TLS", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_TLS_CERTFILE", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_TLS_KEYFILE", raising=False)
    monkeypatch.setenv("ASTLOOM_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setattr(
        "astloom_cli.cli_defaults.load_dotenv_files",
        lambda **_: [],
    )
    monkeypatch.setattr(
        "astloom_cli.remote_client.apply_compose_env_to_os",
        lambda _e, _r: (_ for _ in ()).throw(SystemExit("skip")),
    )
    env = runtime.prepare_mcp_env(tmp_path)
    secret = runtime.mcp_secret_path(tmp_path)
    assert secret.is_file()
    assert env["ASTLOOM_MCP_TOKEN_SECRET"] == secret.read_text(encoding="utf-8").strip()
    assert env["ASTLOOM_MCP_HTTP_PORT"] == str(runtime.DEFAULT_MCP_PORT)
    assert env.get("PYTHONUNBUFFERED") == "1"
    assert env["ASTLOOM_MCP_HTTP_PUBLIC_URL"].startswith("https://")
    assert Path(env["ASTLOOM_MCP_TLS_CERTFILE"]).is_file()
    assert Path(env["ASTLOOM_MCP_TLS_KEYFILE"]).is_file()


def test_prepare_mcp_env_loads_bootstrap_secret(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_MCP_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_HTTP_TOKEN", raising=False)
    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_HTTP_PUBLIC_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setattr(
        "astloom_cli.cli_defaults.load_dotenv_files",
        lambda **_: [],
    )
    monkeypatch.setattr(
        "astloom_cli.remote_client.apply_compose_env_to_os",
        lambda _e, _r: (_ for _ in ()).throw(SystemExit("skip")),
    )
    boot = tmp_path / ".astloom" / "connect-bootstrap.secret"
    boot.parent.mkdir(parents=True)
    boot.write_text("bootstrap-from-file\n", encoding="utf-8")
    env = runtime.prepare_mcp_env(tmp_path)
    assert env["ASTLOOM_CONNECT_BOOTSTRAP_SECRET"] == "bootstrap-from-file"
    assert runtime.mcp_secret_path(tmp_path).is_file()
    assert env["ASTLOOM_MCP_HTTP_PUBLIC_URL"].startswith("https://")


def test_prepare_mcp_env_tls_off_keeps_http_public_url(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_MCP_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_HTTP_TOKEN", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_HTTP_PUBLIC_URL", raising=False)
    monkeypatch.setenv("ASTLOOM_MCP_TLS", "0")
    monkeypatch.setenv("ASTLOOM_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setattr(
        "astloom_cli.cli_defaults.load_dotenv_files",
        lambda **_: [],
    )
    monkeypatch.setattr(
        "astloom_cli.remote_client.apply_compose_env_to_os",
        lambda _e, _r: (_ for _ in ()).throw(SystemExit("skip")),
    )
    env = runtime.prepare_mcp_env(tmp_path)
    assert env["ASTLOOM_MCP_HTTP_PUBLIC_URL"].startswith("http://")
    assert "ASTLOOM_MCP_TLS_CERTFILE" not in env or not env.get("ASTLOOM_MCP_TLS_CERTFILE")


def test_service_state_names_what_is_wrong():
    compose_ok = {"ok": True, "services": {}}
    compose_bad = {"ok": False, "services": {}}
    mcp_ok = {"ok": True, "running": True, "reachable": True}
    mcp_stopped = {"ok": False, "running": False, "reachable": False}
    mcp_unreachable = {"ok": False, "running": True, "reachable": False}
    graph_ok = {"ok": True, "running": True, "reachable": True}
    graph_stopped = {"ok": False, "running": False, "reachable": False}
    graph_unreachable = {"ok": False, "running": True, "reachable": False}
    assert runtime.service_state(compose_ok, mcp_ok, graph_ok) == "all running"
    assert runtime.service_state(compose_ok, mcp_ok, graph_stopped) == "code-graph HTTPS stopped"
    assert (
        runtime.service_state(compose_ok, mcp_ok, graph_unreachable)
        == "code-graph HTTPS not reachable"
    )
    assert runtime.service_state(compose_ok, mcp_stopped, graph_ok) == "MCP HTTP stopped"
    assert runtime.service_state(compose_bad, mcp_stopped, graph_stopped) == "stopped"
    assert runtime.service_state(compose_ok, mcp_unreachable, graph_ok) == "MCP HTTP not reachable"
    assert "degraded" not in {
        runtime.service_state(compose_ok, mcp_stopped, graph_ok),
        runtime.service_state(compose_bad, mcp_ok, graph_ok),
    }


def test_mcp_status_reachable_without_pid_is_operational(tmp_path: Path, monkeypatch):
    from astloom_cli.service_runtime import mcp as mcp_mod

    monkeypatch.setattr(mcp_mod, "read_mcp_pid", lambda _root: None)
    monkeypatch.setattr(mcp_mod, "tcp_ok", lambda _host, _port: True)
    monkeypatch.setattr(mcp_mod, "_discover_managed_mcp_pid", lambda _root, _port: None)
    status = mcp_mod.mcp_status(tmp_path)
    assert status["ok"] is True
    assert status["running"] is True
    assert status["managed"] is False
    assert runtime.service_state(
        {"ok": True},
        status,
        {"ok": True, "running": True, "reachable": True},
    ) == "all running"


def test_format_docker_started_at_to_local_seconds():
    stamp = runtime._format_docker_started_at("2026-07-22T05:40:15.123456789Z")
    assert len(stamp) == 19
    assert stamp[4] == "-" and stamp[10] == " " and stamp[13] == ":"
    assert stamp.endswith("15") or stamp[17:19].isdigit()


def test_wall_clock_now_has_seconds():
    stamp = runtime.wall_clock_now()
    assert len(stamp) == 19
    datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")


def test_stack_restarted_at_picks_latest():
    assert (
        runtime.stack_restarted_at(
            "2026-07-22 09:10:01",
            "2026-07-22 09:10:04",
            "2026-07-22 09:10:02",
        )
        == "2026-07-22 09:10:04"
    )
    assert runtime.stack_restarted_at(None, "", "bad") is None


def test_uptime_seconds_since():
    now = datetime(2026, 7, 22, 10, 10, 4)
    assert runtime.uptime_seconds_since("2026-07-22 09:10:04", now=now) == 3600
    assert runtime.uptime_seconds_since("not-a-stamp", now=now) is None


def test_format_process_started_at_self():
    stamp = runtime.format_process_started_at(os.getpid())
    assert stamp is not None
    datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")


def test_status_all_includes_restarted_and_uptime(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "astloom_cli.cli_defaults.load_dotenv_files",
        lambda **_: [],
    )
    monkeypatch.setattr(
        runtime,
        "compose_status",
        lambda _r: {
            "ok": True,
            "services": {
                "postgres": {
                    "running": True,
                    "health": "healthy",
                    "started_at": "2026-07-22 09:10:01",
                },
                "neo4j": {
                    "running": True,
                    "health": "healthy",
                    "started_at": "2026-07-22 09:10:02",
                },
            },
        },
    )
    monkeypatch.setattr(
        runtime,
        "mcp_status",
        lambda _r: {
            "ok": True,
            "running": True,
            "reachable": True,
            "pid": 42,
            "started_at": "2026-07-22 09:10:04",
            "host": "0.0.0.0",
            "port": 32500,
            "log": "/tmp/mcp.log",
        },
    )
    monkeypatch.setattr(
        runtime,
        "boot_status",
        lambda _r: {"modes": {}},
    )
    report = runtime.status_all(tmp_path)
    assert report["status"] == "all running"
    assert report["restarted_at"] == "2026-07-22 09:10:04"
    assert isinstance(report["uptime_sec"], int)
    assert report["uptime_sec"] >= 0


def test_ensure_running_skips_when_already_up(tmp_path: Path, monkeypatch):
    _stub_compose_stack(tmp_path)
    monkeypatch.setattr(
        runtime,
        "status_all",
        lambda _r: {"status": "all running"},
    )
    started = False

    def boom(_r):
        nonlocal started
        started = True
        raise AssertionError("must not start")

    monkeypatch.setattr(runtime, "start_all", boom)
    assert runtime.ensure_running_or_offer_start(tmp_path) is None
    assert started is False


def test_ensure_running_client_stack_exits(tmp_path: Path):
    try:
        runtime.ensure_running_or_offer_start(tmp_path, stdin_isatty=False)
        raised = False
    except SystemExit as exc:
        raised = True
        assert "Client installs" in str(exc)
        assert ".env.local" in str(exc)
    assert raised


def test_ensure_running_non_tty_exits(tmp_path: Path, monkeypatch):
    _stub_compose_stack(tmp_path)
    monkeypatch.setattr(
        runtime,
        "status_all",
        lambda _r: {"status": "stopped"},
    )
    try:
        runtime.ensure_running_or_offer_start(tmp_path, stdin_isatty=False)
        raised = False
    except SystemExit as exc:
        raised = True
        assert "astloom service start" in str(exc)
        assert "stopped" in str(exc)
    assert raised


def test_ensure_running_decline_cancels(tmp_path: Path, monkeypatch):
    _stub_compose_stack(tmp_path)
    monkeypatch.setattr(
        runtime,
        "status_all",
        lambda _r: {"status": "stopped"},
    )
    monkeypatch.setattr(runtime, "start_all", lambda _r: (_ for _ in ()).throw(AssertionError()))
    try:
        runtime.ensure_running_or_offer_start(
            tmp_path,
            input_fn=lambda _p: "n",
            stdin_isatty=True,
        )
        raised = False
    except SystemExit as exc:
        raised = True
        assert "cancelled" in str(exc)
    assert raised


def test_ensure_running_yes_starts_then_ok(tmp_path: Path, monkeypatch):
    _stub_compose_stack(tmp_path)
    calls = {"status": 0, "start": 0}

    def fake_status(_r):
        calls["status"] += 1
        if calls["start"] == 0:
            return {"status": "stopped"}
        return {"status": "all running"}

    def fake_start(_r):
        calls["start"] += 1
        return {
            "ok": True,
            "compose": {
                "ok": True,
                "started_at": "2026-07-22 09:10:01",
                "services": ["postgres", "neo4j"],
                "service_started_at": {
                    "postgres": "2026-07-22 09:10:02",
                    "neo4j": "2026-07-22 09:10:03",
                },
            },
            "mcp": {
                "ok": True,
                "started_at": "2026-07-22 09:10:04",
                "pid": 42,
                "host": "0.0.0.0",
                "port": 32500,
            },
        }

    monkeypatch.setattr(runtime, "status_all", fake_status)
    monkeypatch.setattr(runtime, "start_all", fake_start)
    report = runtime.ensure_running_or_offer_start(
        tmp_path,
        input_fn=lambda _p: "yes",
        stdin_isatty=True,
    )
    assert report is not None
    assert report["ok"] is True
    assert calls["start"] == 1
    assert calls["status"] == 2


def test_ensure_running_yes_but_still_down(tmp_path: Path, monkeypatch):
    _stub_compose_stack(tmp_path)
    monkeypatch.setattr(
        runtime,
        "status_all",
        lambda _r: {"status": "Compose not healthy"},
    )
    monkeypatch.setattr(
        runtime,
        "start_all",
        lambda _r: {"ok": False, "compose": {}, "mcp": {}},
    )
    try:
        runtime.ensure_running_or_offer_start(
            tmp_path,
            input_fn=lambda _p: "y",
            stdin_isatty=True,
        )
        raised = False
    except SystemExit as exc:
        raised = True
        assert "still not fully running" in str(exc)
        assert "service detail" in str(exc)
    assert raised


def test_stop_mcp_gateway_uses_app_profile(tmp_path: Path, monkeypatch, capsys):
    import subprocess

    from astloom_cli.service_runtime import compose as compose_mod

    compose = tmp_path / "backend" / "deployments" / "compose"
    compose.mkdir(parents=True)
    (compose / "compose.yaml").write_text("name: x\n", encoding="utf-8")
    (compose / ".env.local").write_text("A=1\n", encoding="utf-8")

    seen: list[list[str]] = []

    def fake_run(cmd, *, cwd, check=False, timeout=None):
        seen.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(compose_mod, "run_cmd", fake_run)
    report = compose_mod.stop_mcp_gateway(tmp_path)
    assert report["ok"] is True
    assert report["action"] == "mcp_gateway_stop"
    assert "mcp-gateway" in seen[0]
    assert seen[0].count("--profile") == 2
    assert "core" in seen[0]
    assert "app" in seen[0]
    out = capsys.readouterr().out
    assert "host owns the port" in out


def test_start_mcp_http_refuses_when_port_still_busy(tmp_path: Path, monkeypatch):
    """Regression: docker mcp-gateway on :32500 made start report ok while host died."""
    import subprocess

    from astloom_cli.service_runtime import compose as compose_mod
    from astloom_cli.service_runtime import mcp as mcp_mod

    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(mcp_mod, "read_mcp_pid", lambda _r: None)
    monkeypatch.setattr(
        mcp_mod,
        "mcp_status",
        lambda _r: {
            "running": False,
            "managed": False,
            "pid": None,
            "reachable": False,
        },
    )
    monkeypatch.setattr(
        mcp_mod,
        "prepare_mcp_env",
        lambda _r: {
            "ASTLOOM_MCP_HTTP_HOST": "0.0.0.0",
            "ASTLOOM_MCP_HTTP_PORT": "32500",
            "PATH": os.environ.get("PATH", ""),
        },
    )
    monkeypatch.setattr(compose_mod, "stop_mcp_gateway", lambda _r: {"ok": True})
    monkeypatch.setattr(mcp_mod, "_wait_port_free", lambda *_a, **_k: False)
    launched: list[object] = []

    def boom(*_a, **_k):
        launched.append(1)
        raise AssertionError("must not launch when port is busy")

    monkeypatch.setattr(subprocess, "Popen", boom)
    try:
        mcp_mod.start_mcp_http(tmp_path)
        raised = False
        msg = ""
    except SystemExit as exc:
        raised = True
        msg = str(exc)
    assert raised
    assert "still in use" in msg
    assert "next: astloom service detail" in msg
    assert launched == []


def test_start_mcp_http_clears_pid_when_process_exits_early(tmp_path: Path, monkeypatch):
    import subprocess

    from astloom_cli.service_runtime import compose as compose_mod
    from astloom_cli.service_runtime import mcp as mcp_mod

    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(mcp_mod, "read_mcp_pid", lambda _r: None)
    monkeypatch.setattr(
        mcp_mod,
        "prepare_mcp_env",
        lambda _r: {
            "ASTLOOM_MCP_HTTP_HOST": "127.0.0.1",
            "ASTLOOM_MCP_HTTP_PORT": "32500",
            "PATH": os.environ.get("PATH", ""),
        },
    )
    monkeypatch.setattr(compose_mod, "stop_mcp_gateway", lambda _r: {"ok": True})
    monkeypatch.setattr(mcp_mod, "_wait_port_free", lambda *_a, **_k: True)
    monkeypatch.setattr(mcp_mod, "tcp_ok", lambda *_a, **_k: False)

    class DeadProc:
        pid = 4242
        returncode = 1

        def poll(self):
            return 1

    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: DeadProc())
    pid_path = mcp_mod.mcp_pid_path(tmp_path)
    try:
        mcp_mod.start_mcp_http(tmp_path)
        raised = False
        msg = ""
    except SystemExit as exc:
        raised = True
        msg = str(exc)
    assert raised
    assert "exited before becoming reachable" in msg
    assert "exit_code: 1" in msg
    assert "next: astloom service detail" in msg
    assert not pid_path.is_file()


def test_start_mcp_http_not_reachable_reports_wait_budget_and_exit(
    tmp_path: Path, monkeypatch
):
    import subprocess
    import time

    from astloom_cli.service_runtime import compose as compose_mod
    from astloom_cli.service_runtime import mcp as mcp_mod
    from astloom_cli.service_runtime.paths import MCP_HTTP_READY_TIMEOUT_SEC

    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(mcp_mod, "read_mcp_pid", lambda _r: None)
    monkeypatch.setattr(
        mcp_mod,
        "prepare_mcp_env",
        lambda _r: {
            "ASTLOOM_MCP_HTTP_HOST": "127.0.0.1",
            "ASTLOOM_MCP_HTTP_PORT": "32500",
            "PATH": os.environ.get("PATH", ""),
        },
    )
    monkeypatch.setattr(compose_mod, "stop_mcp_gateway", lambda _r: {"ok": True})
    monkeypatch.setattr(mcp_mod, "_wait_port_free", lambda *_a, **_k: True)
    monkeypatch.setattr(mcp_mod, "tcp_ok", lambda *_a, **_k: False)
    monkeypatch.setattr(mcp_mod, "MCP_HTTP_READY_TIMEOUT_SEC", 0.0)
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    class LiveThenDead:
        pid = 9090
        returncode = None
        _alive = True

        def poll(self):
            return None if self._alive else -15

    proc = LiveThenDead()

    def fake_terminate(p):
        p._alive = False
        return -15

    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: proc)
    monkeypatch.setattr(mcp_mod, "_terminate_mcp_proc", fake_terminate)
    pid_path = mcp_mod.mcp_pid_path(tmp_path)
    try:
        mcp_mod.start_mcp_http(tmp_path)
        raised = False
        msg = ""
    except SystemExit as exc:
        raised = True
        msg = str(exc)
    assert raised
    assert "not reachable" in msg
    assert f"/ {MCP_HTTP_READY_TIMEOUT_SEC:.0f}s budget" in msg or "/ 0s budget" in msg
    assert "exit_code: -15" in msg
    assert "next: astloom service detail" in msg
    assert not pid_path.is_file()


def test_start_mcp_http_launch_oserror_is_actionable(tmp_path: Path, monkeypatch):
    import subprocess

    from astloom_cli.service_runtime import compose as compose_mod
    from astloom_cli.service_runtime import mcp as mcp_mod

    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(mcp_mod, "read_mcp_pid", lambda _r: None)
    monkeypatch.setattr(
        mcp_mod,
        "prepare_mcp_env",
        lambda _r: {
            "ASTLOOM_MCP_HTTP_HOST": "127.0.0.1",
            "ASTLOOM_MCP_HTTP_PORT": "32500",
            "PATH": os.environ.get("PATH", ""),
        },
    )
    monkeypatch.setattr(compose_mod, "stop_mcp_gateway", lambda _r: {"ok": True})
    monkeypatch.setattr(mcp_mod, "_wait_port_free", lambda *_a, **_k: True)

    def boom(*_a, **_k):
        raise OSError("Permission denied")

    monkeypatch.setattr(subprocess, "Popen", boom)
    try:
        mcp_mod.start_mcp_http(tmp_path)
        raised = False
        msg = ""
    except SystemExit as exc:
        raised = True
        msg = str(exc)
    assert raised
    assert "failed to launch" in msg
    assert "Permission denied" in msg
    assert "next: astloom service detail" in msg


def test_start_mcp_http_ok_when_own_process_reachable(tmp_path: Path, monkeypatch, capsys):
    import subprocess

    from astloom_cli.service_runtime import compose as compose_mod
    from astloom_cli.service_runtime import mcp as mcp_mod

    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(mcp_mod, "read_mcp_pid", lambda _r: None)
    monkeypatch.setattr(
        mcp_mod,
        "prepare_mcp_env",
        lambda _r: {
            "ASTLOOM_MCP_HTTP_HOST": "0.0.0.0",
            "ASTLOOM_MCP_HTTP_PORT": "32500",
            "PATH": os.environ.get("PATH", ""),
        },
    )
    monkeypatch.setattr(compose_mod, "stop_mcp_gateway", lambda _r: {"ok": True})
    monkeypatch.setattr(mcp_mod, "_wait_port_free", lambda *_a, **_k: True)
    monkeypatch.setattr(mcp_mod, "tcp_ok", lambda *_a, **_k: True)

    class LiveProc:
        pid = 7777
        returncode = None

        def poll(self):
            return None

    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: LiveProc())
    report = mcp_mod.start_mcp_http(tmp_path)
    assert report["ok"] is True
    assert report["pid"] == 7777
    assert report["action"] == "started"
    assert mcp_mod.mcp_pid_path(tmp_path).read_text(encoding="utf-8").strip() == "7777"
    out = capsys.readouterr().out
    assert "is up on" in out


def test_start_mcp_http_ready_wait_covers_cold_start_beyond_six_seconds(
    tmp_path: Path, monkeypatch
):
    """Regression: cold MCP bind is ~4–8s; old 30×0.2s budget killed a live process."""
    import subprocess
    import time

    from astloom_cli.service_runtime import compose as compose_mod
    from astloom_cli.service_runtime import mcp as mcp_mod
    from astloom_cli.service_runtime.paths import MCP_HTTP_READY_TIMEOUT_SEC

    assert MCP_HTTP_READY_TIMEOUT_SEC >= 30.0

    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(mcp_mod, "read_mcp_pid", lambda _r: None)
    monkeypatch.setattr(
        mcp_mod,
        "prepare_mcp_env",
        lambda _r: {
            "ASTLOOM_MCP_HTTP_HOST": "127.0.0.1",
            "ASTLOOM_MCP_HTTP_PORT": "32500",
            "PATH": os.environ.get("PATH", ""),
        },
    )
    monkeypatch.setattr(compose_mod, "stop_mcp_gateway", lambda _r: {"ok": True})
    monkeypatch.setattr(mcp_mod, "_wait_port_free", lambda *_a, **_k: True)
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    polls = {"n": 0}

    def fake_tcp(*_a, **_k):
        polls["n"] += 1
        # Succeed only after the old 6s / 30-poll budget would have given up.
        return polls["n"] >= 40

    monkeypatch.setattr(mcp_mod, "tcp_ok", fake_tcp)

    class LiveProc:
        pid = 8888
        returncode = None

        def poll(self):
            return None

    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: LiveProc())
    report = mcp_mod.start_mcp_http(tmp_path)
    assert report["ok"] is True
    assert report["pid"] == 8888
    assert polls["n"] >= 40
