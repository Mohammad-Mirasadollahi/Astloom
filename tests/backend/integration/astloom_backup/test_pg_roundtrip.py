"""Integration: export/import Postgres-scoped rows when DATABASE_URL is available."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

from astloom_backup.orchestrator import export_bundle, restore_bundle, scope_is_nonempty
from astloom_backup.pg import connect, database_url
from astloom_backup.scope import Remap, Scope

_REPO = Path(__file__).resolve().parents[4]


def _load_dogfood_database_url() -> None:
    """Adopt local dogfood DB/Neo4j env from .astloom/mcp-servers.json when present."""
    path = _REPO / ".astloom" / "mcp-servers.json"
    if not path.is_file():
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    servers = doc.get("mcpServers") if isinstance(doc, dict) else None
    if not isinstance(servers, dict):
        return
    for server in servers.values():
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
                    WHERE table_schema = 'core_data' AND table_name = 'records'
                    """
                )
                if cur.fetchone() is None:
                    pytest.skip("core_data.records missing")
    except Exception as exc:
        pytest.skip(f"database unavailable: {exc}")


def test_core_data_export_restore_roundtrip(tmp_path: Path, monkeypatch):
    _require_db()
    monkeypatch.setenv("ASTLOOM_ROOT", str(tmp_path))
    suffix = uuid.uuid4().hex[:8]
    scope = Scope(
        tenant_id=f"bk_t_{suffix}",
        workspace_id=f"bk_w_{suffix}",
        project_id=f"bk_p_{suffix}",
    )
    record_id = f"rec_{suffix}"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO core_data.records (
                    id, kind, tenant_id, workspace_id, project_id, actor_id,
                    correlation_id, status, version, data, created_at, updated_at
                ) VALUES (
                    %s, 'task', %s, %s, %s, 'test', 'c1', 'proposed', 1,
                    %s::jsonb, now(), now()
                )
                """,
                (
                    record_id,
                    scope.tenant_id,
                    scope.workspace_id,
                    scope.project_id,
                    json.dumps({"title": "backup-roundtrip"}),
                ),
            )
        conn.commit()

    asbak = tmp_path / "rt.asbak"
    exported = export_bundle(scope, asbak, repo_root=tmp_path)
    assert exported["ok"] is True
    assert exported["store_counts"].get("core_data", 0) >= 1

    # Remove source rows so primary keys do not collide on same-server remap.
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM core_data.records WHERE tenant_id = %s AND project_id = %s",
                (scope.tenant_id, scope.project_id),
            )
        conn.commit()

    target = Scope(scope.tenant_id, scope.workspace_id, f"bk_p2_{suffix}")
    restored = restore_bundle(
        asbak,
        repo_root=tmp_path,
        remap=Remap(project_id=target.project_id),
        replace=False,
        yes=False,
    )
    assert restored["ok"] is True
    assert scope_is_nonempty(target)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS c FROM core_data.records
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                """,
                (target.tenant_id, target.workspace_id, target.project_id),
            )
            assert int(cur.fetchone()["c"]) >= 1
            # cleanup
            cur.execute(
                """
                DELETE FROM core_data.records
                WHERE tenant_id = %s AND workspace_id = %s
                  AND project_id IN (%s, %s)
                """,
                (scope.tenant_id, scope.workspace_id, scope.project_id, target.project_id),
            )
        conn.commit()


def test_conflict_fail_closed(tmp_path: Path, monkeypatch):
    _require_db()
    monkeypatch.setenv("ASTLOOM_ROOT", str(tmp_path))
    suffix = uuid.uuid4().hex[:8]
    scope = Scope(f"cf_t_{suffix}", f"cf_w_{suffix}", f"cf_p_{suffix}")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO core_data.records (
                    id, kind, tenant_id, workspace_id, project_id, actor_id,
                    correlation_id, status, version, data, created_at, updated_at
                ) VALUES (
                    %s, 'task', %s, %s, %s, 'test', 'c1', 'proposed', 1,
                    '{}'::jsonb, now(), now()
                )
                """,
                (f"rec_a_{suffix}", scope.tenant_id, scope.workspace_id, scope.project_id),
            )
        conn.commit()

    asbak = tmp_path / "cf.asbak"
    export_bundle(scope, asbak, repo_root=tmp_path)

    with pytest.raises(ValueError, match="not empty"):
        restore_bundle(asbak, repo_root=tmp_path, replace=False, yes=False)

    # replace path
    restored = restore_bundle(asbak, repo_root=tmp_path, replace=True, yes=True)
    assert restored["ok"] is True

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM core_data.records WHERE tenant_id = %s",
                (scope.tenant_id,),
            )
        conn.commit()
