"""Bundle manifest schema and gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from astloom_backup.scope import Scope

MANIFEST_NAME = "manifest.json"
CHECKSUMS_NAME = "evidence/checksums.json"
BUNDLE_SCHEMA_VERSION = "1.0.0"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    *,
    scope: Scope,
    contract_version: str,
    product_version: str,
    store_counts: dict[str, int],
    created_at: str,
    schema_fingerprint: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "contract_version": str(contract_version),
        "product_version": str(product_version),
        "created_at": created_at,
        "scope": scope.as_dict(),
        "stores": {k: {"row_count": int(v)} for k, v in sorted(store_counts.items())},
        "schema_fingerprint": schema_fingerprint or {},
    }


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest must be an object")
    return data


def validate_manifest_shape(manifest: dict[str, Any]) -> None:
    if str(manifest.get("schema_version") or "") != BUNDLE_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported bundle schema_version: {manifest.get('schema_version')!r} "
            f"(expected {BUNDLE_SCHEMA_VERSION})"
        )
    scope = manifest.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("manifest.scope is required")
    for key in ("tenant_id", "workspace_id", "project_id"):
        if not str(scope.get(key) or "").strip():
            raise ValueError(f"manifest.scope.{key} is required")
    if not isinstance(manifest.get("stores"), dict):
        raise ValueError("manifest.stores is required")


def gate_contract_version(manifest: dict[str, Any], *, expected: str) -> None:
    got = str(manifest.get("contract_version") or "")
    if got != str(expected):
        raise ValueError(
            f"contract_version mismatch: bundle={got!r} host={expected!r}"
        )


def write_checksums(root: Path) -> dict[str, str]:
    """Hash every file under *root* except evidence/checksums.json itself."""
    checksums: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == CHECKSUMS_NAME:
            continue
        checksums[rel] = sha256_file(path)
    out = root / CHECKSUMS_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(checksums, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return checksums


def verify_checksums(root: Path) -> None:
    path = root / CHECKSUMS_NAME
    if not path.is_file():
        raise ValueError("missing evidence/checksums.json")
    expected = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(expected, dict):
        raise ValueError("checksums must be an object")
    for rel, digest in sorted(expected.items()):
        file_path = root / rel
        if not file_path.is_file():
            raise ValueError(f"missing file for checksum: {rel}")
        got = sha256_file(file_path)
        if got != digest:
            raise ValueError(f"checksum mismatch: {rel}")
