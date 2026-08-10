"""Tests for client remote purge scope lock (HTTPS-only; SSH removed)."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path
from types import ModuleType

import pytest

from astloom_cli.connect_config import ConnectSettings
from astloom_cli.connect_flow.remote_purge import (
    assert_cli_scope_matches_connect,
    remote_purge_from_args,
)


def _settings(**kwargs) -> ConnectSettings:
    base = dict(
        graph_url="https://g.internal:8080",
        api_token="tokentokentoken12",
        remote_root="/opt/Astloom",
        tenant="mir",
        workspace="dev",
        project="ThinkingSOC",
    )
    base.update(kwargs)
    return ConnectSettings(**base)


def _fake_httpx_module(*, calls: list[str]) -> ModuleType:
    fake_httpx = ModuleType("httpx")
    fake_httpx.HTTPError = Exception

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"ok": True, "purge": {"deleted": 3}}

    def post(url, headers=None, json=None, timeout=None, verify=True):
        calls.append(url)
        assert headers["Authorization"] == "Bearer tokentokentoken12"
        assert json == {"yes": True}
        assert verify is False
        return _Resp()

    fake_httpx.post = post
    return fake_httpx


def test_scope_mismatch_hard_fails():
    settings = _settings()
    with pytest.raises(SystemExit, match="does not match connect.yaml"):
        assert_cli_scope_matches_connect(
            Namespace(tenant="other", workspace="", project=""),
            settings,
        )


def test_remote_purge_locks_scope_and_purges_over_https(monkeypatch):
    settings = _settings()
    calls: list[str] = []
    monkeypatch.setitem(sys.modules, "httpx", _fake_httpx_module(calls=calls))
    args = Namespace(yes=True, tenant="mir", workspace="dev", project="ThinkingSOC")
    assert remote_purge_from_args(settings, args) == 0
    assert calls == ["https://g.internal:8080/api/v1/projects/ThinkingSOC/graph/purge"]


def test_remote_purge_rejects_mismatch_before_http(monkeypatch):
    settings = _settings()
    calls: list[str] = []

    def boom(*_a, **_k):
        calls.append("called")
        return None

    monkeypatch.setitem(sys.modules, "httpx", _fake_httpx_module(calls=calls))
    with pytest.raises(SystemExit, match="does not match"):
        remote_purge_from_args(
            settings,
            Namespace(yes=True, tenant="evil", workspace="dev", project="ThinkingSOC"),
        )
    assert calls == []


def test_remote_purge_prefers_https_when_graph_url_ready(monkeypatch):
    settings = _settings(graph_url="https://g.internal:8080", api_token="tokentokentoken12")
    calls: list[str] = []
    monkeypatch.setitem(sys.modules, "httpx", _fake_httpx_module(calls=calls))

    args = Namespace(yes=True, tenant="mir", workspace="dev", project="ThinkingSOC")
    assert remote_purge_from_args(settings, args) == 0
    assert calls == ["https://g.internal:8080/api/v1/projects/ThinkingSOC/graph/purge"]


def test_remote_purge_without_graph_url_exits(monkeypatch):
    settings = _settings(graph_url="", api_token="")
    with pytest.raises(SystemExit, match="graph_url"):
        remote_purge_from_args(settings, Namespace(yes=True, tenant="mir", workspace="dev", project="ThinkingSOC"))


def test_cmd_purge_client_role_routes_remote(monkeypatch, tmp_path: Path):
    from astloom_cli.commands.sync.cmd import cmd_purge
    from astloom_cli.connect_config import ConnectSettings

    cfg = tmp_path / "connect.yaml"
    cfg.write_text(
        "server:\n  graph_url: https://g.internal:8080\n  remote_root: /opt/Astloom\n",
        encoding="utf-8",
    )
    seen = {"n": 0}

    monkeypatch.setattr(
        "astloom_cli.service_runtime.paths.install_role",
        lambda _r: "client",
    )
    monkeypatch.setattr(
        "astloom_cli.commands.sync.cmd.repo_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "astloom_cli.connect_config.try_resolve_config_path",
        lambda explicit="", project_root=None: cfg,
    )
    monkeypatch.setattr(
        "astloom_cli.connect_config.load_connect_settings",
        lambda **_k: ConnectSettings(
            graph_url="https://g.internal:8080",
            api_token="tokentokentoken12",
            remote_root="/opt/Astloom",
            tenant="mir",
            workspace="dev",
            project="App",
        ),
    )

    def fake_remote(settings, args):
        seen["n"] += 1
        return 0

    monkeypatch.setattr(
        "astloom_cli.connect_flow.remote_purge.remote_purge_from_args",
        fake_remote,
    )
    assert cmd_purge(Namespace(yes=True, tenant="", workspace="", project="")) == 0
    assert seen["n"] == 1
