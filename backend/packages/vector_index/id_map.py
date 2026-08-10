"""entity_ref → uint64 mapping for VectorIndexPort external ids.

Role: Deterministic durable id bridge between Astloom string/UUID refs and turbovec uint64 ids.
Source of truth: Prefer service-owned ``embedding_id_map`` table (SQL snippet below); in-memory map for tests.
Allowed: stable hash only when reverse lookup is also retained for the request path.
Forbidden: positional slot ids; silent collisions without a documented map.
"""

from __future__ import annotations

import hashlib
import threading
from typing import Iterable

# Services copy/adapt this into their schema. Keep BIGINT UNIQUE for turbovec uint64.
ENTITY_ID_MAP_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS embedding_id_map (
    entity_ref   TEXT        PRIMARY KEY,
    uint64_id    BIGINT      NOT NULL UNIQUE,
    tenant_id    TEXT        NOT NULL,
    workspace_id TEXT        NOT NULL,
    project_id   TEXT        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS embedding_id_map_scope_idx
    ON embedding_id_map (tenant_id, workspace_id, project_id);
CREATE INDEX IF NOT EXISTS embedding_id_map_uint64_idx
    ON embedding_id_map (uint64_id);
""".strip()


def stable_hash_uint64(entity_ref: str) -> int:
    """Deterministic uint64 from entity_ref (SHA-256 prefix).

    Collision policy: cryptographic birthday risk only; services that cannot tolerate
    collisions MUST allocate via a durable table (see ENTITY_ID_MAP_TABLE_SQL).
    """
    digest = hashlib.sha256(entity_ref.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big", signed=False)


def entity_ref_to_uint64(entity_ref: str, *, namespace: str = "") -> int:
    """Map entity_ref to uint64; optional namespace scopes ids per tenant/project."""
    key = f"{namespace}:{entity_ref}" if namespace else str(entity_ref)
    return stable_hash_uint64(key)


class InMemoryEntityIdMap:
    """Process-local bidirectional map for tests and sync_on_write replicas."""

    def __init__(self, *, use_stable_hash: bool = True) -> None:
        self._use_stable_hash = use_stable_hash
        self._fwd: dict[str, int] = {}
        self._rev: dict[int, str] = {}
        self._next = 1
        self._lock = threading.RLock()

    def get_or_assign(self, entity_ref: str) -> int:
        key = str(entity_ref)
        with self._lock:
            existing = self._fwd.get(key)
            if existing is not None:
                return existing
            uid = stable_hash_uint64(key) if self._use_stable_hash else self._alloc()
            # Extremely rare hash collision: fall back to sequential allocate.
            if uid in self._rev and self._rev[uid] != key:
                uid = self._alloc()
            self._fwd[key] = uid
            self._rev[uid] = key
            return uid

    def to_uint64(self, entity_ref: str) -> int | None:
        with self._lock:
            return self._fwd.get(str(entity_ref))

    def to_entity_ref(self, uid: int) -> str | None:
        with self._lock:
            return self._rev.get(int(uid))

    def remove(self, entity_ref: str) -> bool:
        key = str(entity_ref)
        with self._lock:
            uid = self._fwd.pop(key, None)
            if uid is None:
                return False
            self._rev.pop(uid, None)
            return True

    def map_many(self, entity_refs: Iterable[str]) -> list[int]:
        return [self.get_or_assign(ref) for ref in entity_refs]

    def _alloc(self) -> int:
        while self._next in self._rev:
            self._next += 1
        uid = self._next
        self._next += 1
        return uid


class PostgresEntityIdMap:
    """Durable entity_ref → uint64 map backed by service ``embedding_id_map`` table.

    Prefer this over process-local maps when PostgreSQL is available. Collision on
    ``uint64_id`` UNIQUE falls back to sequential allocation (same policy as in-memory).
    """

    def __init__(
        self,
        database_url: str,
        *,
        table: str = "embedding_id_map",
        ensure_schema: bool = False,
        schema_sql: str | None = None,
    ) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("PostgresEntityIdMap requires a PostgreSQL URL")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgresEntityIdMap") from exc
        normalized = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        if not _safe_table_name(table):
            raise ValueError(f"unsafe id-map table name: {table!r}")
        self._table = table
        self._connection = psycopg.connect(normalized, autocommit=True, row_factory=dict_row)
        self._lock = threading.RLock()
        self._fwd: dict[str, int] = {}
        self._rev: dict[int, str] = {}
        self._next = 1
        if ensure_schema:
            ddl = schema_sql or ENTITY_ID_MAP_TABLE_SQL
            # Allow schema-qualified table by rewriting bare CREATE when needed.
            if "." in table and "CREATE TABLE IF NOT EXISTS embedding_id_map" in ddl:
                bare, qualified = "embedding_id_map", table
                ddl = ddl.replace(f" {bare} ", f" {qualified} ").replace(
                    f" {bare}(", f" {qualified}("
                )
                ddl = ddl.replace(f" ON {bare} ", f" ON {qualified} ")
            with self._connection.cursor() as cur:
                cur.execute(ddl)

    def close(self) -> None:
        self._connection.close()

    def get_or_assign(self, entity_ref: str) -> int:
        key = str(entity_ref)
        with self._lock:
            cached = self._fwd.get(key)
            if cached is not None:
                return cached
            uid = self._load(key)
            if uid is not None:
                self._fwd[key] = uid
                self._rev[uid] = key
                return uid
            uid = stable_hash_uint64(key)
            if self._rev.get(uid) not in (None, key) or self._uid_taken(uid):
                uid = self._alloc_db()
            self._insert(key, uid)
            self._fwd[key] = uid
            self._rev[uid] = key
            return uid

    def to_uint64(self, entity_ref: str) -> int | None:
        key = str(entity_ref)
        with self._lock:
            if key in self._fwd:
                return self._fwd[key]
            uid = self._load(key)
            if uid is not None:
                self._fwd[key] = uid
                self._rev[uid] = key
            return uid

    def to_entity_ref(self, uid: int) -> str | None:
        with self._lock:
            if int(uid) in self._rev:
                return self._rev[int(uid)]
            with self._connection.cursor() as cur:
                cur.execute(
                    f"SELECT entity_ref FROM {self._table} WHERE uint64_id = %s",
                    (int(uid),),
                )
                row = cur.fetchone()
            if row is None:
                return None
            key = str(row["entity_ref"])
            self._fwd[key] = int(uid)
            self._rev[int(uid)] = key
            return key

    def remove(self, entity_ref: str) -> bool:
        key = str(entity_ref)
        with self._lock:
            with self._connection.cursor() as cur:
                cur.execute(f"DELETE FROM {self._table} WHERE entity_ref = %s", (key,))
                deleted = cur.rowcount > 0
            uid = self._fwd.pop(key, None)
            if uid is not None:
                self._rev.pop(uid, None)
            return deleted

    def map_many(self, entity_refs: Iterable[str]) -> list[int]:
        return [self.get_or_assign(ref) for ref in entity_refs]

    def _load(self, key: str) -> int | None:
        with self._connection.cursor() as cur:
            cur.execute(
                f"SELECT uint64_id FROM {self._table} WHERE entity_ref = %s",
                (key,),
            )
            row = cur.fetchone()
        return int(row["uint64_id"]) if row else None

    def _uid_taken(self, uid: int) -> bool:
        with self._connection.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {self._table} WHERE uint64_id = %s LIMIT 1",
                (int(uid),),
            )
            return cur.fetchone() is not None

    def _insert(self, key: str, uid: int) -> None:
        with self._connection.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self._table}
                    (entity_ref, uint64_id, tenant_id, workspace_id, project_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (entity_ref) DO NOTHING
                """,
                (key, int(uid), "", "", ""),
            )

    def _alloc_db(self) -> int:
        while True:
            uid = self._next
            self._next += 1
            if not self._uid_taken(uid):
                return uid


def _safe_table_name(table: str) -> bool:
    """Allow schema.table or bare table with [A-Za-z_][A-Za-z0-9_]*."""
    parts = table.split(".")
    if not parts or len(parts) > 2:
        return False
    return all(p.isidentifier() for p in parts)
