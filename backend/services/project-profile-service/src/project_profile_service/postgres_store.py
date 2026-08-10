from __future__ import annotations

from typing import Any
from uuid import uuid4

from .core import ConflictError, NotFoundError, Scope


class PostgresStore:
    """PostgreSQL adapter for the Project Profile Store port (psycopg, sibling pattern)."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Project Profile database URL must use PostgreSQL")
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
            cursor.execute("CREATE SCHEMA IF NOT EXISTS project_profile")
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS project_profile.documents (
                    id text PRIMARY KEY, kind text NOT NULL, tenant_id text NOT NULL,
                    workspace_id text NOT NULL, project_id text,
                    payload jsonb NOT NULL, created_at timestamptz NOT NULL)"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS project_profile.idempotency (
                    scope_key text NOT NULL, resource text NOT NULL, idempotency_key text NOT NULL,
                    resource_id text NOT NULL, PRIMARY KEY (scope_key, resource, idempotency_key))"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS project_profile.outbox (
                    seq bigserial PRIMARY KEY, payload jsonb NOT NULL,
                    occurred_at timestamptz NOT NULL DEFAULT now())"""
            )

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id))

    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT resource_id FROM project_profile.idempotency
                   WHERE scope_key=%s AND resource=%s AND idempotency_key=%s""",
                (self._scope_key(scope), resource, key),
            )
            row = cursor.fetchone()
        return None if row is None else row["resource_id"]

    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT resource_id FROM project_profile.idempotency
                   WHERE scope_key=%s AND resource=%s AND idempotency_key=%s""",
                (self._scope_key(scope), resource, key),
            )
            row = cursor.fetchone()
            if row is not None and row["resource_id"] != resource_id:
                raise ConflictError("idempotency key already bound to another resource")
            cursor.execute(
                """INSERT INTO project_profile.idempotency (scope_key, resource, idempotency_key, resource_id)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (scope_key, resource, idempotency_key) DO NOTHING""",
                (self._scope_key(scope), resource, key, resource_id),
            )

    def append_event(self, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("event_id", f"evt_{uuid4().hex[:12]}")
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO project_profile.outbox (payload) VALUES (%s)",
                (self._json(payload),),
            )

    def outbox(self) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM project_profile.outbox ORDER BY seq")
            return [row["payload"] for row in cursor.fetchall()]

    def put_project(self, project: dict[str, Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO project_profile.documents
                   (id, kind, tenant_id, workspace_id, project_id, payload, created_at)
                   VALUES (%s,'project',%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload""",
                (
                    project["id"],
                    project["tenant_id"],
                    project["workspace_id"],
                    project["project_id"],
                    self._json(project),
                    project["created_at"],
                ),
            )

    def get_project(self, project_id: str, scope: Scope) -> dict[str, Any]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT payload FROM project_profile.documents
                   WHERE id=%s AND kind='project' AND tenant_id=%s AND workspace_id=%s AND project_id=%s""",
                (project_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("project not found")
        return dict(row["payload"])

    def put_group(self, group: dict[str, Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO project_profile.documents
                   (id, kind, tenant_id, workspace_id, project_id, payload, created_at)
                   VALUES (%s,'project_group',%s,%s,NULL,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload""",
                (
                    group["id"],
                    group["tenant_id"],
                    group["workspace_id"],
                    self._json(group),
                    group["created_at"],
                ),
            )

    def get_group(self, group_id: str, tenant_id: str, workspace_id: str) -> dict[str, Any]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT payload FROM project_profile.documents
                   WHERE id=%s AND kind='project_group' AND tenant_id=%s AND workspace_id=%s""",
                (group_id, tenant_id, workspace_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("project group not found")
        return dict(row["payload"])

    def close(self) -> None:
        self._connection.close()
