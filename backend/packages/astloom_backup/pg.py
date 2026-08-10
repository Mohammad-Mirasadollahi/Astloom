"""Postgres scoped table export/import."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from astloom_backup.scope import Scope
from astloom_backup.secrets import assert_no_secrets
from astloom_backup.tables import PG_TABLES, TableSpec


def database_url(env: dict[str, str] | None = None) -> str:
    e = env if env is not None else os.environ
    url = (
        str(e.get("ASTLOOM_DATABASE_URL") or "").strip()
        or str(e.get("DATABASE_URL") or "").strip()
    )
    if url.startswith("postgresql+psycopg://"):
        url = "postgresql://" + url[len("postgresql+psycopg://") :]
    if not url:
        raise RuntimeError("ASTLOOM_DATABASE_URL is required for backup/restore")
    return url


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or database_url(), row_factory=dict_row)


def _table_exists(conn: psycopg.Connection, schema: str, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
            """,
            (schema, table),
        )
        return cur.fetchone() is not None


def _columns(conn: psycopg.Connection, schema: str, table: str) -> list[str]:
    return list(_column_types(conn, schema, table))


def _column_types(conn: psycopg.Connection, schema: str, table: str) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, udt_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        out: dict[str, str] = {}
        for r in cur.fetchall():
            name = str(r["column_name"])
            udt = str(r["udt_name"] or "")
            data_type = str(r["data_type"] or "")
            out[name] = udt or data_type
        return out


def _scope_where(columns: list[str]) -> str | None:
    needed = ("tenant_id", "workspace_id", "project_id")
    if not all(c in columns for c in needed):
        return None
    return "tenant_id = %s AND workspace_id = %s AND project_id = %s"


def count_scope_rows(conn: psycopg.Connection, scope: Scope) -> int:
    total = 0
    for spec in PG_TABLES:
        if not _table_exists(conn, spec.schema, spec.table):
            continue
        cols = _columns(conn, spec.schema, spec.table)
        where = _scope_where(cols)
        if not where:
            continue
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) AS c FROM {spec.schema}.{spec.table} WHERE {where}",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            total += int(cur.fetchone()["c"])
    return total


def export_table(
    conn: psycopg.Connection,
    spec: TableSpec,
    scope: Scope,
    dest: Path,
) -> int:
    if not _table_exists(conn, spec.schema, spec.table):
        return 0
    cols = _columns(conn, spec.schema, spec.table)
    where = _scope_where(cols)
    if not where:
        return 0
    select_parts: list[str] = []
    for col in cols:
        if col in spec.vector_columns:
            select_parts.append(f"{col}::text AS {col}")
        else:
            select_parts.append(col)
    sql = (
        f"SELECT {', '.join(select_parts)} FROM {spec.schema}.{spec.table} "
        f"WHERE {where} ORDER BY 1"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with conn.cursor() as cur, dest.open("w", encoding="utf-8") as fh:
        cur.execute(sql, (scope.tenant_id, scope.workspace_id, scope.project_id))
        for row in cur:
            payload = _serialize_row(dict(row))
            assert_no_secrets(payload, context=f"{spec.schema}.{spec.table}")
            fh.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
            count += 1
    return count


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def import_table(
    conn: psycopg.Connection,
    spec: TableSpec,
    rows: Iterator[dict[str, Any]],
    *,
    require_insert: bool = False,
) -> int:
    if not _table_exists(conn, spec.schema, spec.table):
        # Skip missing optional tables (e.g. embeddings before migration).
        pending = list(rows)
        if pending and require_insert:
            raise RuntimeError(
                f"target missing table {spec.schema}.{spec.table} "
                f"but bundle has {len(pending)} row(s)"
            )
        return 0
    col_types = _column_types(conn, spec.schema, spec.table)
    cols = list(col_types)
    attempted = 0
    inserted = 0
    with conn.cursor() as cur:
        for row in rows:
            assert_no_secrets(row, context=f"{spec.schema}.{spec.table}")
            use_cols = [c for c in cols if c in row]
            if not use_cols:
                continue
            placeholders: list[str] = []
            values: list[Any] = []
            for col in use_cols:
                value = row[col]
                udt = col_types.get(col, "")
                if col in spec.vector_columns:
                    placeholders.append("%s::vector")
                    values.append(value)
                elif udt in {"json", "jsonb"} or isinstance(value, (dict, list)):
                    placeholders.append("%s")
                    values.append(Json(value))
                else:
                    placeholders.append("%s")
                    values.append(value)
            sql = (
                f"INSERT INTO {spec.schema}.{spec.table} ({', '.join(use_cols)}) "
                f"VALUES ({', '.join(placeholders)}) "
                f"ON CONFLICT DO NOTHING"
            )
            cur.execute(sql, values)
            attempted += 1
            inserted += int(cur.rowcount or 0)
    if require_insert and attempted and inserted < attempted:
        raise RuntimeError(
            f"import conflict in {spec.schema}.{spec.table}: "
            f"attempted={attempted} inserted={inserted} "
            "(primary keys collide; wipe target or remap ids)"
        )
    return inserted


def schema_table_fingerprint(conn: psycopg.Connection) -> dict[str, list[str]]:
    """Present tables per store schema (migration presence hint)."""
    out: dict[str, list[str]] = {}
    for spec in PG_TABLES:
        present = out.setdefault(spec.store_id, [])
        if _table_exists(conn, spec.schema, spec.table):
            present.append(f"{spec.schema}.{spec.table}")
    for store_id, tables in list(out.items()):
        out[store_id] = sorted(tables)
    return out


def gate_schema_fingerprint(
    bundle_fp: dict[str, Any],
    host_fp: dict[str, list[str]],
) -> None:
    """Fail when host is missing tables that the bundle used."""
    if not isinstance(bundle_fp, dict):
        return
    for store_id, tables in bundle_fp.items():
        if not isinstance(tables, list):
            continue
        host_tables = set(host_fp.get(str(store_id)) or [])
        missing = [t for t in tables if str(t) not in host_tables]
        if missing:
            raise ValueError(
                f"host missing tables required by bundle store={store_id}: {missing}"
            )


def wipe_scope_pg(conn: psycopg.Connection, scope: Scope) -> dict[str, int]:
    deleted: dict[str, int] = {}
    # Children before parents roughly — embeddings first via reverse order.
    for spec in reversed(PG_TABLES):
        if not _table_exists(conn, spec.schema, spec.table):
            continue
        cols = _columns(conn, spec.schema, spec.table)
        where = _scope_where(cols)
        if not where:
            continue
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {spec.schema}.{spec.table} WHERE {where}",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            deleted[f"{spec.schema}.{spec.table}"] = int(cur.rowcount)
    return deleted
