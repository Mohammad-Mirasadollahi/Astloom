"""PostgreSQL Code Graph Store with bounded connection pool.

Role: persist symbols/edges/idempotency/outbox for the code-graph Store port.
Source of truth: ``code_graph.*`` tables; writers borrow from a sized ``psycopg``
pool (not shareable across threads while checked out).
Allowed: concurrent ingest writers under ``LockedStore`` slot budget; schema
ensure on construct. Forbidden: sharing one checked-out connection across
threads; retaining one idle client per worker thread.
"""

from __future__ import annotations

import json
from typing import Any

from .core import (
    ConflictError,
    DocStatus,
    GraphEdge,
    GraphSymbol,
    NotFoundError,
    Scope,
    SymbolKind,
)
from .domain.confidence_policy import parse_call_confidence
from .pg_thread_local import ThreadLocalPsycopg


def _timestamp(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


class PostgresStore:
    """PostgreSQL adapter for the Code Graph Store port (graph projection + outbox)."""

    def __init__(
        self,
        database_url: str,
        *,
        ensure_schema: bool = True,
        max_connections: int | None = None,
    ) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Code Graph database URL must use PostgreSQL")
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgreSQL persistence") from exc
        from .pg_thread_local import resolve_pg_pool_max

        normalized_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self._json = Jsonb
        pool_max = (
            max(1, int(max_connections))
            if max_connections is not None
            else resolve_pg_pool_max(database_url=normalized_url)
        )
        self._pool = ThreadLocalPsycopg(
            lambda: psycopg.connect(normalized_url, autocommit=True, row_factory=dict_row),
            max_size=pool_max,
        )
        if ensure_schema:
            self.ensure_schema()

    @property
    def _connection(self) -> Any:
        return self._pool.get()

    def close(self) -> None:
        self._pool.close_all()

    def reset_connections(self) -> None:
        """Close worker connections; later calls reopen them lazily."""
        self._pool.close_all()

    def ensure_schema(self) -> None:
        """Apply idempotent symbol-store migrations when present."""
        from pathlib import Path

        migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
        with self._connection.cursor() as cur:
            for name in (
                "0001_code_graph.sql",
                "0002_outbox_published.sql",
                "0006_symbol_fts.sql",
                "0007_symbol_language.sql",
                "0008_symbol_hash_versions.sql",
            ):
                path = migrations_dir / name
                if path.is_file():
                    cur.execute(path.read_text(encoding="utf-8"))

    def capabilities(self) -> dict[str, bool]:
        return {"apoc": False, "gds": False, "fulltext": True}

    def fulltext_search(
        self,
        scope: Scope,
        query: str,
        *,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Postgres FTS via tsvector / ts_rank_cd (english config)."""
        top_k = max(1, min(int(top_k), 100))
        q = (query or "").strip()
        if not q:
            return []
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT id AS symbol_id,
                       ts_rank_cd(
                         COALESCE(
                           search_document,
                           setweight(to_tsvector('english', coalesce(name, '')), 'A')
                           || setweight(to_tsvector('english', coalesce(qualified_name, '')), 'A')
                           || setweight(to_tsvector('english', coalesce(signature, '')), 'B')
                           || setweight(to_tsvector('english', coalesce(file_path, '')), 'B')
                           || setweight(to_tsvector('english', coalesce(ai_documentation, '')), 'C')
                         ),
                         plainto_tsquery('english', %s)
                       ) AS score
                FROM code_graph.symbols
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                  AND (
                    COALESCE(search_document,
                      setweight(to_tsvector('english', coalesce(name, '')), 'A')
                      || setweight(to_tsvector('english', coalesce(qualified_name, '')), 'A')
                      || setweight(to_tsvector('english', coalesce(signature, '')), 'B')
                      || setweight(to_tsvector('english', coalesce(file_path, '')), 'B')
                      || setweight(to_tsvector('english', coalesce(ai_documentation, '')), 'C')
                    ) @@ plainto_tsquery('english', %s)
                  )
                ORDER BY score DESC, id
                LIMIT %s
                """,
                (q, scope.tenant_id, scope.workspace_id, scope.project_id, q, top_k),
            )
            rows = cur.fetchall()
        return [
            {
                "symbol_id": row["symbol_id"],
                "score": float(row["score"] or 0.0),
                "method": "postgres.fts",
            }
            for row in rows
            if float(row["score"] or 0.0) > 0
        ]

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id, scope.project_group_id or ""))

    def _symbol(self, row: dict[str, Any], scope: Scope) -> GraphSymbol:
        metadata = row.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata or "{}")
        return GraphSymbol(
            id=row["id"],
            scope=scope,
            kind=SymbolKind(row["kind"]),
            file_path=row["file_path"],
            name=row["name"],
            qualified_name=row["qualified_name"],
            signature=row["signature"],
            body=row["body"],
            hash_value=row["hash_value"],
            ai_documentation=row["ai_documentation"],
            doc_status=DocStatus(row["doc_status"]),
            embedding=list(row["embedding"] or []),
            visibility=row["visibility"],
            version=row["version"],
            created_at=_timestamp(row["created_at"]),
            updated_at=_timestamp(row["updated_at"]),
            language=str(row.get("language") or ""),
            hash_version=str(row.get("hash_version") or ""),
            parser_version=str(row.get("parser_version") or ""),
            metadata=dict(metadata or {}),
        )

    def get_symbol(self, symbol_id: str, scope: Scope) -> GraphSymbol:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM code_graph.symbols
                WHERE id = %s AND tenant_id = %s AND workspace_id = %s AND project_id = %s
                """,
                (symbol_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cur.fetchone()
        if row is None:
            raise NotFoundError("symbol not found in project scope")
        return self._symbol(row, scope)

    def put_symbol(self, symbol: GraphSymbol) -> None:
        scope = symbol.scope
        with self._connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO code_graph.symbols (
                    id, tenant_id, workspace_id, project_id, project_group_id, kind, file_path, name,
                    qualified_name, signature, body, hash_value, ai_documentation, doc_status, embedding,
                    visibility, version, created_at, updated_at, language, hash_version, parser_version,
                    metadata
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )
                ON CONFLICT (id) DO UPDATE SET
                    kind = EXCLUDED.kind,
                    file_path = EXCLUDED.file_path,
                    name = EXCLUDED.name,
                    qualified_name = EXCLUDED.qualified_name,
                    signature = EXCLUDED.signature,
                    body = EXCLUDED.body,
                    hash_value = EXCLUDED.hash_value,
                    ai_documentation = EXCLUDED.ai_documentation,
                    doc_status = EXCLUDED.doc_status,
                    embedding = EXCLUDED.embedding,
                    visibility = EXCLUDED.visibility,
                    version = EXCLUDED.version,
                    updated_at = EXCLUDED.updated_at,
                    language = EXCLUDED.language,
                    hash_version = EXCLUDED.hash_version,
                    parser_version = EXCLUDED.parser_version,
                    metadata = EXCLUDED.metadata
                """,
                (
                    symbol.id,
                    scope.tenant_id,
                    scope.workspace_id,
                    scope.project_id,
                    scope.project_group_id,
                    symbol.kind.value,
                    symbol.file_path,
                    symbol.name,
                    symbol.qualified_name,
                    symbol.signature,
                    symbol.body,
                    symbol.hash_value,
                    symbol.ai_documentation,
                    symbol.doc_status.value,
                    self._json(symbol.embedding),
                    symbol.visibility,
                    symbol.version,
                    symbol.created_at,
                    symbol.updated_at,
                    symbol.language or "",
                    symbol.hash_version or "",
                    symbol.parser_version or "",
                    self._json(dict(symbol.metadata or {})),
                ),
            )
            # Refresh FTS document (column added by 0006_symbol_fts.sql).
            try:
                cur.execute(
                    """
                    UPDATE code_graph.symbols
                    SET search_document = (
                        setweight(to_tsvector('english', coalesce(name, '')), 'A')
                        || setweight(to_tsvector('english', coalesce(qualified_name, '')), 'A')
                        || setweight(to_tsvector('english', coalesce(signature, '')), 'B')
                        || setweight(to_tsvector('english', coalesce(file_path, '')), 'B')
                        || setweight(to_tsvector('english', coalesce(ai_documentation, '')), 'C')
                        || setweight(to_tsvector('english', left(coalesce(body, ''), 2000)), 'D')
                    )
                    WHERE id = %s
                    """,
                    (symbol.id,),
                )
            except Exception:
                pass

    def delete_symbol(self, symbol_id: str, scope: Scope) -> None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                DELETE FROM code_graph.symbols
                WHERE id = %s
                  AND tenant_id = %s
                  AND workspace_id = %s
                  AND project_id = %s
                """,
                (symbol_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )

    def list_symbols(self, scope: Scope) -> list[GraphSymbol]:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM code_graph.symbols
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                ORDER BY qualified_name, id
                """,
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            rows = cur.fetchall()
        return [self._symbol(row, scope) for row in rows]

    def list_symbols_lean(self, scope: Scope) -> list[GraphSymbol]:
        symbols = self.list_symbols(scope)
        for sym in symbols:
            sym.ai_documentation = ""
        return symbols

    def list_symbols_index(self, scope: Scope) -> list[GraphSymbol]:
        symbols = self.list_symbols(scope)
        for sym in symbols:
            sym.ai_documentation = ""
            sym.body = ""
            sym.embedding = []
            sym.metadata = {}
        return symbols

    def list_file_symbols_for_paths(self, scope: Scope, paths: list[str]) -> list[GraphSymbol]:
        from .domain.enums import SymbolKind

        wanted = {str(p or "").replace("\\", "/").strip() for p in paths if str(p or "").strip()}
        if not wanted:
            return []
        out: list[GraphSymbol] = []
        for path in wanted:
            with self._connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM code_graph.symbols
                    WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                      AND kind = 'file' AND file_path = %s
                    """,
                    (scope.tenant_id, scope.workspace_id, scope.project_id, path),
                )
                rows = cur.fetchall()
            out.extend(self._symbol(row, scope) for row in rows)
        return out

    def has_any_symbol(self, scope: Scope) -> bool:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM code_graph.symbols
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                LIMIT 1
                """,
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return cur.fetchone() is not None

    def list_file_symbols_index(self, scope: Scope) -> list[GraphSymbol]:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM code_graph.symbols
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                  AND kind = 'file'
                ORDER BY file_path, id
                """,
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            rows = cur.fetchall()
        return [self._symbol(row, scope) for row in rows]

    def list_symbols_for_file(self, scope: Scope, file_path: str) -> list[GraphSymbol]:
        path = str(file_path or "").replace("\\", "/")
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM code_graph.symbols
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                  AND file_path = %s
                ORDER BY qualified_name, id
                """,
                (scope.tenant_id, scope.workspace_id, scope.project_id, path),
            )
            rows = cur.fetchall()
        return [self._symbol(row, scope) for row in rows]

    def get_symbol_by_qualified_name(self, scope: Scope, qualified_name: str) -> GraphSymbol | None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM code_graph.symbols
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                  AND (qualified_name = %s OR name = %s)
                ORDER BY CASE WHEN qualified_name = %s THEN 0 ELSE 1 END, id
                LIMIT 1
                """,
                (
                    scope.tenant_id,
                    scope.workspace_id,
                    scope.project_id,
                    qualified_name,
                    qualified_name,
                    qualified_name,
                ),
            )
            row = cur.fetchone()
        return None if row is None else self._symbol(row, scope)

    def delete_file_edges(self, scope: Scope, file_path: str) -> None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                DELETE FROM code_graph.edges
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                  AND metadata->>'file_path' = %s
                """,
                (scope.tenant_id, scope.workspace_id, scope.project_id, file_path),
            )

    def delete_edge(self, scope: Scope, edge_id: str) -> None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                DELETE FROM code_graph.edges
                WHERE id = %s AND tenant_id = %s AND workspace_id = %s AND project_id = %s
                """,
                (edge_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )

    def delete_edges(self, scope: Scope, edge_ids: list[str]) -> None:
        ids = [str(edge_id) for edge_id in edge_ids if str(edge_id or "").strip()]
        if not ids:
            return
        with self._connection.cursor() as cur:
            cur.execute(
                """
                DELETE FROM code_graph.edges
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                  AND id = ANY(%s)
                """,
                (scope.tenant_id, scope.workspace_id, scope.project_id, ids),
            )

    def put_edge(self, edge: GraphEdge) -> None:
        scope = edge.scope
        with self._connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO code_graph.edges (
                    id, tenant_id, workspace_id, project_id, project_group_id, rel_type, source_id,
                    target_id, confidence, metadata
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    rel_type = EXCLUDED.rel_type,
                    source_id = EXCLUDED.source_id,
                    target_id = EXCLUDED.target_id,
                    confidence = EXCLUDED.confidence,
                    metadata = EXCLUDED.metadata
                """,
                (
                    edge.id,
                    scope.tenant_id,
                    scope.workspace_id,
                    scope.project_id,
                    scope.project_group_id,
                    edge.rel_type,
                    edge.source_id,
                    edge.target_id,
                    parse_call_confidence(edge.confidence).value,
                    self._json(edge.metadata),
                ),
            )

    def list_edges(
        self,
        scope: Scope,
        *,
        rel_type: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
        target_id_prefixes: list[str] | None = None,
    ) -> list[GraphEdge]:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM code_graph.edges
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                  AND (%s::text IS NULL OR rel_type = %s)
                  AND (%s::text IS NULL OR source_id = %s)
                  AND (%s::text IS NULL OR target_id = %s)
                ORDER BY id
                """,
                (
                    scope.tenant_id,
                    scope.workspace_id,
                    scope.project_id,
                    rel_type,
                    rel_type,
                    source_id,
                    source_id,
                    target_id,
                    target_id,
                ),
            )
            rows = cur.fetchall()
        prefixes = tuple(target_id_prefixes or ())
        edges = [
            GraphEdge(
                id=row["id"],
                scope=scope,
                rel_type=row["rel_type"],
                source_id=row["source_id"],
                target_id=row["target_id"],
                confidence=parse_call_confidence(row["confidence"]),
                metadata=dict(row["metadata"] or {}),
            )
            for row in rows
        ]
        if not prefixes:
            return edges
        return [
            edge
            for edge in edges
            if any(str(edge.target_id).startswith(p) for p in prefixes)
        ]

    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT resource_id FROM code_graph.idempotency
                WHERE scope_key = %s AND idempotency_key = %s AND resource_type = %s
                """,
                (self._scope_key(scope), key, resource),
            )
            row = cur.fetchone()
        return None if row is None else row["resource_id"]

    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO code_graph.idempotency (scope_key, idempotency_key, resource_type, resource_id)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (scope_key, idempotency_key, resource_type) DO UPDATE
                SET resource_id = EXCLUDED.resource_id
                RETURNING resource_id
                """,
                (self._scope_key(scope), key, resource, resource_id),
            )
            row = cur.fetchone()
        if row and row["resource_id"] != resource_id:
            raise ConflictError("idempotency key already bound to another resource")

    def append_event(self, event: dict[str, Any]) -> None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO code_graph.outbox (event_id, event_type, payload)
                VALUES (%s,%s,%s)
                """,
                (event["event_id"], event["event_type"], self._json(event)),
            )

    def outbox(self) -> list[dict[str, Any]]:
        with self._connection.cursor() as cur:
            cur.execute("SELECT payload FROM code_graph.outbox ORDER BY created_at, event_id")
            rows = cur.fetchall()
        return [dict(row["payload"]) if isinstance(row["payload"], dict) else json.loads(row["payload"]) for row in rows]

    def wipe_scope(self, scope: Scope) -> dict[str, int]:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                DELETE FROM code_graph.edges
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                """,
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            edges = int(cur.rowcount or 0)
            cur.execute(
                """
                DELETE FROM code_graph.symbols
                WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
                """,
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            symbols = int(cur.rowcount or 0)
            cur.execute(
                "DELETE FROM code_graph.idempotency WHERE scope_key = %s",
                (self._scope_key(scope),),
            )
            idem = int(cur.rowcount or 0)
        return {"symbols": symbols, "edges": edges, "idempotency": idem}
