"""Auto-generate TLS CA and server certificate material under the data root.

Module contract:
- Role: ensure private CA + leaf cert exist under ``{data_root}/certs/`` or honor
  operator-supplied cert/key paths from environment variables.
- SoT / invariants: ``ca.pem``, ``ca.key``, ``server.pem``, ``server.key`` under
  ``certs/``; operator env paths win when both files exist; keys are mode ``0600``.
- Failures: never log private key material; renew auto-generated leaf when near expiry.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

DEFAULT_CERT_ENV = "ASTLOOM_TLS_CERT"
DEFAULT_KEY_ENV = "ASTLOOM_TLS_KEY"

CERTS_DIR_NAME = "certs"
CA_PEM_NAME = "ca.pem"
CA_KEY_NAME = "ca.key"
SERVER_CERT_NAME = "server.pem"
SERVER_KEY_NAME = "server.key"
MARKER_NAME = ".astloom-certs.json"

CA_VALIDITY_DAYS = 3650
LEAF_VALIDITY_DAYS = 825
LEAF_RENEW_BEFORE_DAYS = 30
KEY_MODE = 0o600
PEM_MODE = 0o644


@dataclass(frozen=True)
class TlsMaterial:
    ca_pem_path: Path
    cert_path: Path
    key_path: Path
    generated: bool


def ensure_tls_material(
    *,
    data_root: Path,
    hostname: str,
    cert_env: str = "",
    key_env: str = "",
) -> TlsMaterial:
    """Return TLS paths, generating CA + leaf under ``data_root`` when needed."""
    certs_dir = data_root / CERTS_DIR_NAME
    ca_pem_path = certs_dir / CA_PEM_NAME
    server_cert_path = certs_dir / SERVER_CERT_NAME
    server_key_path = certs_dir / SERVER_KEY_NAME

    operator = _resolve_operator_material(
        cert_env=cert_env or DEFAULT_CERT_ENV,
        key_env=key_env or DEFAULT_KEY_ENV,
        ca_pem_path=ca_pem_path,
    )
    if operator is not None:
        return operator

    if _has_reusable_leaf(server_cert_path, server_key_path):
        return TlsMaterial(
            ca_pem_path=ca_pem_path,
            cert_path=server_cert_path,
            key_path=server_key_path,
            generated=False,
        )

    certs_dir.mkdir(parents=True, exist_ok=True)
    _ensure_ca_material(certs_dir)
    _write_leaf_certificate(
        certs_dir=certs_dir,
        hostname=hostname,
        server_cert_path=server_cert_path,
        server_key_path=server_key_path,
    )
    _write_marker(
        certs_dir / MARKER_NAME,
        hostname=hostname,
        not_after=_read_cert_not_after(server_cert_path),
    )
    return TlsMaterial(
        ca_pem_path=ca_pem_path,
        cert_path=server_cert_path,
        key_path=server_key_path,
        generated=True,
    )


def _resolve_operator_material(
    *,
    cert_env: str,
    key_env: str,
    ca_pem_path: Path,
) -> TlsMaterial | None:
    cert_value = os.environ.get(cert_env, "").strip()
    key_value = os.environ.get(key_env, "").strip()
    if not cert_value or not key_value:
        return None
    cert_path = Path(cert_value)
    key_path = Path(key_value)
    if not cert_path.is_file() or not key_path.is_file():
        return None
    return TlsMaterial(
        ca_pem_path=ca_pem_path,
        cert_path=cert_path.resolve(),
        key_path=key_path.resolve(),
        generated=False,
    )


def _has_reusable_leaf(cert_path: Path, key_path: Path) -> bool:
    if not cert_path.is_file() or not key_path.is_file():
        return False
    not_after = _read_cert_not_after(cert_path)
    now = datetime.now(timezone.utc)
    if not_after <= now:
        return False
    renew_before = now + timedelta(days=LEAF_RENEW_BEFORE_DAYS)
    return not_after > renew_before


def _read_cert_not_after(cert_path: Path) -> datetime:
    pem = cert_path.read_bytes()
    cert = x509.load_pem_x509_certificate(pem)
    not_after = cert.not_valid_after_utc
    if not_after.tzinfo is None:
        return not_after.replace(tzinfo=timezone.utc)
    return not_after


def _ensure_ca_material(certs_dir: Path) -> None:
    ca_pem_path = certs_dir / CA_PEM_NAME
    ca_key_path = certs_dir / CA_KEY_NAME
    if ca_pem_path.is_file() and ca_key_path.is_file():
        return

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = _build_name(common_name="Astloom Private CA")
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=CA_VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )
    _write_private_key(ca_key_path, private_key)
    _write_text_file(ca_pem_path, cert.public_bytes(serialization.Encoding.PEM), PEM_MODE)


def _write_leaf_certificate(
    *,
    certs_dir: Path,
    hostname: str,
    server_cert_path: Path,
    server_key_path: Path,
) -> None:
    ca_pem_path = certs_dir / CA_PEM_NAME
    ca_key_path = certs_dir / CA_KEY_NAME
    ca_cert = x509.load_pem_x509_certificate(ca_pem_path.read_bytes())
    ca_private_key = serialization.load_pem_private_key(
        ca_key_path.read_bytes(),
        password=None,
    )

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = _build_name(common_name=hostname)
    now = datetime.now(timezone.utc)
    from ipaddress import ip_address

    san_names: list[x509.GeneralName] = [
        x509.DNSName(hostname),
        x509.DNSName("localhost"),
        x509.IPAddress(ip_address("127.0.0.1")),
    ]
    if hostname not in {"localhost", "127.0.0.1"}:
        try:
            san_names.append(x509.IPAddress(ip_address(hostname)))
        except ValueError:
            pass
    san = x509.SubjectAlternativeName(san_names)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=LEAF_VALIDITY_DAYS))
        .add_extension(san, critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_private_key, hashes.SHA256())
    )
    _write_private_key(server_key_path, private_key)
    _write_text_file(
        server_cert_path,
        cert.public_bytes(serialization.Encoding.PEM),
        PEM_MODE,
    )


def _build_name(*, common_name: str) -> x509.Name:
    return x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Astloom"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )


def _write_private_key(path: Path, private_key: rsa.RSAPrivateKey) -> None:
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _write_text_file(path, pem, KEY_MODE)


def _write_text_file(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        tmp.write_bytes(content)
        os.chmod(tmp, mode)
        tmp.replace(path)
        os.chmod(path, mode)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _write_marker(path: Path, *, hostname: str, not_after: datetime) -> None:
    payload = {
        "hostname": hostname,
        "not_after": not_after.astimezone(timezone.utc).isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_text_file(
        path,
        json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n",
        PEM_MODE,
    )
