"""Integration: multi-store export/restore with memory + common_context + replace."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

from astloom_backup.orchestrator import (
    dry_run_bundle,
    export_bundle,
    restore_bundle,
    scope_is_nonempty,
)
from astloom_backup.pg import connect, database_url
from astloom_backup.scope import Remap, Scope

_REPO = Path(__file__).resolve().parents[4]


def _load_dogfood_database_url() -> None:
    path = _REPO / ".astloom" / "mcp-servers.json"
    if not path.is_file():
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    for server in (doc.get("mcpServers") or {}).values():
        if not isinstance(server, dict):
            continue
        env = server.get("env")
        if not isinstance(env, dict):
            continue
        for key in (
            "ASTLOOM_DATABASE_URL",
            "ASTLOOM_NEO4J_PASSWORD",
            "ASTLOOM_NEO4J_URI",
            "ASTLOOM_NEO4J_USER",
            "ASTLOOM_CODE_GRAPH_STORE",
            "ASTLOOM_MCP_GRAPH_MODE",
        ):
            val = str(env.get(key) or "").strip()
            if val:
                os.environ[key] = val
        return


def _require_db() -> None:
    _load_dogfood_database_url()
    try:
        url = database_url()
    except RuntimeError as exc:
        pytest.skip(str(exc))
    try:
        with connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'memory' AND table_name = 'memory_items'
                    """
                )
                if cur.fetchone() is None:
                    pytest.skip("memory.memory_items missing")
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'common_context' AND table_name = 'documents'
                    """
                )
                if cur.fetchone() is None:
                    pytest.skip("common_context.documents missing")
    except Exception as exc:
        pytest.skip(f"database unavailable: {exc}")


def test_memory_and_context_roundtrip_with_replace(tmp_path: Path, monkeypatch):
    _require_db()
    monkeypatch.setenv("ASTLOOM_ROOT", str(tmp_path))
    suffix = uuid.uuid4().hex[:8]
    scope = Scope(f"ms_t_{suffix}", f"ms_w_{suffix}", f"ms_p_{suffix}")
    mem_id = f"mem_{suffix}"
    ctx_id = f"ctx_{suffix}"

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory.memory_items (
                    id, tenant_id, workspace_id, project_id, actor_id, correlation_id,
                    kind, state, title, body, tags, evidence_refs, source_refs,
                    confidence, version, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, 'test', 'c1', 'semantic', 'active',
                    'backup-mem', 'body', '[]'::jsonb, '[]'::jsonb, '[]'::jsonb,
                    0.9, 1, now(), now()
                )
                """,
                (mem_id, scope.tenant_id, scope.workspace_id, scope.project_id),
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
                    scope.tenant_id,
                    scope.workspace_id,
                    scope.project_id,
                    json.dumps({"slug": "backup-test"}),
                ),
            )
        conn.commit()

    # local project pin
    from astloom_cli import state

    state.save_project(
        state.default_state_root(tmp_path),
        {
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "name": "backup-test",
            "usage_profile": "programming-cursor-mcp",
        },
    )

    asbak = tmp_path / "multi.asbak"
    exported = export_bundle(scope, asbak, repo_root=tmp_path)
    assert exported["store_counts"].get("memory", 0) >= 1
    assert exported["store_counts"].get("common_context", 0) >= 1
    assert exported["store_counts"].get("local", 0) == 1
    assert "memory" in (exported.get("schema_fingerprint") or {})

    dry = dry_run_bundle(asbak, repo_root=tmp_path, replace=False)
    assert dry["would_fail_conflict"] is True

    restored = restore_bundle(asbak, repo_root=tmp_path, replace=True, yes=True)
    assert restored["ok"] is True
    assert restored["verification"]["ok"] is True
    assert scope_is_nonempty(scope)
    assert state.load_project(
        state.default_state_root(tmp_path),
        scope.tenant_id,
        scope.workspace_id,
        scope.project_id,
    )

    # cleanup
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM memory.memory_items WHERE tenant_id = %s",
                (scope.tenant_id,),
            )
            cur.execute(
                "DELETE FROM common_context.documents WHERE tenant_id = %s",
                (scope.tenant_id,),
            )
        conn.commit()


def test_memory_embedding_id_map_in_registry():
    from astloom_backup.tables import PG_TABLES

    assert any(
        t.schema == "memory" and t.table == "embedding_id_map" for t in PG_TABLES
    )
