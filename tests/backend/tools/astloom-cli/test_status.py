"""Tests for astloom status."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path
from types import ModuleType

from astloom_cli.commands.status import _overall, build_status_report, cmd_status
from astloom_cli.connect_config import ConnectSettings
from astloom_cli.parser import build_parser


def test_parser_status():
    parser = build_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"
    assert args.json is False


def test_overall_empty_vs_ready():
    assert (
        _overall(
            {
                "graph": {"ok": True, "symbol_count": 0, "pending_count": 0},
                "postgres": {},
                "neo4j": {},
            }
        )
        == "empty"
    )
    assert (
        _overall(
            {
                "graph": {"ok": True, "symbol_count": 3, "pending_count": 0},
                "postgres": {"configured": True, "reachable": True},
                "neo4j": {"configured": True, "reachable": True},
            }
        )
        == "ready"
    )
    assert (
        _overall(
            {
                "graph": {"ok": True, "symbol_count": 3, "pending_count": 2},
                "postgres": {},
                "neo4j": {},
            }
        )
        == "pending_sync"
    )
    assert (
        _overall(
            {
                "graph": {"ok": True, "symbol_count": 3, "pending_count": 0},
                "postgres": {"configured": True, "reachable": False},
                "neo4j": {"configured": True, "reachable": True},
            }
        )
        == "Postgres unreachable"
    )


def test_cmd_status_proxies_to_server_over_https_on_client_install(monkeypatch, tmp_path: Path):
    """server.url set → status proxies over HTTPS on a client install (no local stack)."""
    cfg = tmp_path / "connect.yaml"
    cfg.write_text(
        "server:\n  url: https://astloom.example:9443\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "astloom_cli.service_runtime.paths.local_compose_stack_present",
        lambda _root: False,
    )
    monkeypatch.setattr(
        "astloom_cli.connect_config.try_resolve_config_path",
        lambda explicit="", project_root=None: cfg,
    )
    monkeypatch.setattr(
        "astloom_cli.connect_config.load_connect_settings",
        lambda **_k: ConnectSettings(
            api_url="https://astloom.example:9443",
            api_token="tokentokentoken12",
            project="demo",
        ),
    )

    fake_httpx = ModuleType("httpx")
    fake_httpx.HTTPError = Exception
    calls: list[str] = []

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "scope": {"tenant_id": "t", "workspace_id": "w", "project_id": "demo"},
                "usage_profile": "programming-cursor-mcp",
                "code_source": {"server_path": "/srv/repos/demo"},
                "ingest": {"status": "registered"},
            }

    verify_args: list[object] = []

    def get(url, headers=None, timeout=None, verify=True):
        calls.append(url)
        verify_args.append(verify)
        return _Resp()

    fake_httpx.get = get
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    assert cmd_status(Namespace(tenant="", workspace="", project="", json=True, verbose=False)) == 0
    assert calls == ["https://astloom.example:9443/api/v1/projects/demo/connect/status"]
    # Default tls_verify=false → encrypt without validating auto-TLS lab certs.
    assert verify_args == [False]


def test_build_status_report_smoke(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ASTLOOM_TENANT_ID", raising=False)
    monkeypatch.delenv("ASTLOOM_WORKSPACE_ID", raising=False)
    monkeypatch.delenv("ASTLOOM_PROJECT_ID", raising=False)
    monkeypatch.setattr("astloom_cli.commands.status.load_dotenv_files", lambda **_: [])
    monkeypatch.setattr("astloom_cli.cli_defaults.load_dotenv_files", lambda **_: [])
    monkeypatch.setattr("astloom_cli.cli_defaults.peek_identity_scope", lambda: {})
    monkeypatch.setattr("astloom_cli.cli_defaults.peek_connect_scope", lambda: {})
    monkeypatch.setattr(
        "astloom_cli.commands.status._graph_snapshot",
        lambda *_a, **_k: {
            "ok": True,
            "backend": "memory",
            "symbol_count": 0,
            "edge_count": 0,
            "pending_count": 0,
            "pending_files": [],
            "last_sync_at": None,
        },
    )
    monkeypatch.setattr(
        "astloom_cli.commands.status._postgres_probe",
        lambda: {"configured": False, "reachable": None},
    )
    monkeypatch.setattr(
        "astloom_cli.commands.status._neo4j_probe",
        lambda: {"configured": False, "reachable": None},
    )
    report = build_status_report(cwd=tmp_path)
    assert report["status"] == "empty"
    assert "astloom sync" in " ".join(report["hints"])
    assert report["scope"]["tenant"] == "astloom"
