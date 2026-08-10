"""Tests for client HTTPS scheme enforcement, and 401 fail-closed (no refresh)."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest

from astloom_cli.connect_config import ConnectSettings, http_error_message, load_connect_settings


def _write_cfg(tmp_path: Path, body: str) -> Path:
    cfg_dir = tmp_path / ".astloom"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg = cfg_dir / "connect.yaml"
    cfg.write_text(body, encoding="utf-8")
    return cfg


# --- HTTPS scheme enforcement -----------------------------------------------


@pytest.mark.parametrize("field", ["url", "mcp_http_url", "graph_url"])
def test_http_scheme_rejected_without_override(tmp_path, monkeypatch, field):
    monkeypatch.delenv("ASTLOOM_ALLOW_INSECURE_HTTP", raising=False)
    cfg = _write_cfg(
        tmp_path,
        f"server:\n  {field}: http://astloom.example.internal:9\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
    )
    with pytest.raises(SystemExit, match="insecure"):
        load_connect_settings(config_path=str(cfg), allow_incomplete=True)


def test_https_scheme_allowed(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_ALLOW_INSECURE_HTTP", raising=False)
    cfg = _write_cfg(
        tmp_path,
        "server:\n  url: https://astloom.example.internal:9\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
    )
    settings = load_connect_settings(config_path=str(cfg), allow_incomplete=True)
    assert settings.api_url == "https://astloom.example.internal:9"


def test_http_scheme_allowed_with_explicit_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_ALLOW_INSECURE_HTTP", "1")
    cfg = _write_cfg(
        tmp_path,
        "server:\n  graph_url: http://astloom.example.internal:9\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
    )
    settings = load_connect_settings(config_path=str(cfg), allow_incomplete=True)
    assert settings.graph_url == "http://astloom.example.internal:9"


# --- 401 fails closed with a re-bootstrap hint (no auto-refresh) ------------


def test_http_error_message_on_401_points_at_rebootstrap():
    class _Resp:
        status_code = 401
        text = "unauthorized"

    message = http_error_message("ingest", _Resp())
    assert "401" in message
    assert "astloom connect" in message


def test_http_error_message_on_other_error_includes_body():
    class _Resp:
        status_code = 500
        text = "boom"

    message = http_error_message("ingest", _Resp())
    assert "500" in message
    assert "boom" in message


def test_api_ingest_401_fails_closed_without_retry(monkeypatch):
    from astloom_cli.connect_flow import api as api_mod

    calls: list[str] = []

    class _UnauthorizedResp:
        status_code = 401
        text = "unauthorized"

    def post(url, headers=None, json=None, timeout=None, verify=None):
        calls.append(url)
        return _UnauthorizedResp()

    fake = ModuleType("httpx")
    fake.HTTPError = Exception
    fake.post = post
    monkeypatch.setattr(api_mod, "httpx", fake)

    settings = ConnectSettings(api_url="https://api:9", api_token="stale-access", tenant="t", workspace="w", project="p")
    with pytest.raises(SystemExit, match="astloom connect"):
        api_mod.api_ingest(settings)
    assert len(calls) == 1  # no retry attempted
