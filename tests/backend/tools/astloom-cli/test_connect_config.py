"""Tests for connect config loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from astloom_cli.connect_config import load_connect_settings, write_connect_template


def test_load_connect_settings_graph_url(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "connect.yaml"
    cfg.write_text(
        "server:\n  graph_url: https://g.internal:8080/\n"
        "auth:\n  token: tokentokentoken12\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ASTLOOM_CONNECT_GRAPH_URL", raising=False)
    monkeypatch.delenv("ASTLOOM_CONNECT_TOKEN", raising=False)
    settings = load_connect_settings(config_path=str(cfg), allow_incomplete=True)
    assert settings.graph_url == "https://g.internal:8080"
    assert settings.api_token == "tokentokentoken12"

    monkeypatch.setenv("ASTLOOM_CONNECT_GRAPH_URL", "https://env.internal:9")
    monkeypatch.setenv("ASTLOOM_CONNECT_TOKEN", "envtokenenvtoken12")
    settings2 = load_connect_settings(config_path=str(cfg), allow_incomplete=True)
    assert settings2.graph_url == "https://env.internal:9"
    assert settings2.api_token == "envtokenenvtoken12"


def test_project_defaults_to_cwd_name(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "connect.json"
    cfg.write_text(
        json.dumps({"server": {"local": True}, "scope": {"tenant": "t", "workspace": "w"}}),
        encoding="utf-8",
    )
    app = tmp_path / "myapp"
    app.mkdir()
    monkeypatch.chdir(app)
    settings = load_connect_settings(config_path=str(cfg))
    assert settings.project == "myapp"


def test_write_connect_template(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = write_connect_template()
    assert path == tmp_path / ".astloom" / "connect.yaml"
    assert path.is_file()
    assert "server:" in path.read_text(encoding="utf-8")


def test_default_config_paths_prefer_project_cwd(tmp_path: Path, monkeypatch):
    from astloom_cli.connect_config import default_config_paths, default_connect_yaml_path

    project = tmp_path / "MyApp"
    project.mkdir()
    install = tmp_path / "Astloom"
    install.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: install)
    monkeypatch.setattr(Path, "home", lambda: home)
    paths = default_config_paths()
    assert paths[0] == default_connect_yaml_path()
    assert paths[0] == project / ".astloom" / "connect.yaml"
    assert any(p == install / ".astloom" / "connect.yaml" for p in paths)
    assert any(p == home / ".astloom" / "connect.yaml" for p in paths)


def test_write_or_merge_connect_yaml_creates_file(tmp_path: Path):
    from astloom_cli.connect_config import ConnectSettings, write_or_merge_connect_yaml

    path = tmp_path / "connect.yaml"
    settings = ConnectSettings(
        api_url="https://astloom.example",
        remote_root="/opt/Astloom",
        tenant="t",
        workspace="w",
        project="p",
        prefer_http=True,
    )
    write_or_merge_connect_yaml(settings, path=path, prefer_http=True)
    text = path.read_text(encoding="utf-8")
    assert "https://astloom.example" in text
    assert "prefer_http: true" in text


def test_write_or_merge_persists_https_fields_without_ssh(tmp_path: Path):
    from astloom_cli.connect_config import ConnectSettings, write_or_merge_connect_yaml

    path = tmp_path / "connect.yaml"
    settings = ConnectSettings(
        api_url="https://astloom.example:9443",
        mcp_http_url="https://astloom.example:9443/mcp",
        graph_url="https://astloom.example:9443",
        tenant="acme",
        workspace="eng",
        project="App",
        prefer_http=True,
    )
    write_or_merge_connect_yaml(settings, path=path, prefer_http=True)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["server"]["url"] == "https://astloom.example:9443"
    assert doc["server"]["mcp_http_url"] == "https://astloom.example:9443/mcp"
    assert doc["server"]["graph_url"] == "https://astloom.example:9443"
    assert "ssh" not in doc["server"]
    assert "ssh_key" not in doc.get("auth", {})


def test_write_connect_template_refuses_overwrite(tmp_path: Path, monkeypatch):
    target = tmp_path / ".astloom" / "connect.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("existing", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        write_connect_template()


def test_connect_schema_rejects_ssh_only(tmp_path: Path):
    """SSH has been removed: server.ssh with no HTTPS/local alternative fails closed."""
    cfg = tmp_path / "connect.yaml"
    cfg.write_text(
        "server:\n  ssh: ops@host\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="SSH has been removed"):
        load_connect_settings(config_path=str(cfg), allow_incomplete=True)


def test_connect_schema_ignores_ssh_when_https_present(tmp_path: Path, capsys):
    """Leftover server.ssh alongside a working HTTPS URL is ignored (with a warning), not fatal."""
    cfg = tmp_path / "connect.yaml"
    cfg.write_text(
        "server:\n  ssh: ops@host\n  url: https://astloom.example\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
        encoding="utf-8",
    )
    settings = load_connect_settings(config_path=str(cfg), allow_incomplete=True)
    assert settings.api_url == "https://astloom.example"
    assert "SSH has been removed" in capsys.readouterr().err


def test_connect_schema_https_only_config_works(tmp_path: Path):
    cfg = tmp_path / "connect.yaml"
    cfg.write_text(
        "server:\n  url: https://astloom.example\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
        encoding="utf-8",
    )
    settings = load_connect_settings(config_path=str(cfg))
    assert settings.api_url == "https://astloom.example"


def test_product_packages_never_call_deleted_ssh_symbols():
    """Regression gate: SSH has been removed; these symbols must not exist anywhere."""
    import re

    packages_root = Path(__file__).resolve().parents[4] / "backend" / "packages"
    assert packages_root.is_dir()
    forbidden = re.compile(
        r"ssh_bootstrap|materialize_ssh_mcp_fragment|remote_register_project|"
        r"run_ssh_connect_wizard|ensure_ssh_ready|connect_flow\.ssh\b|remote_mcp_serve"
    )
    hits: list[str] = []
    for path in packages_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            hits.append(str(path))
    assert hits == []


