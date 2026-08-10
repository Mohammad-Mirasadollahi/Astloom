"""Live: real Postgres/Neo4j backup export → remap restore → conflict → replace → wipe."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from astloom_backup.orchestrator import (
    dry_run_bundle,
    export_bundle,
    restore_bundle,
    scope_is_nonempty,
    wipe_scope,
)
from astloom_backup.pg import connect, database_url
from astloom_backup.scope import Remap, Scope

_REPO = Path(__file__).resolve().parents[4]


def _load_runtime_env() -> None:
    from astloom_cli.cli_defaults import load_dotenv_files
    from astloom_cli.remote_client import apply_compose_env_to_os

    load_dotenv_files(root=_REPO)
    if not str(os.environ.get("ASTLOOM_DATABASE_URL") or "").strip():
        try:
            apply_compose_env_to_os(os.environ, _REPO)
        except SystemExit:
            pass


def _require_live_db() -> None:
    _load_runtime_env()
    try:
        database_url()
    except RuntimeError as exc:
        pytest.skip(str(exc))
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'memory' AND table_name = 'memory_items'
                    """
                )
                if cur.fetchone() is None:
                    pytest.skip("memory.memory_items missing")
    except Exception as exc:
        pytest.skip(f"database unavailable: {exc}")


@pytest.mark.live
def test_live_backup_remap_restore_roundtrip(tmp_path: Path, monkeypatch):
    _require_live_db()
    monkeypatch.setenv("ASTLOOM_ROOT", str(tmp_path))
    suffix = uuid.uuid4().hex[:8]
    source = Scope(f"lv_t_{suffix}", f"lv_w_{suffix}", f"lv_p_{suffix}")
    target = Scope(f"lv_rt_{suffix}", f"lv_rw_{suffix}", f"lv_rp_{suffix}")
    mem_id = f"live_mem_{suffix}"
    ctx_id = f"live_ctx_{suffix}"

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory.memory_items (
                    id, tenant_id, workspace_id, project_id, actor_id, correlation_id,
                    kind, state, title, body, tags, evidence_refs, source_refs,
                    confidence, version, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, 'live', 'c1', 'semantic', 'active',
                    'live-backup', 'body', '[]'::jsonb, '[]'::jsonb, '[]'::jsonb,
                    0.9, 1, now(), now()
                )
                """,
                (mem_id, source.tenant_id, source.workspace_id, source.project_id),
            )
            cur.execute(
                """
                INSERT INTO common_context.documents (
                    id, kind, tenant_id, workspace_id, project_id, status, payload, created_at
                ) VALUES (
                    %s, 'rule', %s, %s, %s, 'active', %s::jsonb, now()
                )
                """,
                (
                    ctx_id,
                    source.tenant_id,
                    source.workspace_id,
                    source.project_id,
                    json.dumps({"slug": "live-backup"}),
                ),
            )
        conn.commit()

    asbak = tmp_path / "live.asbak"
    exported = export_bundle(source, asbak, repo_root=tmp_path)
    assert exported["ok"] is True
    assert exported["store_counts"]["memory"] >= 1
    assert exported["store_counts"]["common_context"] >= 1

    dry = dry_run_bundle(
        asbak,
        repo_root=tmp_path,
        remap=Remap(
            tenant_id=target.tenant_id,
            workspace_id=target.workspace_id,
            project_id=target.project_id,
        ),
    )
    assert dry["would_fail_conflict"] is False

    restored = restore_bundle(
        asbak,
        repo_root=tmp_path,
        remap=Remap(
            tenant_id=target.tenant_id,
            workspace_id=target.workspace_id,
            project_id=target.project_id,
        ),
    )
    assert restored["ok"] is True
    assert restored["verification"]["ok"] is True
    assert scope_is_nonempty(target)

    with pytest.raises(ValueError, match="not empty"):
        restore_bundle(
            asbak,
            repo_root=tmp_path,
            remap=Remap(
                tenant_id=target.tenant_id,
                workspace_id=target.workspace_id,
                project_id=target.project_id,
            ),
        )

    replaced = restore_bundle(
        asbak,
        repo_root=tmp_path,
        remap=Remap(
            tenant_id=target.tenant_id,
            workspace_id=target.workspace_id,
            project_id=target.project_id,
        ),
        replace=True,
        yes=True,
    )
    assert replaced["ok"] is True

    wipe_scope(source, repo_root=_REPO)
    wipe_scope(target, repo_root=_REPO)
    assert not scope_is_nonempty(source)
    assert not scope_is_nonempty(target)
