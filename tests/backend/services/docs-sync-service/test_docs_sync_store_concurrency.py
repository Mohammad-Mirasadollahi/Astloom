"""Unit tests for thread-safe docs-sync store adapters."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from docs_sync_service.core import Document, DocumentState, Scope
from docs_sync_service.postgres_store import PostgresStore
from docs_sync_service.testing import InMemoryStore

SCOPE = Scope("t", "w", "p")


def _doc(doc_id: str) -> Document:
    return Document(
        doc_id,
        SCOPE,
        "actor",
        "corr",
        f"docs/{doc_id}.md",
        doc_id,
        "platform",
        DocumentState.INDEXED,
        "1.0.0",
        [],
        [],
        {"doc_id": doc_id},
        "body",
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00Z",
        1,
    )


def test_inmemory_store_put_document_is_safe_under_threads():
    store = InMemoryStore()
    errors: list[BaseException] = []

    def _write(i: int) -> None:
        try:
            store.put_document(_doc(f"d{i}"))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_write, range(40)))
    assert errors == []
    assert len(store.list_documents(SCOPE)) == 40


def test_inmemory_store_keeps_same_document_id_isolated_by_scope():
    store = InMemoryStore()
    other_scope = Scope("t", "w", "other-project")
    first = _doc("shared-doc")
    second = _doc("shared-doc")
    second.scope = other_scope

    store.put_document(first)
    store.put_document(second)

    assert store.get_document("shared-doc", SCOPE).scope == SCOPE
    assert store.get_document("shared-doc", other_scope).scope == other_scope


def test_postgres_store_uses_per_thread_connections():
    """Concurrent holds must not share one live connection across threads."""
    from docs_sync_service.pg_thread_local import ThreadLocalPsycopg

    created: list[object] = []
    lock = threading.Lock()
    errors: list[BaseException] = []

    class _Conn:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def cursor(self):
            raise AssertionError("cursor not used in this unit test")

    def fake_connect():
        conn = _Conn()
        with lock:
            created.append(conn)
        return conn

    store = PostgresStore.__new__(PostgresStore)
    store._json = object()
    store._pool = ThreadLocalPsycopg(fake_connect, max_size=8)

    seen: dict[int, int] = {}
    start = threading.Barrier(4)
    held = threading.Barrier(4)

    def worker() -> None:
        try:
            start.wait(timeout=5)
            conn = store._connection
            seen[threading.get_ident()] = id(conn.unwrap())
            # Stay checked-out until every worker has a live hold.
            held.wait(timeout=5)
            store._pool.release()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(seen) == 4
    assert len(set(seen.values())) == 4
    assert len(created) == 4
    store.close()
    assert all(c.closed for c in created)
