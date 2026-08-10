from __future__ import annotations

from typing import Any
from uuid import uuid4

from .core import ConflictError, NotFoundError, Scope


class PostgresStore:
    """PostgreSQL adapter for the Audit Store port (psycopg, sibling pattern)."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Audit database URL must use PostgreSQL")
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
            cursor.execute("CREATE SCHEMA IF NOT EXISTS audit")
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS audit.documents (
                    id text PRIMARY KEY, kind text NOT NULL, tenant_id text NOT NULL,
                    workspace_id text NOT NULL, project_id text NOT NULL, correlation_id text,
                    payload jsonb NOT NULL, created_at timestamptz NOT NULL)"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS audit.idempotency (
                    scope_key text NOT NULL, resource text NOT NULL, idempotency_key text NOT NULL,
                    resource_id text NOT NULL, PRIMARY KEY (scope_key, resource, idempotency_key))"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS audit.outbox (
                    seq bigserial PRIMARY KEY, payload jsonb NOT NULL,
                    occurred_at timestamptz NOT NULL DEFAULT now())"""
            )

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id))

    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT resource_id FROM audit.idempotency
                   WHERE scope_key=%s AND resource=%s AND idempotency_key=%s""",
                (self._scope_key(scope), resource, key),
            )
            row = cursor.fetchone()
        return None if row is None else row["resource_id"]

    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT resource_id FROM audit.idempotency
                   WHERE scope_key=%s AND resource=%s AND idempotency_key=%s""",
                (self._scope_key(scope), resource, key),
            )
            row = cursor.fetchone()
            if row is not None and row["resource_id"] != resource_id:
                raise ConflictError("idempotency key already bound to another resource")
            cursor.execute(
                """INSERT INTO audit.idempotency (scope_key, resource, idempotency_key, resource_id)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (scope_key, resource, idempotency_key) DO NOTHING""",
                (self._scope_key(scope), resource, key, resource_id),
            )

    def append_event(self, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("event_id", f"evt_{uuid4().hex[:12]}")
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO audit.outbox (payload) VALUES (%s)",
                (self._json(payload),),
            )

    def outbox(self) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM audit.outbox ORDER BY seq")
            return [row["payload"] for row in cursor.fetchall()]

    def put_audit_event(self, event: dict[str, Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT id FROM audit.documents WHERE id=%s AND kind='audit_event'", (event["id"],))
            if cursor.fetchone() is not None:
                raise ConflictError("audit events are immutable")
            cursor.execute(
                """INSERT INTO audit.documents
                   (id, kind, tenant_id, workspace_id, project_id, correlation_id, payload, created_at)
                   VALUES (%s,'audit_event',%s,%s,%s,%s,%s,%s)""",
                (
                    event["id"],
                    event["tenant_id"],
                    event["workspace_id"],
                    event["project_id"],
                    event.get("correlation_id"),
                    self._json(event),
                    event["created_at"],
                ),
            )

    def get_audit_event(self, event_id: str, scope: Scope) -> dict[str, Any]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT payload FROM audit.documents
                   WHERE id=%s AND kind='audit_event' AND tenant_id=%s AND workspace_id=%s AND project_id=%s""",
                (event_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("audit event not found")
        return dict(row["payload"])

    def list_audit_events(self, scope: Scope, correlation_id: str | None = None) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            if correlation_id:
                cursor.execute(
                    """SELECT payload FROM audit.documents
                       WHERE kind='audit_event' AND tenant_id=%s AND workspace_id=%s AND project_id=%s
                       AND correlation_id=%s ORDER BY created_at, id""",
                    (scope.tenant_id, scope.workspace_id, scope.project_id, correlation_id),
                )
            else:
                cursor.execute(
                    """SELECT payload FROM audit.documents
                       WHERE kind='audit_event' AND tenant_id=%s AND workspace_id=%s AND project_id=%s
                       ORDER BY created_at, id""",
                    (scope.tenant_id, scope.workspace_id, scope.project_id),
                )
            return [dict(row["payload"]) for row in cursor.fetchall()]

    def close(self) -> None:
        self._connection.close()
