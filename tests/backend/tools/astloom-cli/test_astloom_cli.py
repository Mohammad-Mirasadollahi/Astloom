import json
import os
import sys
from pathlib import Path

from astloom_cli.main import main
from astloom_cli.util import ensure_service_import_paths


def test_service_import_paths_use_install_checkout_when_state_root_is_isolated(
    tmp_path: Path,
    monkeypatch,
):
    checkout = Path(__file__).resolve().parents[4]
    expected = {
        str(checkout / "backend" / "services" / "code-graph-service" / "src"),
        str(checkout / "backend" / "services" / "docs-sync-service" / "src"),
    }
    monkeypatch.setenv("ASTLOOM_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "path", [item for item in sys.path if item not in expected])

    ensure_service_import_paths()

    assert expected.issubset(set(sys.path))


def test_profile_list_and_show(capsys):
    assert main(["profile", "list"]) == 0
    out = capsys.readouterr().out
    assert "programming-cursor-mcp" in out
    assert main(["profile"]) == 0
    bare = capsys.readouterr().out
    assert "programming-cursor-mcp" in bare
    assert main(["profile", "show", "programming-cursor-mcp"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile_id"] == "programming-cursor-mcp"


def test_project_lifecycle_and_cursor_export(tmp_path, monkeypatch):
    root = Path("/opt/Astloom")
    monkeypatch.setenv("ASTLOOM_ROOT", str(root))
    import astloom_cli.state as state

    monkeypatch.setattr(state, "default_state_root", lambda _root: tmp_path / "projects")

    assert (
        main(
            [
                "project",
                "register",
                "--tenant",
                "t",
                "--workspace",
                "w",
                "--project",
                "p",
                "--name",
                "Demo",
                "--usage-profile",
                "programming-cursor-mcp",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "project",
                "activate",
                "--tenant",
                "t",
                "--workspace",
                "w",
                "--project",
                "p",
                "--usage-profile",
                "programming-cursor-mcp",
            ]
        )
        == 0
    )
    project = json.loads((tmp_path / "projects" / "t" / "w" / "p.json").read_text(encoding="utf-8"))
    assert project["usage_profile"] == "programming-cursor-mcp"

    out_file = tmp_path / "mcp.json"
    assert (
        main(
            [
                "cursor",
                "export",
                "--tenant",
                "t",
                "--workspace",
                "w",
                "--project",
                "p",
                "--out",
                str(out_file),
            ]
        )
        == 0
    )
    fragment = json.loads(out_file.read_text(encoding="utf-8"))
    assert "Astloom-Programming" in fragment["mcpServers"]
    assert fragment["mcpServers"]["Astloom-Programming"]["env"]["ASTLOOM_PROJECT_ID"] == "p"


def test_mcp_tools(capsys):
    assert main(["mcp", "tools", "--usage-profile", "programming-cursor-mcp"]) == 0
    assert "astloom_memory_retrieve" in capsys.readouterr().out


def test_llm_sessions_reads_running_service_snapshot(monkeypatch, capsys):
    expected = {
        "rpm": 4,
        "inflight_cap": 4,
        "starts_in_window": 3,
        "inflight_count": 2,
        "inflight": [{"session_id": "live-1", "status": "in_flight"}],
        "history": [{"session_id": "done-1", "status": "ok"}],
    }
    import astloom_cli.commands.llm_cmd as llm_cmd

    monkeypatch.setattr(
        llm_cmd,
        "_fetch_sessions",
        lambda: ("http://127.0.0.1:32140/api/v1/llm/sessions", expected),
        raising=False,
    )

    assert main(["llm", "sessions"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sessions"] == expected
    assert payload["source"].endswith("/api/v1/llm/sessions")


def test_llm_sessions_prefers_active_sync_process(monkeypatch, capsys):
    expected = {
        "rpm": 4,
        "inflight_cap": 4,
        "starts_in_window": 4,
        "inflight_count": 3,
        "inflight": [{"session_id": "sync-live"}],
        "history": [],
    }
    import astloom_cli.commands.llm_cmd as llm_cmd

    monkeypatch.setattr(
        llm_cmd,
        "read_live_progress",
        lambda: {"pid": 4321, "llm_sessions": expected},
        raising=False,
    )
    monkeypatch.setattr(
        llm_cmd,
        "_fetch_sessions",
        lambda: (_ for _ in ()).throw(AssertionError("daemon must not win")),
    )

    assert main(["llm", "sessions"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sessions"] == expected
    assert payload["source"] == "sync-process:4321"


def test_llm_test_reports_model_and_reply(monkeypatch, capsys):
    import astloom_cli.commands.llm_cmd as llm_cmd
    from llm_gateway import CompletionResult
    from llm_gateway.settings import LlmGatewaySettings

    settings = LlmGatewaySettings(
        enabled=True,
        host="127.0.0.1",
        port=32400,
        api_base="https://example.test/v1",
        api_base_override="https://example.test/v1",
        api_base_is_auto=False,
        api_key="k",
        default_model="openai/gpt-oss-120b",
        timeout_seconds=30.0,
        num_retries=0,
        rpm=30,
        drop_params=True,
        debug=False,
        reasoning_enabled=False,
        reasoning_effort="",
    )

    class FakeGateway:
        def __init__(self, _settings):
            self.settings = _settings

        def complete(self, request):
            assert request.messages[-1].content == "Hi"
            assert request.model == "openai/gpt-oss-120b"
            return CompletionResult(
                content="Hello!",
                model="openai/gpt-oss-120b",
                provider="openai",
                usage={"total_tokens": 3},
            )

    monkeypatch.setattr(llm_cmd, "load_dotenv_files", lambda: [])
    monkeypatch.setattr(
        "llm_gateway.LlmGatewaySettings.from_environment",
        staticmethod(lambda: settings),
    )
    monkeypatch.setattr("llm_gateway.LiteLlmGateway", FakeGateway)

    assert main(["llm", "test"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["configured_model"] == "openai/gpt-oss-120b"
    assert payload["model"] == "openai/gpt-oss-120b"
    assert payload["reply"] == "Hello!"
    assert payload["prompt"] == "Hi"


def test_llm_test_fails_when_disabled(monkeypatch, capsys):
    import astloom_cli.commands.llm_cmd as llm_cmd
    from llm_gateway.settings import LlmGatewaySettings

    settings = LlmGatewaySettings(
        enabled=False,
        host="127.0.0.1",
        port=32400,
        api_base="http://127.0.0.1:32400",
        api_base_override="",
        api_base_is_auto=True,
        api_key="",
        default_model="openai/gpt-oss-120b",
        timeout_seconds=30.0,
        num_retries=0,
        rpm=30,
        drop_params=True,
        debug=False,
        reasoning_enabled=False,
        reasoning_effort="",
    )
    monkeypatch.setattr(llm_cmd, "load_dotenv_files", lambda: [])
    monkeypatch.setattr(
        "llm_gateway.LlmGatewaySettings.from_environment",
        staticmethod(lambda: settings),
    )

    assert main(["llm", "test"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "disabled" in payload["error"].lower()


def test_path_install(tmp_path, monkeypatch):
    root = Path("/opt/Astloom")
    monkeypatch.setenv("ASTLOOM_ROOT", str(root))
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    source = root / ".venv" / "bin" / "astloom"
    if not source.is_file():
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("#!/bin/sh\necho astloom\n", encoding="utf-8")
        source.chmod(0o755)
    assert main(["path", "install"]) == 0
    target = home / ".local" / "bin" / "astloom"
    assert target.is_symlink()
    assert os.path.realpath(target) == os.path.realpath(source)


def test_path_install_shell_rc_even_when_local_bin_already_on_path(tmp_path, monkeypatch):
    """install.sh exports ~/.local/bin temporarily; --shell-rc must still persist PATH."""
    root = Path("/opt/Astloom")
    monkeypatch.setenv("ASTLOOM_ROOT", str(root))
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    local_bin = home / ".local" / "bin"
    monkeypatch.setenv("PATH", f"{local_bin}{os.pathsep}{os.environ.get('PATH', '')}")
    source = root / ".venv" / "bin" / "astloom"
    if not source.is_file():
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("#!/bin/sh\necho astloom\n", encoding="utf-8")
        source.chmod(0o755)
    bashrc = home / ".bashrc"
    bashrc.write_text("# test bashrc\n", encoding="utf-8")
    assert main(["path", "install", "--shell-rc", ".bashrc"]) == 0
    text = bashrc.read_text(encoding="utf-8")
    assert "# Astloom CLI" in text
    assert str(local_bin) in text
    # Idempotent: second run does not duplicate
    assert main(["path", "install", "--shell-rc", ".bashrc"]) == 0
    assert bashrc.read_text(encoding="utf-8").count("# Astloom CLI") == 1


def test_path_install_default_persists_bashrc_when_missing(tmp_path, monkeypatch):
    """Client install: no pre-existing .bashrc must still get durable PATH."""
    root = Path("/opt/Astloom")
    monkeypatch.setenv("ASTLOOM_ROOT", str(root))
    monkeypatch.setenv("SHELL", "/bin/bash")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # Simulate install.sh exporting local bin temporarily — must NOT skip rc write.
    local_bin = home / ".local" / "bin"
    monkeypatch.setenv("PATH", f"{local_bin}{os.pathsep}/usr/bin")
    source = root / ".venv" / "bin" / "astloom"
    if not source.is_file():
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("#!/bin/sh\necho astloom\n", encoding="utf-8")
        source.chmod(0o755)
    assert not (home / ".bashrc").exists()
    assert main(["path", "install"]) == 0
    bashrc = home / ".bashrc"
    assert bashrc.is_file()
    assert "# Astloom CLI" in bashrc.read_text(encoding="utf-8")
    assert (home / ".local" / "bin" / "astloom").is_symlink()
    profile = home / ".profile"
    assert profile.is_file()
    assert "Astloom CLI bashrc" in profile.read_text(encoding="utf-8")


def test_path_install_no_shell_rc_skips_rc(tmp_path, monkeypatch):
    root = Path("/opt/Astloom")
    monkeypatch.setenv("ASTLOOM_ROOT", str(root))
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    source = root / ".venv" / "bin" / "astloom"
    if not source.is_file():
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("#!/bin/sh\necho astloom\n", encoding="utf-8")
        source.chmod(0o755)
    assert main(["path", "install", "--no-shell-rc"]) == 0
    assert (home / ".local" / "bin" / "astloom").is_symlink()
    assert not (home / ".bashrc").exists()


def _write_mini_profile(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "ports": {
                    "ASTLOOM_API_PORT": 32100,
                    "ASTLOOM_ADMIN_PORT": 32101,
                },
                "service_owners": {
                    "api": "ASTLOOM_API_PORT",
                    "admin": "ASTLOOM_ADMIN_PORT",
                },
            }
        ),
        encoding="utf-8",
    )


def test_ports_show_and_check(tmp_path, monkeypatch, capsys):
    profile = tmp_path / "ports.json"
    _write_mini_profile(profile)
    monkeypatch.setenv("ASTLOOM_API_PORT", "32155")

    assert main(["ports", "show", "--profile", str(profile)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["ports"]["ASTLOOM_API_PORT"] == 32155
    assert shown["ports"]["ASTLOOM_ADMIN_PORT"] == 32101

    from port_profile import loader as port_loader

    monkeypatch.setattr(port_loader, "check_port_available", lambda port, host="127.0.0.1": True)
    assert main(["ports", "check", "--profile", str(profile)]) == 0
    ok_payload = json.loads(capsys.readouterr().out)
    assert ok_payload["ok"] is True
    assert ok_payload["ports"]["ASTLOOM_API_PORT"]["port"] == 32155
    assert ok_payload["ports"]["ASTLOOM_API_PORT"]["available"] is True

    monkeypatch.setattr(
        port_loader,
        "check_port_available",
        lambda port, host="127.0.0.1": port != 32155,
    )
    monkeypatch.setattr(port_loader, "find_port_owner", lambda port: {"pid": 9, "name": "other", "source": "test"})
    monkeypatch.setattr(port_loader, "suggest_alternate_port", lambda *a, **k: 32156)
    assert main(["ports", "check", "--profile", str(profile)]) == 1
    bad = json.loads(capsys.readouterr().out)
    assert bad["ok"] is False
    assert bad["ports"]["ASTLOOM_API_PORT"]["available"] is False
    assert bad["ports"]["ASTLOOM_API_PORT"]["suggested_port"] == 32156
    assert bad["ports"]["ASTLOOM_API_PORT"]["owner"]["name"] == "other"
    assert bad["ports"]["ASTLOOM_ADMIN_PORT"]["available"] is True


def test_ports_check_occupied_writes_map_and_suggests(tmp_path, monkeypatch, capsys):
    """Regression: an occupied profile port fails preflight and writes a port-map artifact."""
    import socket

    from port_profile import load_profile, run_preflight, write_port_map

    profile_path = tmp_path / "ports.json"
    _write_mini_profile(profile_path)
    # Bind an ephemeral port, then force the profile to use it.
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    occupied = holder.getsockname()[1]
    monkeypatch.setenv("ASTLOOM_API_PORT", str(occupied))
    monkeypatch.setenv("ASTLOOM_ADMIN_PORT", "32101")

    profile = load_profile(profile_path)
    report = run_preflight(profile, profile_path=profile_path)
    assert report["ok"] is False
    api = report["ports"]["ASTLOOM_API_PORT"]
    assert api["available"] is False
    assert api["port"] == occupied
    assert api.get("suggested_port") is not None
    assert api["suggested_port"] != occupied
    assert "ASTLOOM_API_PORT" in report["conflicts"]

    map_path = tmp_path / "port-map.json"
    write_port_map(map_path, report)
    written = json.loads(map_path.read_text(encoding="utf-8"))
    assert written["ok"] is False
    assert written["ports"]["ASTLOOM_API_PORT"]["port"] == occupied

    map_arg = tmp_path / "cli-port-map.json"
    assert main(["ports", "check", "--profile", str(profile_path), "--write-map", str(map_arg)]) == 1
    cli_out = json.loads(capsys.readouterr().out)
    assert cli_out["ok"] is False
    assert cli_out["port_map"] == str(map_arg)
    assert map_arg.is_file()
    holder.close()


def test_find_port_owner_parses_ss(monkeypatch):
    from port_profile.loader import find_port_owner

    sample = (
        "State Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
        'LISTEN 0 128 127.0.0.1:32100 0.0.0.0:* users:(("python",pid=4242,fd=6))\n'
    )
    monkeypatch.setattr("port_profile.loader.shutil.which", lambda name: "/usr/bin/ss" if name == "ss" else None)
    monkeypatch.setattr("port_profile.loader._run_capture", lambda cmd: sample)
    owner = find_port_owner(32100)
    assert owner == {"pid": 4242, "name": "python", "source": "ss", "raw": sample.strip()[:400]}


def test_preflight_allows_explicit_owned_pid(monkeypatch):
    from port_profile import run_preflight

    profile = {
        "ports": {"ASTLOOM_API_PORT": 32100},
        "service_owners": {"api": "ASTLOOM_API_PORT"},
    }
    monkeypatch.setattr("port_profile.loader.check_port_available", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        "port_profile.loader.find_port_owner",
        lambda _port: {"pid": 4242, "name": "python", "source": "test"},
    )
    monkeypatch.setattr("port_profile.loader.suggest_alternate_port", lambda *_args, **_kwargs: None)

    report = run_preflight(profile, allow_ours=True, allowed_pids={4242})

    assert report["ok"] is True
    assert report["ports"]["ASTLOOM_API_PORT"]["ours"] is True
    assert report["ports"]["ASTLOOM_API_PORT"]["blocking"] is False


def _preflight_python_owner(monkeypatch, *, pid: int = 4242) -> dict:
    """Occupied profile port owned by a bare ``python`` process (ss comm name)."""
    profile = {
        "ports": {"ASTLOOM_ADAPTER_PORT": 32170},
        "service_owners": {"adapter": "ASTLOOM_ADAPTER_PORT"},
    }
    monkeypatch.setattr("port_profile.loader.check_port_available", lambda *_a, **_k: False)
    monkeypatch.setattr(
        "port_profile.loader.find_port_owner",
        lambda _port: {"pid": pid, "name": "python", "source": "test"},
    )
    monkeypatch.setattr("port_profile.loader.suggest_alternate_port", lambda *_a, **_k: None)
    return profile


def test_preflight_adopts_listener_started_from_repo_root(monkeypatch, tmp_path):
    """Regression: our own venv service (ss reports only `python`) must not block start."""
    from port_profile import run_preflight

    profile = _preflight_python_owner(monkeypatch)
    monkeypatch.setattr(
        "port_profile.loader.pid_started_from_root",
        lambda pid, root: pid == 4242 and root == tmp_path,
    )

    report = run_preflight(profile, allow_ours=True, repo_root=tmp_path)

    assert report["ok"] is True
    assert report["ports"]["ASTLOOM_ADAPTER_PORT"]["ours"] is True
    assert report["ports"]["ASTLOOM_ADAPTER_PORT"]["blocking"] is False


def test_preflight_foreign_python_listener_still_blocks(monkeypatch, tmp_path):
    from port_profile import run_preflight

    profile = _preflight_python_owner(monkeypatch)
    monkeypatch.setattr("port_profile.loader.pid_started_from_root", lambda _pid, _root: False)

    report = run_preflight(profile, allow_ours=True, repo_root=tmp_path)

    assert report["ok"] is False
    assert report["ports"]["ASTLOOM_ADAPTER_PORT"]["ours"] is False
    assert report["ports"]["ASTLOOM_ADAPTER_PORT"]["blocking"] is True
    assert "ASTLOOM_ADAPTER_PORT" in report["conflicts"]


def test_pid_started_from_root_reads_proc(tmp_path):
    """Real /proc probe: relative and absolute argv0 under the root are ours; others are not."""
    import subprocess
    import sys

    from port_profile.loader import pid_started_from_root

    # Incident shape: `.venv/bin/python -m adapter_service` with cwd at the checkout.
    relative = subprocess.Popen(
        [".venv/bin/python", "-c", "import time; time.sleep(30)"],
        executable=sys.executable,
        cwd=str(tmp_path),
    )
    absolute = subprocess.Popen(
        [str(tmp_path / ".venv" / "bin" / "python"), "-c", "import time; time.sleep(30)"],
        executable=sys.executable,
    )
    try:
        assert pid_started_from_root(relative.pid, tmp_path) is True
        assert pid_started_from_root(absolute.pid, tmp_path) is True
        assert pid_started_from_root(absolute.pid, tmp_path / "elsewhere") is False
    finally:
        for proc in (relative, absolute):
            proc.kill()
            proc.wait(timeout=10)
    assert pid_started_from_root(2**22 + 1, tmp_path) is False


def test_graph_smoke_ingest_explore(capsys, monkeypatch):
    monkeypatch.setenv("ASTLOOM_ROOT", "/opt/Astloom")
    monkeypatch.setenv("ASTLOOM_GRAPH_CLI_BACKEND", "memory")
    sample = "/opt/Astloom/samples/e2e-graph-probe/src"
    assert (
        main(
            [
                "graph",
                "smoke",
                "--tenant",
                "t",
                "--workspace",
                "w",
                "--project",
                "p",
                "--path",
                sample,
                "--query",
                "login password",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["hybrid_hits"] >= 1
    assert payload["explore_sections"] >= 1


def test_graph_watch_once(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_ROOT", "/opt/Astloom")
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("x=1\n", encoding="utf-8")
    assert (
        main(
            [
                "graph",
                "watch",
                "--tenant",
                "t",
                "--workspace",
                "w",
                "--project",
                "p",
                "--path",
                str(src),
                "--interval",
                "0.05",
                "--debounce",
                "0.01",
                "--max-wait",
                "0.1",
                "--once",
            ]
        )
        == 0
    )


def test_doctor_imports_mcp_gateway(capsys, monkeypatch):
    monkeypatch.setenv("ASTLOOM_ROOT", "/opt/Astloom")
    assert main(["doctor"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["venv_python"] is True
    assert payload["import_mcp_gateway_service"] is True
