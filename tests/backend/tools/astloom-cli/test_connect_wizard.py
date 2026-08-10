"""Unit tests for the interactive HTTPS connect wizard and yaml merge (SSH removed)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from astloom_cli.connect_config import ConnectSettings, load_connect_settings, write_or_merge_connect_yaml
from astloom_cli.parser import build_parser


def test_connect_parser_word_modes():
    parser = build_parser()
    assert parser.parse_args(["connect"]).connect_mode == ""
    assert parser.parse_args(["connect", "edit"]).connect_mode == "edit"
    assert parser.parse_args(["connect", "init"]).connect_mode == "init"
    assert parser.parse_args(["connect", "/a,/b"]).connect_mode == "/a,/b"


def test_parse_connect_project_dirs(tmp_path: Path):
    from astloom_cli.commands.connect import parse_connect_project_dirs

    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert parse_connect_project_dirs("", cwd=tmp_path) == [tmp_path.resolve()]
    assert parse_connect_project_dirs(f"{a},{b}", cwd=tmp_path) == [a.resolve(), b.resolve()]
    with pytest.raises(SystemExit, match="not a directory"):
        parse_connect_project_dirs(str(tmp_path / "missing"), cwd=tmp_path)


def test_cmd_connect_multi_path_reuses_shared_settings(tmp_path: Path, monkeypatch):
    from argparse import Namespace
    from dataclasses import replace

    from astloom_cli.commands.connect import cmd_connect
    from astloom_cli.connect_config import ConnectSettings

    a = tmp_path / "AppA"
    b = tmp_path / "AppB"
    a.mkdir()
    b.mkdir()
    saw_shared: list[bool] = []

    def fake_one(args, *, work, shared, force_edit):
        saw_shared.append(shared is not None)
        settings = shared or ConnectSettings(
            api_url="https://astloom.example",
            tenant="t",
            workspace="w",
            project=work.name,
            source_server_path=str(work),
            prefer_http=True,
            local=False,
        )
        return 0, replace(settings, project=work.name, source_server_path=str(work))

    monkeypatch.setattr("astloom_cli.commands.connect._connect_one", fake_one)
    monkeypatch.setattr("astloom_cli.commands.connect._pin_software_paths", lambda *a, **k: None)
    monkeypatch.chdir(tmp_path)
    args = Namespace(
        connect_mode=f"{a},{b}",
        config="",
        local=False,
        dry_run=True,
        project="",
        server="",
        clients="all",
        include_user_clients=False,
        tenant="",
        workspace="",
        remote_root="",
    )
    assert cmd_connect(args) == 0
    assert saw_shared == [False, True]


def test_write_or_merge_preserves_hand_tuned_fields(tmp_path: Path):
    path = tmp_path / "connect.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "server": {"url": "https://old.example", "remote_root": "/opt/Astloom"},
                "scope": {"tenant": "acme", "workspace": "eng"},
                "clients": "cursor",
                "source": {"server_path": "/srv/repos/App"},
                "connect": {"ingest": "always", "prefer_http": True},
            }
        ),
        encoding="utf-8",
    )
    settings = ConnectSettings(
        api_url="https://new.example",
        remote_root="/opt/Astloom",
        tenant="acme",
        workspace="eng",
        project="App",
        prefer_http=True,
        clients="cursor",
        ingest_mode="always",
    )
    write_or_merge_connect_yaml(settings, path=path, prefer_http=True)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["server"]["url"] == "https://new.example"
    assert doc["source"]["server_path"] == "/srv/repos/App"
    assert doc["clients"] == "cursor"
    assert doc["connect"]["prefer_http"] is True
    assert "password" not in doc.get("auth", {})


def test_write_or_merge_strips_legacy_ssh_keys(tmp_path: Path):
    """Old connect.yaml with server.ssh / auth.ssh_key must not survive a merge."""
    path = tmp_path / "connect.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "server": {"ssh": "old@host", "remote_root": "/opt/Astloom"},
                "auth": {"ssh_key": "/tmp/id_ed25519_astloom"},
                "scope": {"tenant": "acme", "workspace": "eng"},
            }
        ),
        encoding="utf-8",
    )
    settings = ConnectSettings(api_url="https://astloom.example", tenant="acme", workspace="eng", project="App")
    write_or_merge_connect_yaml(settings, path=path, prefer_http=True)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "ssh" not in doc.get("server", {})
    assert "ssh_key" not in doc.get("auth", {})
    assert doc["server"]["url"] == "https://astloom.example"


def test_write_or_merge_never_keeps_password(tmp_path: Path):
    path = tmp_path / "connect.yaml"
    path.write_text(
        yaml.safe_dump({"server": {"url": "https://u.example"}, "auth": {"password": "nope"}}),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="do not store"):
        write_or_merge_connect_yaml(
            ConnectSettings(api_url="https://u.example"),
            path=path,
            prefer_http=True,
        )


def test_run_https_connect_wizard_writes_yaml(tmp_path: Path, monkeypatch):
    from astloom_cli.connect_wizard import run_https_connect_wizard

    monkeypatch.setattr("astloom_cli.connect_wizard._require_tty", lambda: None)
    answers = iter(["https://astloom.example:9443", "acme", "eng"])

    def fake_input(prompt: str) -> str:
        return next(answers)

    def fake_password(prompt: str) -> str:
        if "API key" in prompt:
            return "as1.test.token.value"
        return ""

    app = tmp_path / "MyApp"
    app.mkdir()
    cfg_path = tmp_path / ".astloom" / "connect.yaml"
    settings = run_https_connect_wizard(
        existing=ConnectSettings(project="MyApp", usage_profile="programming-cursor-mcp"),
        config_path=cfg_path,
        project_dir=app,
        input_fn=fake_input,
        password_fn=fake_password,
    )
    assert settings.api_url == "https://astloom.example:9443"
    assert settings.tenant == "acme"
    assert settings.workspace == "eng"
    assert settings.prefer_http is True
    assert settings.api_token == "as1.test.token.value"

    doc = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert "ssh" not in doc.get("server", {})
    assert "ssh_key" not in doc.get("auth", {})
    assert doc["server"]["url"] == "https://astloom.example:9443"
    assert not (tmp_path / ".astloom" / "ssh").exists()


def test_run_https_connect_wizard_rejects_non_https(tmp_path: Path, monkeypatch):
    from astloom_cli.connect_wizard import run_https_connect_wizard

    monkeypatch.setattr("astloom_cli.connect_wizard._require_tty", lambda: None)
    answers = iter(["http://astloom.example:9443"])
    app = tmp_path / "MyApp"
    app.mkdir()
    with pytest.raises(SystemExit, match="https://"):
        run_https_connect_wizard(
            existing=ConnectSettings(project="MyApp"),
            config_path=tmp_path / ".astloom" / "connect.yaml",
            project_dir=app,
            input_fn=lambda _p: next(answers),
            password_fn=lambda _p: "",
        )


def test_connect_one_runs_https_wizard_when_server_given(tmp_path: Path, monkeypatch):
    """`--server https://…` on a fresh connect wires through the HTTPS wizard."""
    from argparse import Namespace
    from dataclasses import replace

    from astloom_cli.commands import connect as connect_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    app = tmp_path / "App"
    app.mkdir()
    calls: list[str] = []

    def fake_https_wizard(*, existing, config_path, project_dir, url_override):
        calls.append(url_override)
        return replace(existing, api_url=url_override, prefer_http=True, project="App")

    monkeypatch.setattr(connect_mod, "run_https_connect_wizard", fake_https_wizard)
    monkeypatch.setattr(
        connect_mod,
        "_persist_and_run_connect",
        lambda settings, **_k: (0, settings),
    )
    args = Namespace(
        project="",
        dry_run=True,
        local=False,
        config="",
        clients="all",
        include_user_clients=False,
        tenant="",
        workspace="",
        server="https://astloom.example:9443",
        usage_profile="programming-cursor-mcp",
    )
    code, settings = connect_mod._connect_one(args, work=app, shared=None, force_edit=False)
    assert code == 0
    assert calls == ["https://astloom.example:9443"]
    assert settings.api_url == "https://astloom.example:9443"


def test_prompt_usage_profile_accepts_number(monkeypatch):
    from astloom_cli.connect_wizard import prompt_usage_profile

    monkeypatch.setattr(
        "usage_profile.list_profile_ids",
        lambda: ["alpha", "programming-cursor-mcp"],
    )
    monkeypatch.setattr(
        "usage_profile.load_usage_profile",
        lambda pid: {"title": pid},
    )
    assert prompt_usage_profile(input_fn=lambda _p: "2") == "programming-cursor-mcp"
    assert prompt_usage_profile(default="alpha", input_fn=lambda _p: "") == "alpha"


def test_prompt_usage_profile_auto_selects_sole_entry(monkeypatch):
    from astloom_cli.connect_wizard import prompt_usage_profile

    monkeypatch.setattr(
        "usage_profile.list_profile_ids",
        lambda: ["programming-cursor-mcp"],
    )
    assert prompt_usage_profile(input_fn=lambda _p: (_ for _ in ()).throw(AssertionError("no prompt"))) == (
        "programming-cursor-mcp"
    )


def test_prompt_api_key_requires_when_missing():
    from astloom_cli.connect_wizard import prompt_api_key

    with pytest.raises(SystemExit, match="API key is required"):
        prompt_api_key(existing="", password_fn=lambda _p: "")


def test_prompt_api_key_keeps_existing_on_blank():
    from astloom_cli.connect_wizard import prompt_api_key

    got = prompt_api_key(
        existing="as1.existing.token.value",
        password_fn=lambda _p: "",
    )
    assert got == "as1.existing.token.value"


def test_prompt_api_key_accepts_replacement():
    from astloom_cli.connect_wizard import prompt_api_key

    got = prompt_api_key(
        existing="as1.old.token.value",
        password_fn=lambda _p: "as1.new.token.value",
    )
    assert got == "as1.new.token.value"


def test_prompt_api_key_reads_access_token_file(tmp_path: Path):
    from astloom_cli.connect_http import persist_access_token
    from astloom_cli.connect_wizard import prompt_api_key

    cfg = tmp_path / ".astloom" / "connect.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("server: {}\n", encoding="utf-8")
    persist_access_token(cfg, "as1.from.file.token")
    got = prompt_api_key(
        existing="",
        config_path=cfg,
        password_fn=lambda _p: "",
    )
    assert got == "as1.from.file.token"


def test_run_https_connect_wizard_persists_api_key(tmp_path: Path, monkeypatch):
    from astloom_cli.connect_http import read_access_token_file
    from astloom_cli.connect_wizard import run_https_connect_wizard

    monkeypatch.setattr("astloom_cli.connect_wizard._require_tty", lambda: None)
    answers = iter(["https://astloom.example:9443", "acme", "eng"])

    def fake_password(prompt: str) -> str:
        if "API key" in prompt:
            return "as1.wizard.minted.token"
        return "bootstrap-secret"

    app = tmp_path / "MyApp"
    app.mkdir()
    cfg_path = tmp_path / ".astloom" / "connect.yaml"
    settings = run_https_connect_wizard(
        existing=ConnectSettings(project="MyApp", usage_profile="programming-cursor-mcp"),
        config_path=cfg_path,
        project_dir=app,
        input_fn=lambda _p: next(answers),
        password_fn=fake_password,
    )
    assert settings.api_token == "as1.wizard.minted.token"
    assert read_access_token_file(cfg_path) == "as1.wizard.minted.token"


def test_run_connect_keeps_user_api_token_when_bootstrap_mints(monkeypatch):
    """Bootstrap may return a minted token; env-supplied API key must win."""
    from astloom_cli.connect_flow import run as run_mod

    monkeypatch.setenv("ASTLOOM_TOKEN", "as1.user.supplied")
    settings = ConnectSettings(
        api_url="https://api.example",
        api_token="as1.user.supplied",
        tenant="t",
        workspace="w",
        project="p",
        usage_profile="programming-cursor-mcp",
        prefer_http=True,
        mcp_http_url="https://mcp.example:32500",
        register=True,
        config_path=None,
    )

    monkeypatch.setattr(run_mod, "validate_connect_settings", lambda _s: [])
    monkeypatch.setattr(run_mod, "reachability_check", lambda _s: None)
    monkeypatch.setattr(
        run_mod,
        "api_bootstrap",
        lambda _s: {
            "access_token": "as1.bootstrap.minted",
            "mcp": {
                "url": "https://mcp.example:32500/mcp",
                "headers": {"Authorization": "Bearer as1.bootstrap.minted"},
            },
        },
    )
    monkeypatch.setattr(run_mod, "mcp_http_smoke", lambda *a, **k: True)
    monkeypatch.setattr(run_mod, "write_clients", lambda *a, **k: [])
    monkeypatch.setattr(run_mod, "print_connect_summary", lambda *a, **k: None)
    monkeypatch.setattr(run_mod, "should_ingest", lambda _s: False)
    monkeypatch.setattr(run_mod, "guidance_connect_notes", lambda *_a, **_k: [])
    monkeypatch.setattr(run_mod, "materialize_mcp_first_guidance", lambda *_a, **_k: {})

    persisted: list[str] = []

    def fake_persist(_path, token: str):
        persisted.append(token)
        return None

    monkeypatch.setattr(
        "astloom_cli.connect_http.persist_access_token",
        fake_persist,
    )

    code = run_mod.run_connect(settings, dry_run=True)
    assert code == 0
    assert settings.api_token == "as1.user.supplied"
    assert persisted == []


def test_run_connect_replaces_stale_access_token_file_with_bootstrap_mint(monkeypatch):
    """Stale ``.astloom/access_token`` must not block saving a bootstrap mint."""
    from astloom_cli.connect_flow import run as run_mod

    monkeypatch.delenv("ASTLOOM_TOKEN", raising=False)
    monkeypatch.delenv("ASTLOOM_CONNECT_TOKEN", raising=False)
    settings = ConnectSettings(
        api_url="https://api.example",
        api_token="as1.stale.file.token",
        tenant="t",
        workspace="w",
        project="p",
        usage_profile="programming-cursor-mcp",
        prefer_http=True,
        mcp_http_url="https://mcp.example:32500",
        register=True,
        config_path=None,
    )

    monkeypatch.setattr(run_mod, "validate_connect_settings", lambda _s: [])
    monkeypatch.setattr(run_mod, "reachability_check", lambda _s: None)
    monkeypatch.setattr(
        run_mod,
        "api_bootstrap",
        lambda _s: {
            "access_token": "as1.bootstrap.minted",
            "mcp": {
                "url": "https://mcp.example:32500/mcp",
                "headers": {"Authorization": "Bearer as1.bootstrap.minted"},
            },
        },
    )
    monkeypatch.setattr(run_mod, "mcp_http_smoke", lambda *a, **k: True)
    monkeypatch.setattr(run_mod, "write_clients", lambda *a, **k: [])
    monkeypatch.setattr(run_mod, "print_connect_summary", lambda *a, **k: None)
    monkeypatch.setattr(run_mod, "should_ingest", lambda _s: False)
    monkeypatch.setattr(run_mod, "guidance_connect_notes", lambda *_a, **_k: [])
    monkeypatch.setattr(run_mod, "materialize_mcp_first_guidance", lambda *_a, **_k: {})

    persisted: list[str] = []

    def fake_persist(_path, token: str):
        persisted.append(token)
        return None

    monkeypatch.setattr(
        "astloom_cli.connect_http.persist_access_token",
        fake_persist,
    )

    code = run_mod.run_connect(settings, dry_run=True)
    assert code == 0
    assert settings.api_token == "as1.bootstrap.minted"
    assert persisted == ["as1.bootstrap.minted"]

