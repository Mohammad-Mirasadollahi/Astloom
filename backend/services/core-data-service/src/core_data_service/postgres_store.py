from __future__ import annotations

from typing import Any

from .core import ConflictError, Kind, NotFoundError, Record, Scope, digest


def _timestamp(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


class PostgresStore:
    """PostgreSQL adapter for the Core Data Store port."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Core Data database URL must use PostgreSQL")
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover - exercised by deployment preflight
            raise RuntimeError("psycopg is required for PostgreSQL persistence") from exc
        normalized_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self._connection = psycopg.connect(normalized_url, autocommit=True, row_factory=dict_row)
        self._json = Jsonb

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id))

    @staticmethod
    def _record(row: dict[str, Any], scope: Scope) -> Record:
        return Record(
            row["id"], Kind(row["kind"]), scope, row["actor_id"], row["correlation_id"], row["status"],
            row["data"], _timestamp(row["created_at"]), _timestamp(row["updated_at"]), row["version"],
        )

    def get(self, record_id: str, scope: Scope) -> Record:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM core_data.records
                   WHERE id=%s AND tenant_id=%s AND workspace_id=%s AND project_id=%s""",
                (record_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("record not found in project scope")
        return self._record(row, scope)

    def list(self, kind: Kind, scope: Scope) -> list[Record]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM core_data.records
                   WHERE kind=%s AND tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (kind.value, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            rows = cursor.fetchall()
        return [self._record(row, scope) for row in rows]

    def put(self, record: Record) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO core_data.records
                   (id,kind,tenant_id,workspace_id,project_id,actor_id,correlation_id,status,version,data,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, version=EXCLUDED.version,
                   data=EXCLUDED.data, updated_at=EXCLUDED.updated_at""",
                (record.id, record.kind.value, record.scope.tenant_id, record.scope.workspace_id,
                 record.scope.project_id, record.actor_id, record.correlation_id, record.status,
                 record.version, self._json(record.data), record.created_at, record.updated_at),
            )

    def delete(self, record_id: str, scope: Scope) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """DELETE FROM core_data.records
                   WHERE id=%s AND tenant_id=%s AND workspace_id=%s AND project_id=%s""",
                (record_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("record not found in project scope")

    def idempotent(self, scope: Scope, command: str, key: str, payload: dict[str, Any]) -> str | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT fingerprint,record_id FROM core_data.idempotency
                   WHERE scope_key=%s AND command=%s AND idempotency_key=%s""",
                (self._scope_key(scope), command, key),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        if row["fingerprint"] != digest(payload):
            raise ConflictError("idempotency key was reused with a different payload")
        return row["record_id"]

    def remember(self, scope: Scope, command: str, key: str, payload: dict[str, Any], record_id: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO core_data.idempotency
                   (scope_key,command,idempotency_key,fingerprint,record_id) VALUES (%s,%s,%s,%s,%s)""",
                (self._scope_key(scope), command, key, digest(payload), record_id),
            )

    def event(self, payload: dict[str, Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO core_data.outbox (event_id,event_type,payload,occurred_at)
                   VALUES (%s,%s,%s,%s)""",
                (payload["event_id"], payload["event_type"], self._json(payload), payload["occurred_at"]),
            )

    def outbox(self) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM core_data.outbox ORDER BY occurred_at,event_id")
            return [row["payload"] for row in cursor.fetchall()]

    def close(self) -> None:
        self._connection.close()
