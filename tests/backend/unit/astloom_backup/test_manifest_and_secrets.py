"""Unit tests for backup manifest, secrets, remap, and conflict gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astloom_backup.bundle import pack_directory, unpack_archive
from astloom_backup.manifest import (
    BUNDLE_SCHEMA_VERSION,
    build_manifest,
    gate_contract_version,
    validate_manifest_shape,
    verify_checksums,
    write_checksums,
)
from astloom_backup.remap import remap_row, resolve_target_scope
from astloom_backup.scope import Remap, Scope
from astloom_backup.secrets import assert_no_secrets, find_secret_hit


def test_manifest_shape_and_contract_gate():
    scope = Scope("t", "w", "p")
    m = build_manifest(
        scope=scope,
        contract_version="1",
        product_version="0.1.2",
        store_counts={"memory": 2},
        created_at="2026-08-01T00:00:00Z",
    )
    validate_manifest_shape(m)
    assert m["schema_version"] == BUNDLE_SCHEMA_VERSION
    gate_contract_version(m, expected="1")
    with pytest.raises(ValueError, match="contract_version mismatch"):
        gate_contract_version(m, expected="99")


def test_checksums_round_trip(tmp_path: Path):
    root = tmp_path / "bundle"
    root.mkdir()
    (root / "manifest.json").write_text('{"ok": true}\n', encoding="utf-8")
    write_checksums(root)
    verify_checksums(root)
    (root / "manifest.json").write_text('{"ok": false}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_checksums(root)


def test_pack_unpack(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "manifest.json").write_text('{"a": 1}\n', encoding="utf-8")
    asbak = tmp_path / "x.asbak"
    pack_directory(src, asbak)
    out = unpack_archive(asbak, tmp_path / "out")
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8"))["a"] == 1


def test_secret_scan_rejects_password_fields():
    assert find_secret_hit({"password": "hunter2"}) is not None
    with pytest.raises(ValueError, match="secret-like"):
        assert_no_secrets({"api_key": "abc"}, context="test")
    # Fingerprint metadata allowed
    assert find_secret_hit({"credential_fingerprint": "deadbeef"}) is None


def test_remap_scope_and_embedded_ids():
    source = Scope("t1", "w1", "p1")
    target = Scope("t2", "w2", "p2")
    row = {
        "tenant_id": "t1",
        "workspace_id": "w1",
        "project_id": "p1",
        "id": "sym:p1:mod.fn",
        "nested": {"project_id": "p1"},
    }
    out = remap_row(row, source=source, target=target)
    assert out["tenant_id"] == "t2"
    assert out["project_id"] == "p2"
    assert out["id"] == "sym:p2:mod.fn"
    assert out["nested"]["project_id"] == "p2"
    assert resolve_target_scope(source, Remap(project_id="p2")).project_id == "p2"


def test_remap_plain_text_primary_keys_for_same_server_clone():
    source = Scope("t1", "w1", "p1")
    target = Scope("t2", "w2", "p2")
    row = {
        "tenant_id": "t1",
        "workspace_id": "w1",
        "project_id": "p1",
        "id": "mem_abc",
        "memory_id": "mem_abc",
        "title": "keep-me",
        "nested": {"id": "mem_abc", "note": "keep-me"},
    }
    out = remap_row(row, source=source, target=target)
    assert out["id"] == "asbak:t2/w2/p2:mem_abc"
    assert out["memory_id"] == "asbak:t2/w2/p2:mem_abc"
    assert out["title"] == "keep-me"
    assert out["nested"]["id"] == "asbak:t2/w2/p2:mem_abc"
    assert out["nested"]["note"] == "keep-me"
    # Identity preserve when scopes match
    same = remap_row(row, source=source, target=source)
    assert same["id"] == "mem_abc"


def test_restore_replace_requires_yes():
    from astloom_backup.orchestrator import restore_bundle

    with pytest.raises(ValueError, match="replace requires --yes"):
        restore_bundle(
            Path("/nonexistent.asbak"),
            repo_root=Path("/tmp"),
            replace=True,
            yes=False,
        )
