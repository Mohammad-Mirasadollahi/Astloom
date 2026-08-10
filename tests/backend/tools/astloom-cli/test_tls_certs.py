"""Tests for TLS auto-certificate material under the Astloom data root."""

from __future__ import annotations

import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def test_ensure_tls_material_creates_once(tmp_path: Path) -> None:
    from astloom_cli.tls_certs import ensure_tls_material

    first = ensure_tls_material(data_root=tmp_path, hostname="astloom.test")
    assert first.cert_path.is_file()
    assert first.key_path.is_file()
    assert first.ca_pem_path.is_file()
    assert first.generated is True
    second = ensure_tls_material(data_root=tmp_path, hostname="astloom.test")
    assert second.generated is False
    assert second.cert_path == first.cert_path


def test_ensure_tls_material_uses_operator_env_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astloom_cli.tls_certs import ensure_tls_material

    operator_cert = tmp_path / "operator.pem"
    operator_key = tmp_path / "operator.key"
    operator_cert.write_text("CERT", encoding="utf-8")
    operator_key.write_text("KEY", encoding="utf-8")

    monkeypatch.setenv("ASTLOOM_TLS_CERT", str(operator_cert))
    monkeypatch.setenv("ASTLOOM_TLS_KEY", str(operator_key))

    material = ensure_tls_material(data_root=tmp_path / "data", hostname="astloom.test")
    assert material.generated is False
    assert material.cert_path == operator_cert.resolve()
    assert material.key_path == operator_key.resolve()
    assert not (tmp_path / "data" / "certs" / "server.pem").exists()


def test_ensure_tls_material_key_permissions(tmp_path: Path) -> None:
    from astloom_cli.tls_certs import ensure_tls_material

    material = ensure_tls_material(data_root=tmp_path, hostname="astloom.test")
    key_mode = stat.S_IMODE(material.key_path.stat().st_mode)
    ca_key = material.ca_pem_path.parent / "ca.key"
    assert ca_key.is_file()
    ca_key_mode = stat.S_IMODE(ca_key.stat().st_mode)
    assert key_mode == 0o600
    assert ca_key_mode == 0o600


def test_ensure_tls_material_renews_near_expiry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from astloom_cli.tls_certs import LEAF_RENEW_BEFORE_DAYS, ensure_tls_material

    first = ensure_tls_material(data_root=tmp_path, hostname="astloom.test")
    assert first.generated is True

    near_expiry = datetime.now(timezone.utc) + timedelta(days=LEAF_RENEW_BEFORE_DAYS - 1)
    monkeypatch.setattr("astloom_cli.tls_certs._read_cert_not_after", lambda _p: near_expiry)

    renewed = ensure_tls_material(data_root=tmp_path, hostname="astloom.test")
    assert renewed.generated is True
    assert renewed.cert_path == first.cert_path
