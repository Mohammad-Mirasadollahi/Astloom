"""PostgreSQL pgvector index + outbox mirror (bounded connection pools).

Role: ANN embeddings and Neo4j→Postgres outbox mirror for hybrid retrieval.
Source of truth: ``code_graph.symbol_embeddings`` / ``code_graph.outbox``; SQL text
lives in ``postgres.sql``; writers borrow from a sized ``psycopg`` pool.
Allowed: concurrent upsert/search under ``LockedStore`` slot budget and pool max.
Forbidden: sharing one checked-out connection across threads; retaining one idle
client per worker thread; destructive dimension migration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, Sequence

from .domain.models import Scope
from .domain.rag import SEARCHABLE_SYMBOL_KINDS
from .pg_thread_local import ThreadLocalPsycopg
from .postgres import sql as pg_sql


class EmbeddingIndex(Protocol):
    def upsert(
        self,
        scope: Scope,
        symbol_id: str,
        vector: list[float],
        *,
        model: str,
        kind: str = "unknown",
    ) -> None: ...

    def delete(self, scope: Scope, symbol_id: str) -> None: ...

    def search(
        self,
        scope: Scope,
        vector: list[float],
        *,
        top_k: int = 5,
        kinds: Sequence[str] | None = None,
    ) -> list[tuple[str, float]]: ...


class InMemoryEmbeddingIndex:
    """Test double for EmbeddingIndex (thread-safe)."""

    def __init__(self) -> None:
        import threading

        # key → (vector, model, kind)
        self._rows: dict[tuple[str, str, str, str], tuple[list[float], str, str]] = {}
        self._lock = threading.RLock()

    def upsert(
        self,
        scope: Scope,
        symbol_id: str,
        vector: list[float],
        *,
        model: str,
        kind: str = "unknown",
    ) -> None:
        key = (scope.tenant_id, scope.workspace_id, scope.project_id, symbol_id)
        with self._lock:
            self._rows[key] = (list(vector), model, str(kind or "unknown"))

    def delete(self, scope: Scope, symbol_id: str) -> None:
        key = (scope.tenant_id, scope.workspace_id, scope.project_id, symbol_id)
        with self._lock:
            self._rows.pop(key, None)

    def delete_many(self, scope: Scope, symbol_ids: list[str]) -> int:
        with self._lock:
            drop = [
                (scope.tenant_id, scope.workspace_id, scope.project_id, symbol_id)
                for symbol_id in symbol_ids
                if (
                    scope.tenant_id,
                    scope.workspace_id,
                    scope.project_id,
                    symbol_id,
                )
                in self._rows
            ]
            for key in drop:
                del self._rows[key]
            return len(drop)

    def wipe_scope(self, scope: Scope) -> int:
        with self._lock:
            drop = [
                key
                for key in self._rows
                if key[:3] == (scope.tenant_id, scope.workspace_id, scope.project_id)
            ]
            for key in drop:
                del self._rows[key]
            return len(drop)

    def list_symbol_models(self, scope: Scope) -> dict[str, str]:
        """Return symbol_id → embedding model for one scope."""
        out: dict[str, str] = {}
        with self._lock:
            for (tenant, workspace, project, symbol_id), (_vec, model, _kind) in self._rows.items():
                if (tenant, workspace, project) != (scope.tenant_id, scope.workspace_id, scope.project_id):
                    continue
                if model:
                    out[symbol_id] = model
        return out

    def search(
        self,
        scope: Scope,
        vector: list[float],
        *,
        top_k: int = 5,
        kinds: Sequence[str] | None = None,
    ) -> list[tuple[str, float]]:
        from code_graph_service.domain.embeddings import cosine

        allowed = {str(k) for k in (kinds if kinds is not None else SEARCHABLE_SYMBOL_KINDS)}
        scored: list[tuple[str, float]] = []
        with self._lock:
            items = list(self._rows.items())
        for (tenant, workspace, project, symbol_id), (stored, _model, kind) in items:
            if (tenant, workspace, project) != (scope.tenant_id, scope.workspace_id, scope.project_id):
                continue
            if allowed and kind not in allowed:
                continue
            scored.append((symbol_id, cosine(vector, stored)))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return [(sid, score) for sid, score in scored[: max(1, top_k)] if score > 0]


class PostgresEmbeddingIndex:
    """pgvector-backed ANN index (cosine distance) for symbol embeddings."""

    def __init__(
        self,
        database_url: str,
        *,
        dims: int = 1024,
        ensure_schema: bool = True,
        max_connections: int | None = None,
    ) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Embedding index database URL must use PostgreSQL")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgresEmbeddingIndex") from exc
        from .pg_thread_local import resolve_pg_pool_max

        normalized = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self._dims = dims
        pool_max = (
            max(1, int(max_connections))
            if max_connections is not None
            else resolve_pg_pool_max(database_url=normalized)
        )
        self._pool = ThreadLocalPsycopg(
            lambda: psycopg.connect(normalized, autocommit=True, row_factory=dict_row),
            max_size=pool_max,
        )
        if ensure_schema:
            try:
                self.ensure_schema()
            except Exception:
                self._pool.close_all()
                raise

    @property
    def _connection(self) -> Any:
        return self._pool.get()

    def close(self) -> None:
        self._pool.close_all()

    def reset_connections(self) -> None:
        """Close worker connections; later calls reopen them lazily."""
        self._pool.close_all()

    def ensure_schema(self) -> None:
        migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
        with self._connection.cursor() as cur:
            for name in pg_sql.EMBEDDING_MIGRATION_FILES:
                path = migrations_dir / name
                if path.is_file():
                    cur.execute(path.read_text(encoding="utf-8"))
            cur.execute(pg_sql.SELECT_EMBEDDING_COLUMN_TYPE)
            row = cur.fetchone()
            expected = pg_sql.expected_vector_type(self._dims)
            if row and str(row.get("typ") or "") != expected:
                actual = str(row.get("typ") or "unknown")
                raise RuntimeError(
                    "embedding schema dimension mismatch: "
                    f"database has {actual}, configured provider requires {expected}; "
                    "run an explicit backed-up embedding migration or use the canonical dimension"
                )

    @staticmethod
    def _vector_literal(vector: list[float]) -> str:
        return "[" + ",".join(str(float(v)) for v in vector) + "]"

    def upsert(
        self,
        scope: Scope,
        symbol_id: str,
        vector: list[float],
        *,
        model: str,
        kind: str = "unknown",
    ) -> None:
        if len(vector) != self._dims:
            raise ValueError(f"embedding dims must be {self._dims}, got {len(vector)}")
        literal = self._vector_literal(vector)
        kind_value = str(kind or "unknown").strip() or "unknown"
        with self._connection.cursor() as cur:
            cur.execute(
                pg_sql.UPSERT_EMBEDDING,
                (
                    symbol_id,
                    scope.tenant_id,
                    scope.workspace_id,
                    scope.project_id,
                    model,
                    self._dims,
                    kind_value,
                    literal,
                ),
            )

    def delete(self, scope: Scope, symbol_id: str) -> None:
        with self._connection.cursor() as cur:
            cur.execute(
                pg_sql.DELETE_EMBEDDING,
                (symbol_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )

    def delete_many(self, scope: Scope, symbol_ids: list[str]) -> int:
        ids = [str(symbol_id) for symbol_id in symbol_ids if str(symbol_id)]
        if not ids:
            return 0
        with self._connection.cursor() as cur:
            cur.execute(
                pg_sql.DELETE_EMBEDDINGS,
                (ids, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return int(cur.rowcount or 0)

    def wipe_scope(self, scope: Scope) -> int:
        with self._connection.cursor() as cur:
            cur.execute(
                pg_sql.WIPE_EMBEDDINGS_SCOPE,
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return int(cur.rowcount or 0)

    def list_symbol_models(self, scope: Scope) -> dict[str, str]:
        """Return symbol_id → embedding model for one scope."""
        with self._connection.cursor() as cur:
            cur.execute(
                pg_sql.LIST_EMBEDDING_MODELS,
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            rows = cur.fetchall() or []
        out: dict[str, str] = {}
        for row in rows:
            sid = str(row.get("symbol_id") or "").strip()
            model = str(row.get("model") or "").strip()
            if sid and model:
                out[sid] = model
        return out

    def search(
        self,
        scope: Scope,
        vector: list[float],
        *,
        top_k: int = 5,
        kinds: Sequence[str] | None = None,
    ) -> list[tuple[str, float]]:
        from .pg_thread_local import is_transient_db_error

        try:
            return self._search_once(scope, vector, top_k=top_k, kinds=kinds)
        except Exception as exc:  # noqa: BLE001 — classify then maybe retry
            if not is_transient_db_error(exc):
                raise
            self.reset_connections()
            return self._search_once(scope, vector, top_k=top_k, kinds=kinds)

    def _search_once(
        self,
        scope: Scope,
        vector: list[float],
        *,
        top_k: int = 5,
        kinds: Sequence[str] | None = None,
    ) -> list[tuple[str, float]]:
        if len(vector) != self._dims:
            raise ValueError(f"query dims must be {self._dims}, got {len(vector)}")
        literal = self._vector_literal(vector)
        allowed = [str(k) for k in (kinds if kinds is not None else SEARCHABLE_SYMBOL_KINDS)]
        with self._connection.cursor() as cur:
            cur.execute(
                pg_sql.SEARCH_EMBEDDINGS,
                (
                    literal,
                    scope.tenant_id,
                    scope.workspace_id,
                    scope.project_id,
                    allowed,
                    literal,
                    max(1, top_k),
                ),
            )
            rows = cur.fetchall()
        return [(str(row["symbol_id"]), float(row["score"])) for row in rows if float(row["score"]) > 0]


class PostgresOutboxMirror:
    """Writes code-graph outbox rows so the Postgres outbox-relay can publish Neo4j events."""

    def __init__(self, database_url: str, *, max_connections: int | None = None) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Outbox mirror database URL must use PostgreSQL")
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgresOutboxMirror") from exc
        from .pg_thread_local import resolve_pg_pool_max

        normalized = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self._json = Jsonb
        pool_max = (
            max(1, int(max_connections))
            if max_connections is not None
            else resolve_pg_pool_max(database_url=normalized)
        )
        self._pool = ThreadLocalPsycopg(
            lambda: psycopg.connect(normalized, autocommit=True, row_factory=dict_row),
            max_size=pool_max,
        )

    @property
    def _connection(self) -> Any:
        return self._pool.get()

    def close(self) -> None:
        self._pool.close_all()

    def reset_connections(self) -> None:
        """Close worker connections; later calls reopen them lazily."""
        self._pool.close_all()

    def append_event(self, event: dict[str, Any]) -> None:
        with self._connection.cursor() as cur:
            cur.execute(
                pg_sql.APPEND_OUTBOX_EVENT,
                (event["event_id"], event["event_type"], self._json(event)),
            )
