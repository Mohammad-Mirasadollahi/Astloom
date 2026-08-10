"""PostgreSQL memory embeddings SoR (GAP-T03).

Role: durable pgvector rows for memory-service Stage-1 retrieve.
SoT: ``memory.memory_embeddings`` (+ optional ``memory.embedding_id_map``).
Allowed: ensure_schema for 0003/0004; cosine search via pgvector.
Forbidden: writing TurboVec as SoR; cross-tenant search.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .domain.embeddings_store import MemoryEmbeddingRow

MIGRATION_FILES = (
    "0003_memory_embeddings.sql",
    "0004_embedding_id_map.sql",
)


class PostgresMemoryEmbeddingStore:
    """pgvector-backed MemoryEmbeddingStore."""

    def __init__(
        self,
        database_url: str,
        *,
        dims: int = 1024,
        ensure_schema: bool = True,
    ) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Memory embedding store requires a PostgreSQL URL")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgresMemoryEmbeddingStore") from exc
        normalized = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self._dims = int(dims)
        self._connection = psycopg.connect(normalized, autocommit=True, row_factory=dict_row)
        if ensure_schema:
            self.ensure_schema()

    def close(self) -> None:
        self._connection.close()

    def ensure_schema(self) -> None:
        migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
        with self._connection.cursor() as cur:
            for name in MIGRATION_FILES:
                path = migrations_dir / name
                if path.is_file():
                    cur.execute(path.read_text(encoding="utf-8"))

    @staticmethod
    def _vector_literal(vector: Sequence[float]) -> str:
        return "[" + ",".join(str(float(v)) for v in vector) + "]"

    def upsert(self, row: MemoryEmbeddingRow) -> None:
        if len(row.vector) != self._dims:
            raise ValueError(f"embedding dims must be {self._dims}, got {len(row.vector)}")
        literal = self._vector_literal(row.vector)
        with self._connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory.memory_embeddings
                    (memory_id, tenant_id, workspace_id, project_id, model, dims, embedding, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector, now())
                ON CONFLICT (memory_id) DO UPDATE SET
                    model = EXCLUDED.model,
                    dims = EXCLUDED.dims,
                    embedding = EXCLUDED.embedding,
                    updated_at = now()
                """,
                (
                    row.memory_id,
                    row.tenant_id,
                    row.workspace_id,
                    row.project_id,
                    row.model,
                    row.dims,
                    literal,
                ),
            )

    def delete(self, scope: Any, memory_id: str) -> None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                DELETE FROM memory.memory_embeddings
                WHERE memory_id = %s AND tenant_id = %s AND workspace_id = %s AND project_id = %s
                """,
                (memory_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )

    def get_vector(self, scope: Any, memory_id: str) -> list[float] | None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT embedding::text AS embedding
                FROM memory.memory_embeddings
                WHERE memory_id = %s AND tenant_id = %s AND workspace_id = %s AND project_id = %s
                """,
                (memory_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        raw = str(row["embedding"]).strip("[]")
        if not raw:
            return []
        return [float(x) for x in raw.split(",")]

    def list_models(self, scope: Any) -> dict[str, str]:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT memory_id, model
                FROM memory.memory_embeddings
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                """,
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            rows = cur.fetchall()
        return {str(r["memory_id"]): str(r["model"]) for r in rows}

    def search(
        self,
        scope: Any,
        vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        if len(vector) != self._dims:
            raise ValueError(f"query dims must be {self._dims}, got {len(vector)}")
        literal = self._vector_literal(vector)
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT memory_id,
                       1 - (embedding <=> %s::vector) AS score
                FROM memory.memory_embeddings
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (
                    literal,
                    scope.tenant_id,
                    scope.workspace_id,
                    scope.project_id,
                    literal,
                    max(1, int(top_k)),
                ),
            )
            rows = cur.fetchall()
        return [(str(r["memory_id"]), float(r["score"])) for r in rows if float(r["score"]) > 0]
