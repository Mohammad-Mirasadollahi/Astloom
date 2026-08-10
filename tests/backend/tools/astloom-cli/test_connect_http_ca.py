"""Tests for connect HTTP CA trust + bootstrap secret env + token/CA persist."""

from __future__ import annotations

from pathlib import Path

import pytest

from astloom_cli.connect_config import ConnectSettings, load_connect_settings
from astloom_cli.connect_http import (
    httpx_verify,
    persist_access_token,
    persist_ca_pem,
    read_access_token_file,
)


def _write_cfg(tmp_path: Path, body: str) -> Path:
    cfg_dir = tmp_path / ".astloom"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg = cfg_dir / "connect.yaml"
    cfg.write_text(body, encoding="utf-8")
    return cfg


def test_bootstrap_secret_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", "op-secret-from-env")
    cfg = _write_cfg(
        tmp_path,
        "server:\n  url: https://astloom.example.internal:9\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
    )
    settings = load_connect_settings(config_path=str(cfg), allow_incomplete=True)
    assert settings.bootstrap_secret == "op-secret-from-env"


def test_httpx_verify_default_off_skips_validation(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_CA_FILE", raising=False)
    settings = ConnectSettings(tls_verify=False, ca_file="")
    assert httpx_verify(settings) is False


def test_httpx_verify_true_uses_ca_file(tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n")
    settings = ConnectSettings(tls_verify=True, ca_file=str(ca))
    assert httpx_verify(settings) == str(ca)


def test_httpx_verify_true_without_ca_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_CA_FILE", raising=False)
    settings = ConnectSettings(tls_verify=True, ca_file=str(tmp_path / "missing.pem"))
    with pytest.raises(SystemExit, match="tls_verify is true but no CA trust"):
        httpx_verify(settings)


def test_load_defaults_tls_verify_false(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_TLS_VERIFY", raising=False)
    cfg = _write_cfg(
        tmp_path,
        "server:\n  url: https://astloom.example.internal:9\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
    )
    settings = load_connect_settings(config_path=str(cfg), allow_incomplete=True)
    assert settings.tls_verify is False
    assert httpx_verify(settings) is False


def test_load_tls_verify_true_from_yaml(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_TLS_VERIFY", raising=False)
    ca = tmp_path / ".astloom" / "certs" / "ca.pem"
    ca.parent.mkdir(parents=True)
    ca.write_text("-----BEGIN CERTIFICATE-----\nABC\n-----END CERTIFICATE-----\n")
    cfg = _write_cfg(
        tmp_path,
        "server:\n  url: https://astloom.example.internal:9\n"
        "auth:\n  tls_verify: true\n  ca_file: .astloom/certs/ca.pem\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
    )
    # Relative ca_file may not resolve — use absolute for this unit test.
    cfg.write_text(
        "server:\n  url: https://astloom.example.internal:9\n"
        f"auth:\n  tls_verify: true\n  ca_file: {ca}\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
        encoding="utf-8",
    )
    settings = load_connect_settings(config_path=str(cfg), allow_incomplete=True)
    assert settings.tls_verify is True
    assert httpx_verify(settings) == str(ca)


def test_persist_and_reload_access_token(tmp_path):
    cfg = _write_cfg(
        tmp_path,
        "server:\n  url: https://astloom.example.internal:9\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
    )
    path = persist_access_token(cfg, "as1.example.token")
    assert path is not None
    assert path.stat().st_mode & 0o777 == 0o600
    assert read_access_token_file(cfg) == "as1.example.token"
    settings = load_connect_settings(config_path=str(cfg), allow_incomplete=True)
    assert settings.api_token == "as1.example.token"


def test_persist_ca_pem_auto_loaded(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_CA_FILE", raising=False)
    cfg = _write_cfg(
        tmp_path,
        "server:\n  url: https://astloom.example.internal:9\n"
        "scope:\n  tenant: t\n  workspace: w\n  project: p\n",
    )
    pem = "-----BEGIN CERTIFICATE-----\nABC\n-----END CERTIFICATE-----\n"
    ca_path = persist_ca_pem(cfg, pem)
    assert ca_path is not None and ca_path.is_file()
    settings = load_connect_settings(config_path=str(cfg), allow_incomplete=True)
    assert settings.ca_file == str(ca_path)
    # Default verify off — CA is stored for when operator enables tls_verify.
    assert settings.tls_verify is False
    assert httpx_verify(settings) is False
    settings.tls_verify = True
    assert httpx_verify(settings) == str(ca_path)
