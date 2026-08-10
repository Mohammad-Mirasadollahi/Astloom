from __future__ import annotations

from typing import Any
from uuid import uuid4

from .core import ConflictError, NotFoundError, Scope


class PostgresStore:
    """PostgreSQL adapter for the Reporting Store port (psycopg, sibling pattern)."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Reporting database URL must use PostgreSQL")
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgreSQL persistence") from exc
        normalized_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self._connection = psycopg.connect(normalized_url, autocommit=True, row_factory=dict_row)
        self._json = Jsonb
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS reporting")
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS reporting.documents (
                    id text PRIMARY KEY, kind text NOT NULL, tenant_id text NOT NULL,
                    workspace_id text NOT NULL, project_id text NOT NULL, kpi_name text,
                    payload jsonb NOT NULL, created_at timestamptz NOT NULL)"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS reporting.idempotency (
                    scope_key text NOT NULL, resource text NOT NULL, idempotency_key text NOT NULL,
                    resource_id text NOT NULL, PRIMARY KEY (scope_key, resource, idempotency_key))"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS reporting.outbox (
                    seq bigserial PRIMARY KEY, payload jsonb NOT NULL,
                    occurred_at timestamptz NOT NULL DEFAULT now())"""
            )

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id))

    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT resource_id FROM reporting.idempotency
                   WHERE scope_key=%s AND resource=%s AND idempotency_key=%s""",
                (self._scope_key(scope), resource, key),
            )
            row = cursor.fetchone()
        return None if row is None else row["resource_id"]

    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT resource_id FROM reporting.idempotency
                   WHERE scope_key=%s AND resource=%s AND idempotency_key=%s""",
                (self._scope_key(scope), resource, key),
            )
            row = cursor.fetchone()
            if row is not None and row["resource_id"] != resource_id:
                raise ConflictError("idempotency key already bound to another resource")
            cursor.execute(
                """INSERT INTO reporting.idempotency (scope_key, resource, idempotency_key, resource_id)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (scope_key, resource, idempotency_key) DO NOTHING""",
                (self._scope_key(scope), resource, key, resource_id),
            )

    def append_event(self, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("event_id", f"evt_{uuid4().hex[:12]}")
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO reporting.outbox (payload) VALUES (%s)",
                (self._json(payload),),
            )

    def outbox(self) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM reporting.outbox ORDER BY seq")
            return [row["payload"] for row in cursor.fetchall()]

    def put_sample(self, sample: dict[str, Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO reporting.documents
                   (id, kind, tenant_id, workspace_id, project_id, kpi_name, payload, created_at)
                   VALUES (%s,'kpi_sample',%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload""",
                (
                    sample["id"],
                    sample["tenant_id"],
                    sample["workspace_id"],
                    sample["project_id"],
                    sample["kpi_name"],
                    self._json(sample),
                    sample["created_at"],
                ),
            )

    def get_sample(self, sample_id: str, scope: Scope) -> dict[str, Any]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT payload FROM reporting.documents
                   WHERE id=%s AND kind='kpi_sample' AND tenant_id=%s AND workspace_id=%s AND project_id=%s""",
                (sample_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("sample not found")
        return dict(row["payload"])

    def list_samples(self, scope: Scope, kpi_name: str | None = None) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            if kpi_name:
                cursor.execute(
                    """SELECT payload FROM reporting.documents
                       WHERE kind='kpi_sample' AND tenant_id=%s AND workspace_id=%s AND project_id=%s
                       AND kpi_name=%s ORDER BY created_at, id""",
                    (scope.tenant_id, scope.workspace_id, scope.project_id, kpi_name),
                )
            else:
                cursor.execute(
                    """SELECT payload FROM reporting.documents
                       WHERE kind='kpi_sample' AND tenant_id=%s AND workspace_id=%s AND project_id=%s
                       ORDER BY created_at, id""",
                    (scope.tenant_id, scope.workspace_id, scope.project_id),
                )
            return [dict(row["payload"]) for row in cursor.fetchall()]

    def close(self) -> None:
        self._connection.close()
