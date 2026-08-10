from __future__ import annotations

from typing import Any
from uuid import uuid4

from .core import ConflictError, NotFoundError, Scope


class PostgresStore:
    """PostgreSQL adapter for the Orchestration Store port (psycopg, sibling pattern)."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Orchestration database URL must use PostgreSQL")
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
            cursor.execute("CREATE SCHEMA IF NOT EXISTS orchestration")
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS orchestration.documents (
                    id text PRIMARY KEY, kind text NOT NULL, tenant_id text NOT NULL,
                    workspace_id text NOT NULL, project_id text NOT NULL, batch_id text,
                    payload jsonb NOT NULL, created_at timestamptz NOT NULL)"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS orchestration.idempotency (
                    scope_key text NOT NULL, resource text NOT NULL, idempotency_key text NOT NULL,
                    resource_id text NOT NULL, PRIMARY KEY (scope_key, resource, idempotency_key))"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS orchestration.outbox (
                    seq bigserial PRIMARY KEY, payload jsonb NOT NULL,
                    occurred_at timestamptz NOT NULL DEFAULT now())"""
            )

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id))

    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT resource_id FROM orchestration.idempotency
                   WHERE scope_key=%s AND resource=%s AND idempotency_key=%s""",
                (self._scope_key(scope), resource, key),
            )
            row = cursor.fetchone()
        return None if row is None else row["resource_id"]

    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT resource_id FROM orchestration.idempotency
                   WHERE scope_key=%s AND resource=%s AND idempotency_key=%s""",
                (self._scope_key(scope), resource, key),
            )
            row = cursor.fetchone()
            if row is not None and row["resource_id"] != resource_id:
                raise ConflictError("idempotency key already bound to another resource")
            cursor.execute(
                """INSERT INTO orchestration.idempotency (scope_key, resource, idempotency_key, resource_id)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (scope_key, resource, idempotency_key) DO NOTHING""",
                (self._scope_key(scope), resource, key, resource_id),
            )

    def append_event(self, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("event_id", f"evt_{uuid4().hex[:12]}")
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO orchestration.outbox (payload) VALUES (%s)",
                (self._json(payload),),
            )

    def outbox(self) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM orchestration.outbox ORDER BY seq")
            return [row["payload"] for row in cursor.fetchall()]

    def put_batch(self, batch: dict[str, Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO orchestration.documents
                   (id, kind, tenant_id, workspace_id, project_id, batch_id, payload, created_at)
                   VALUES (%s,'work_batch',%s,%s,%s,NULL,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload""",
                (
                    batch["id"],
                    batch["tenant_id"],
                    batch["workspace_id"],
                    batch["project_id"],
                    self._json(batch),
                    batch["created_at"],
                ),
            )

    def get_batch(self, batch_id: str, scope: Scope) -> dict[str, Any]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT payload FROM orchestration.documents
                   WHERE id=%s AND kind='work_batch' AND tenant_id=%s AND workspace_id=%s AND project_id=%s""",
                (batch_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("work batch not found")
        return dict(row["payload"])

    def put_assignment(self, assignment: dict[str, Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO orchestration.documents
                   (id, kind, tenant_id, workspace_id, project_id, batch_id, payload, created_at)
                   VALUES (%s,'assignment',%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload, batch_id=EXCLUDED.batch_id""",
                (
                    assignment["id"],
                    assignment["tenant_id"],
                    assignment["workspace_id"],
                    assignment["project_id"],
                    assignment.get("batch_id"),
                    self._json(assignment),
                    assignment["created_at"],
                ),
            )

    def get_assignment(self, assignment_id: str, scope: Scope) -> dict[str, Any]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT payload FROM orchestration.documents
                   WHERE id=%s AND kind='assignment' AND tenant_id=%s AND workspace_id=%s AND project_id=%s""",
                (assignment_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("assignment not found")
        return dict(row["payload"])

    def list_assignments(self, scope: Scope, batch_id: str | None = None) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            if batch_id:
                cursor.execute(
                    """SELECT payload FROM orchestration.documents
                       WHERE kind='assignment' AND tenant_id=%s AND workspace_id=%s AND project_id=%s
                       AND batch_id=%s ORDER BY id""",
                    (scope.tenant_id, scope.workspace_id, scope.project_id, batch_id),
                )
            else:
                cursor.execute(
                    """SELECT payload FROM orchestration.documents
                       WHERE kind='assignment' AND tenant_id=%s AND workspace_id=%s AND project_id=%s
                       ORDER BY id""",
                    (scope.tenant_id, scope.workspace_id, scope.project_id),
                )
            return [dict(row["payload"]) for row in cursor.fetchall()]

    def put_agent_ticket(self, ticket: dict[str, Any], expected_version: int | None = None) -> None:
        with self._connection.cursor() as cursor:
            if expected_version is not None:
                cursor.execute(
                    """SELECT payload FROM orchestration.documents
                       WHERE id=%s AND kind='agent_ticket'""",
                    (ticket["id"],),
                )
                row = cursor.fetchone()
                if row is None or dict(row["payload"]).get("version") != expected_version:
                    raise ConflictError("agent ticket version conflict", code="version_conflict")
            cursor.execute(
                """INSERT INTO orchestration.documents
                   (id, kind, tenant_id, workspace_id, project_id, batch_id, payload, created_at)
                   VALUES (%s,'agent_ticket',%s,%s,%s,NULL,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload""",
                (
                    ticket["id"],
                    ticket["tenant_id"],
                    ticket["workspace_id"],
                    ticket["project_id"],
                    self._json(ticket),
                    ticket["created_at"],
                ),
            )

    def get_agent_ticket(self, ticket_id: str, scope: Scope) -> dict[str, Any]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT payload FROM orchestration.documents
                   WHERE id=%s AND kind='agent_ticket' AND tenant_id=%s AND workspace_id=%s AND project_id=%s""",
                (ticket_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("agent ticket not found")
        return dict(row["payload"])

    def list_agent_tickets(
        self,
        scope: Scope,
        *,
        status: str | None = None,
        agent_id: str | None = None,
        task_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT payload FROM orchestration.documents
                   WHERE kind='agent_ticket' AND tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at, id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            items = [dict(row["payload"]) for row in cursor.fetchall()]
        if status:
            items = [t for t in items if t.get("status") == status]
        if agent_id:
            items = [t for t in items if t.get("agent_id") == agent_id]
        if task_id:
            items = [t for t in items if t.get("task_id") == task_id]
        return items

    def close(self) -> None:
        self._connection.close()
