from __future__ import annotations

from typing import Any

from .core import (
    BatchState,
    ConflictError,
    MemoryItem,
    MemoryKind,
    MemoryState,
    NotFoundError,
    QuestionMemory,
    QuestionState,
    Scope,
    WorkBatch,
    digest,
)


def _timestamp(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


class PostgresStore:
    """PostgreSQL adapter for the Memory Store port."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Memory database URL must use PostgreSQL")
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
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id, scope.project_group_id or ""))

    @staticmethod
    def _memory(row: dict[str, Any], scope: Scope) -> MemoryItem:
        expires = row.get("expires_at")
        return MemoryItem(
            row["id"],
            scope,
            row["actor_id"],
            row["correlation_id"],
            MemoryKind(row["kind"]),
            MemoryState(row["state"]),
            row["title"],
            row["body"],
            row["tags"],
            row["evidence_refs"],
            row["source_refs"],
            row["confidence"],
            _timestamp(row["created_at"]),
            _timestamp(row["updated_at"]),
            row["version"],
            pinned=bool(row.get("pinned", False)),
            expires_at=None if expires is None else _timestamp(expires),
        )

    @staticmethod
    def _question(row: dict[str, Any], scope: Scope) -> QuestionMemory:
        return QuestionMemory(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["normalized_question"],
            row["observations"], row["evidence_refs"], QuestionState(row["state"]), row["answer"],
            _timestamp(row["created_at"]), _timestamp(row["updated_at"]), row["version"],
        )

    @staticmethod
    def _batch(row: dict[str, Any], scope: Scope) -> WorkBatch:
        return WorkBatch(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["title"], row["item_refs"],
            row["deferred_actions"], BatchState(row["state"]), _timestamp(row["created_at"]),
            _timestamp(row["updated_at"]), row["version"],
        )

    def get_memory(self, memory_id: str, scope: Scope) -> MemoryItem:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM memory.memory_items WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (memory_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("memory item not found in project scope")
        return self._memory(row, scope)

    def put_memory(self, item: MemoryItem) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO memory.memory_items
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,kind,state,title,body,
                    tags,evidence_refs,source_refs,confidence,version,created_at,updated_at,pinned,expires_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET state=EXCLUDED.state,kind=EXCLUDED.kind,title=EXCLUDED.title,body=EXCLUDED.body,
                   tags=EXCLUDED.tags,evidence_refs=EXCLUDED.evidence_refs,source_refs=EXCLUDED.source_refs,
                   confidence=EXCLUDED.confidence,version=EXCLUDED.version,updated_at=EXCLUDED.updated_at,
                   pinned=EXCLUDED.pinned,expires_at=EXCLUDED.expires_at""",
                (
                    item.id,
                    item.scope.tenant_id,
                    item.scope.workspace_id,
                    item.scope.project_id,
                    item.scope.project_group_id,
                    item.actor_id,
                    item.correlation_id,
                    item.kind.value,
                    item.state.value,
                    item.title,
                    item.body,
                    self._json(item.tags),
                    self._json(item.evidence_refs),
                    self._json(item.source_refs),
                    item.confidence,
                    item.version,
                    item.created_at,
                    item.updated_at,
                    item.pinned,
                    item.expires_at,
                ),
            )

    def list_memory(self, scope: Scope) -> list[MemoryItem]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM memory.memory_items WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""", (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._memory(row, scope) for row in cursor.fetchall()]

    def get_question(self, question_id: str, scope: Scope) -> QuestionMemory:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM memory.question_memory WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (question_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("question memory not found in project scope")
        return self._question(row, scope)

    def find_question(self, normalized: str, scope: Scope) -> QuestionMemory | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM memory.question_memory WHERE normalized_question=%s
                   AND tenant_id=%s AND workspace_id=%s AND project_id=%s""",
                (normalized, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        return self._question(row, scope) if row else None

    def put_question(self, question: QuestionMemory) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO memory.question_memory
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,normalized_question,
                    observations,evidence_refs,state,answer,version,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET observations=EXCLUDED.observations,
                   evidence_refs=EXCLUDED.evidence_refs,state=EXCLUDED.state,answer=EXCLUDED.answer,
                   version=EXCLUDED.version,updated_at=EXCLUDED.updated_at""",
                (question.id,question.scope.tenant_id,question.scope.workspace_id,question.scope.project_id,
                 question.scope.project_group_id,question.actor_id,question.correlation_id,
                 question.normalized_question,question.observations,self._json(question.evidence_refs),question.state.value,
                 question.answer,question.version,question.created_at,question.updated_at),
            )

    def list_questions(self, scope: Scope) -> list[QuestionMemory]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM memory.question_memory WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY observations DESC,updated_at DESC,id""", (scope.tenant_id,scope.workspace_id,scope.project_id),
            )
            return [self._question(row, scope) for row in cursor.fetchall()]

    def get_batch(self, batch_id: str, scope: Scope) -> WorkBatch:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM memory.work_batches WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (batch_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("work batch not found in project scope")
        return self._batch(row, scope)

    def put_batch(self, batch: WorkBatch) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO memory.work_batches
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,title,item_refs,
                    deferred_actions,state,version,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET item_refs=EXCLUDED.item_refs,
                   deferred_actions=EXCLUDED.deferred_actions,state=EXCLUDED.state,
                   version=EXCLUDED.version,updated_at=EXCLUDED.updated_at""",
                (batch.id,batch.scope.tenant_id,batch.scope.workspace_id,batch.scope.project_id,
                 batch.scope.project_group_id,batch.actor_id,batch.correlation_id,batch.title,self._json(batch.item_refs),
                 self._json(batch.deferred_actions),batch.state.value,batch.version,batch.created_at,batch.updated_at),
            )

    def list_batches(self, scope: Scope) -> list[WorkBatch]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM memory.work_batches WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""", (scope.tenant_id,scope.workspace_id,scope.project_id),
            )
            return [self._batch(row, scope) for row in cursor.fetchall()]

    def idempotent(self, scope: Scope, command: str, key: str, payload: dict[str, Any]) -> str | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT fingerprint,record_id FROM memory.idempotency
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
                """INSERT INTO memory.idempotency
                   (scope_key,command,idempotency_key,fingerprint,record_id) VALUES (%s,%s,%s,%s,%s)""",
                (self._scope_key(scope), command, key, digest(payload), record_id),
            )

    def event(self, payload: dict[str, Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO memory.outbox (event_id,event_type,payload,occurred_at) VALUES (%s,%s,%s,%s)",
                (payload["event_id"], payload["event_type"], self._json(payload), payload["occurred_at"]),
            )

    def outbox(self) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM memory.outbox ORDER BY occurred_at,event_id")
            return [row["payload"] for row in cursor.fetchall()]

    def close(self) -> None:
        self._connection.close()
