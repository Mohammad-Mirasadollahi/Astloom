"""Unit tests for per-thread Postgres connections."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from code_graph_service.pg_thread_local import ThreadLocalPsycopg, resolve_pg_pool_max
from code_graph_service.testing import InMemoryStore
from code_graph_service.core import Scope
from code_graph_service.domain.models import GraphSymbol
from code_graph_service.domain.enums import DocStatus, SymbolKind


SCOPE = Scope("t", "w", "p")


def test_resolve_pg_pool_max_default_is_uncapped_without_url():
    assert resolve_pg_pool_max({}) is None
    assert resolve_pg_pool_max({"ASTLOOM_PG_POOL_MAX": "auto"}) is None
    assert resolve_pg_pool_max({"ASTLOOM_PG_POOL_MAX": "none"}) is None
    assert resolve_pg_pool_max({"ASTLOOM_PG_POOL_MAX": "unlimited"}) is None


def test_resolve_pg_pool_max_explicit_override():
    assert resolve_pg_pool_max({"ASTLOOM_PG_POOL_MAX": "12"}) == 12


def test_resolve_pg_pool_max_auto_from_server_capacity(monkeypatch):
    class _Cur:
        def __init__(self) -> None:
            self._n = 0

        def execute(self, sql: str) -> None:
            self._sql = sql

        def fetchone(self):
            if "max_connections" in self._sql:
                return ("100",)
            return (20,)

        def __enter__(self) -> "_Cur":
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

    class _Conn:
        def cursor(self) -> _Cur:
            return _Cur()

        def __enter__(self) -> "_Conn":
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def close(self) -> None:
            return None

    class _Psycopg:
        @staticmethod
        def connect(*_a: object, **_k: object) -> _Conn:
            return _Conn()

    import code_graph_service.pg_thread_local as mod

    monkeypatch.setitem(__import__("sys").modules, "psycopg", _Psycopg)
    # free = 100 - 20 - max(15, 20) = 60; share 3 → 20
    assert resolve_pg_pool_max({"ASTLOOM_PG_POOL_MAX": "auto"}, database_url="postgresql://x") == 20


def test_thread_local_default_max_size_is_uncapped():
    created: list[_Conn] = []
    lock = threading.Lock()

    def connect() -> _Conn:
        conn = _Conn()
        with lock:
            created.append(conn)
        return conn

    pool = ThreadLocalPsycopg(connect)
    assert pool._max_size is None
    all_held = threading.Barrier(7)  # 6 workers + main
    release_gate = threading.Event()
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            pool.get()
            all_held.wait(timeout=5)
            assert release_gate.wait(timeout=5)
            pool.release()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    all_held.wait(timeout=5)
    assert len(created) == 6
    release_gate.set()
    for t in threads:
        t.join()
    assert errors == []
    pool.close_all()


class _Cursor:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        return None

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def close(self) -> None:
        return None


class _Conn:
    def __init__(self) -> None:
        self.closed = False

    def cursor(self, *_args: object, **_kwargs: object) -> _Cursor:
        return _Cursor()

    def close(self) -> None:
        self.closed = True


def test_thread_local_get_replaces_closed_connection():
    created: list[_Conn] = []

    def connect() -> _Conn:
        conn = _Conn()
        created.append(conn)
        return conn

    pool = ThreadLocalPsycopg(connect, max_size=None)
    first = pool.get()
    first.unwrap().closed = True
    pool.release()
    second = pool.get()
    assert second.unwrap() is not first.unwrap()
    assert len(created) == 2
    pool.release()
    pool.close_all()


def test_thread_local_drop_forces_new_connection():
    created: list[_Conn] = []

    def connect() -> _Conn:
        conn = _Conn()
        created.append(conn)
        return conn

    pool = ThreadLocalPsycopg(connect, max_size=None)
    first = pool.get()
    pool.drop()
    assert first.unwrap().closed is True
    second = pool.get()
    assert second.unwrap() is not first.unwrap()
    assert len(created) == 2
    pool.release()
    pool.close_all()


def test_is_db_capacity_error_detects_too_many_clients():
    from code_graph_service.pg_thread_local import is_db_capacity_error

    assert is_db_capacity_error(RuntimeError("FATAL: sorry, too many clients already"))
    assert is_db_capacity_error(RuntimeError("remaining connection slots are reserved"))
    assert not is_db_capacity_error(RuntimeError("connection refused"))


def test_checkout_raises_database_capacity_error_after_retries(monkeypatch):
    from code_graph_service.domain.errors import DatabaseCapacityError
    from code_graph_service.pg_thread_local import ThreadLocalPsycopg

    monkeypatch.setenv("ASTLOOM_PG_CAPACITY_RETRIES", "2")

    def connect() -> _Conn:
        raise RuntimeError("connection failed: FATAL: sorry, too many clients already")

    pool = ThreadLocalPsycopg(connect, max_size=None)
    try:
        pool.get()
        raise AssertionError("expected DatabaseCapacityError")
    except DatabaseCapacityError as exc:
        assert exc.code == "database_capacity"
        assert "too many clients" in exc.message.lower() or "client slots" in exc.message.lower()
    pool.close_all()


def test_checkout_retries_then_succeeds_when_capacity_clears(monkeypatch):
    from code_graph_service.pg_thread_local import ThreadLocalPsycopg

    monkeypatch.setenv("ASTLOOM_PG_CAPACITY_RETRIES", "4")
    calls = {"n": 0}

    def connect() -> _Conn:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("FATAL: sorry, too many clients already")
        return _Conn()

    pool = ThreadLocalPsycopg(connect, max_size=None)
    managed = pool.get()
    assert isinstance(managed.unwrap(), _Conn)
    pool.release()
    pool.close_all()
    assert calls["n"] == 3


def test_unbounded_pool_allows_parallel_held_connections():
    created: list[_Conn] = []
    lock = threading.Lock()

    def connect() -> _Conn:
        conn = _Conn()
        with lock:
            created.append(conn)
        return conn

    pool = ThreadLocalPsycopg(connect, max_size=None)
    seen: dict[int, int] = {}
    all_held = threading.Barrier(5)  # 4 workers + main
    release_gate = threading.Event()
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            managed = pool.get()
            seen[threading.get_ident()] = id(managed.unwrap())
            all_held.wait(timeout=5)
            assert release_gate.wait(timeout=5)
            pool.release()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    all_held.wait(timeout=5)
    assert len(seen) == 4
    assert len(set(seen.values())) == 4
    assert len(created) == 4
    release_gate.set()
    for t in threads:
        t.join()
    assert errors == []
    pool.close_all()
    assert all(c.closed for c in created)


def test_bounded_pool_never_exceeds_max_size_under_parallel_workers():
    """Regression: parallel sync must not open one idle PG client per worker forever."""
    created: list[_Conn] = []
    lock = threading.Lock()
    peak_live = 0

    def connect() -> _Conn:
        nonlocal peak_live
        conn = _Conn()
        with lock:
            created.append(conn)
            live = sum(1 for c in created if not c.closed)
            peak_live = max(peak_live, live)
        return conn

    pool = ThreadLocalPsycopg(connect, max_size=2)
    errors: list[BaseException] = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        try:
            barrier.wait(timeout=5)
            for _ in range(3):
                managed = pool.get()
                with managed.cursor() as cur:
                    cur.execute("select 1")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert errors == []
    assert peak_live <= 2
    assert pool.live_count() <= 2
    pool.close_all()
    assert pool.live_count() == 0
    assert all(c.closed for c in created)


def test_bounded_pool_reuses_idle_connections_across_threads():
    created: list[_Conn] = []

    def connect() -> _Conn:
        conn = _Conn()
        created.append(conn)
        return conn

    pool = ThreadLocalPsycopg(connect, max_size=1)
    first = pool.get()
    with first.cursor():
        pass
    assert len(created) == 1
    second = pool.get()
    with second.cursor():
        pass
    assert len(created) == 1
    assert first.unwrap() is second.unwrap()
    pool.close_all()


def test_inmemory_store_put_symbol_safe_under_threads():
    store = InMemoryStore()
    errors: list[BaseException] = []

    def _write(i: int) -> None:
        try:
            store.put_symbol(
                GraphSymbol(
                    id=f"s{i}",
                    scope=SCOPE,
                    kind=SymbolKind.FUNCTION,
                    file_path=f"f{i}.py",
                    name=f"f{i}",
                    qualified_name=f"mod.f{i}",
                    signature=f"def f{i}()",
                    body="",
                    hash_value=f"h{i}",
                    ai_documentation="",
                    doc_status=DocStatus.MISSING,
                    embedding=[],
                )
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_write, range(40)))
    assert errors == []
    assert len(store.list_symbols(SCOPE)) == 40
