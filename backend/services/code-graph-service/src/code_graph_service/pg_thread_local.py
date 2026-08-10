"""Checkout/checkin ``psycopg`` pool for parallel store writers.

Role: lend one connection per in-flight DB operation without retaining an idle
client per worker thread forever.
Source of truth: caller connect factory; optional ``max_size`` (explicit or
auto from server capacity) caps live clients only when needed.
Allowed: re-entrant checkout on one thread; return to idle on cursor exit /
``release``; close-all on shutdown; drop/retry after server disconnect.
Forbidden: sharing one checked-out connection across threads; leaking one idle
client per ThreadPool worker (exhausts Postgres ``max_connections``).
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import Any

_TRANSIENT_MARKERS = (
    "adminshutdown",
    "connectiondoesnotexist",
    "defunct connection",
    "server closed the connection",
    "connection not open",
    "ssl connection has been closed",
    "terminating connection due to administrator command",
    "connection refused",
    "could not connect to server",
)

# How many independent PG pools this process may open (embedding / outbox / docs…).
_DEFAULT_POOL_SHARE = 3
# Keep room for other Astloom processes + superuser when auto-sizing.
_DEFAULT_RESERVE_FLOOR = 15


def _probe_server_pool_max(database_url: str, *, pool_share: int) -> int | None:
    """Derive a soft per-pool cap from live Postgres capacity; None if probe fails."""
    try:
        import psycopg
    except ImportError:
        return None
    url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SHOW max_connections")
                max_conn = int((cur.fetchone() or [0])[0] or 0)
                cur.execute("SELECT count(*)::int FROM pg_stat_activity")
                used = int((cur.fetchone() or [0])[0] or 0)
    except Exception:  # noqa: BLE001 — auto mode must not block store construction
        return None
    if max_conn < 1:
        return None
    reserve = max(_DEFAULT_RESERVE_FLOOR, max_conn // 5)
    free = max_conn - used - reserve
    if free < 1:
        # Server already tight: keep a tiny pool so work proceeds without stampede.
        return 2
    share = max(1, int(pool_share))
    return max(2, free // share)


def resolve_pg_pool_max(
    environ: dict[str, str] | None = None,
    *,
    database_url: str | None = None,
) -> int | None:
    """Resolve per-pool live connection cap.

    - unset / ``auto``: probe Postgres when ``database_url`` is set; else no cap
      (checkout/checkin alone prevents per-worker leaks; concurrency comes from
      workers / ``LockedStore``).
    - ``none`` / ``unlimited`` / ``off``: no cap
    - positive int (``ASTLOOM_PG_POOL_MAX``): explicit override
    """
    env = environ if environ is not None else os.environ
    raw = str(env.get("ASTLOOM_PG_POOL_MAX", "") or "").strip().lower()
    if raw in {"none", "unlimited", "off"}:
        return None
    if raw and raw not in {"auto", "0"}:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    share_raw = str(env.get("ASTLOOM_PG_POOL_SHARE", "") or "").strip()
    try:
        pool_share = max(1, int(share_raw)) if share_raw else _DEFAULT_POOL_SHARE
    except ValueError:
        pool_share = _DEFAULT_POOL_SHARE
    if database_url:
        return _probe_server_pool_max(database_url, pool_share=pool_share)
    return None


def is_db_capacity_error(exc: BaseException) -> bool:
    """True when Postgres refused a new client (slot exhaustion)."""
    blob = f"{type(exc).__name__}:{exc}".lower()
    return (
        "too many clients" in blob
        or "remaining connection slots are reserved" in blob
        or "connection limit exceeded" in blob
    )


def is_transient_db_error(exc: BaseException) -> bool:
    """True for dead/restarted Postgres (or similar) transport failures worth one retry."""
    if is_db_capacity_error(exc):
        # Capacity is retryable at the pool layer, but not a "dead connection" reset.
        return False
    name = type(exc).__name__
    blob = f"{name}:{exc}".lower()
    if name in {"AdminShutdown", "InterfaceError", "ServiceUnavailable"}:
        return True
    if name in {"OperationalError", "DatabaseError"} and any(m in blob for m in _TRANSIENT_MARKERS):
        return True
    return any(m in blob for m in _TRANSIENT_MARKERS)


def _capacity_error_type() -> type[Exception]:
    try:
        from .domain.errors import DatabaseCapacityError
    except ImportError:  # pragma: no cover — docs-sync vendored copy
        from code_graph_service.domain.errors import DatabaseCapacityError  # type: ignore

    return DatabaseCapacityError



class _PooledCursor:
    """Cursor that returns the connection to the pool when the ``with`` block ends."""

    def __init__(self, pool: "ThreadLocalPsycopg", cursor: Any) -> None:
        self._pool = pool
        self._cursor = cursor
        self._released = False

    def __enter__(self) -> Any:
        enter = getattr(self._cursor, "__enter__", None)
        if callable(enter):
            enter()
        return self

    def __exit__(self, *exc: Any) -> Any:
        try:
            leave = getattr(self._cursor, "__exit__", None)
            if callable(leave):
                return leave(*exc)
            return None
        finally:
            self._release_once()

    def close(self) -> None:
        try:
            closer = getattr(self._cursor, "close", None)
            if callable(closer):
                closer()
        finally:
            self._release_once()

    def _release_once(self) -> None:
        if self._released:
            return
        self._released = True
        self._pool.release()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _PooledConnection:
    """Thin wrapper so ``.cursor()`` auto-releases via ``_PooledCursor``."""

    def __init__(self, pool: "ThreadLocalPsycopg", conn: Any) -> None:
        self._pool = pool
        self._conn = conn

    def unwrap(self) -> Any:
        return self._conn

    def cursor(self, *args: Any, **kwargs: Any) -> _PooledCursor:
        return _PooledCursor(self._pool, self._conn.cursor(*args, **kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


class ThreadLocalPsycopg:
    """Checkout pool with per-thread re-entrant holds; optional live-client cap."""

    def __init__(
        self,
        connect: Callable[[], Any],
        *,
        max_size: int | None = None,
    ) -> None:
        self._connect = connect
        # None = no artificial cap (reuse via idle list; grow with concurrent holds).
        self._max_size = None if max_size is None else max(1, int(max_size))
        self._local = threading.local()
        self._idle: list[Any] = []
        self._all: list[Any] = []
        self._live = 0
        self._cond = threading.Condition(threading.Lock())

    def live_count(self) -> int:
        with self._cond:
            return int(self._live)

    def get(self) -> _PooledConnection:
        depth = int(getattr(self._local, "depth", 0) or 0)
        if depth > 0:
            self._local.depth = depth + 1
            return _PooledConnection(self, self._local.connection)

        conn = self._checkout()
        self._local.connection = conn
        self._local.depth = 1
        return _PooledConnection(self, conn)

    def release(self) -> None:
        """Drop one re-entrant hold; return connection to idle at depth 0."""
        depth = int(getattr(self._local, "depth", 0) or 0)
        if depth <= 0:
            return
        if depth > 1:
            self._local.depth = depth - 1
            return
        conn = getattr(self._local, "connection", None)
        self._local.connection = None
        self._local.depth = 0
        self._checkin(conn)

    def drop(self) -> None:
        """Forget the current thread’s connection after a transport error."""
        conn = getattr(self._local, "connection", None)
        self._local.connection = None
        self._local.depth = 0
        if conn is None:
            return
        self._discard(conn)

    def close_all(self) -> None:
        with self._cond:
            conns = list(self._all)
            self._all.clear()
            self._idle.clear()
            self._live = 0
            self._cond.notify_all()
        for conn in conns:
            self._close_quiet(conn)
        self._local.connection = None
        self._local.depth = 0

    def _checkout(self) -> Any:
        # Retry when the server reports slot exhaustion; then fail with a typed error.
        max_attempts = max(1, int(os.environ.get("ASTLOOM_PG_CAPACITY_RETRIES", "6") or "6"))
        last_exc: BaseException | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self._checkout_once()
            except Exception as exc:  # noqa: BLE001 — classify capacity vs other
                if not is_db_capacity_error(exc):
                    raise
                last_exc = exc
                with self._cond:
                    self._cond.notify_all()
                if attempt >= max_attempts:
                    break
                # Wait for a sibling checkin / other process to free a slot.
                delay = min(2.0, 0.15 * attempt)
                with self._cond:
                    self._cond.wait(timeout=delay)
        assert last_exc is not None
        raise _capacity_error_type()() from last_exc

    def _checkout_once(self) -> Any:
        with self._cond:
            while True:
                while self._idle:
                    conn = self._idle.pop()
                    if not getattr(conn, "closed", False):
                        return conn
                    self._live = max(0, self._live - 1)
                    try:
                        self._all.remove(conn)
                    except ValueError:
                        pass
                if self._max_size is None or self._live < self._max_size:
                    self._live += 1
                    break
                self._cond.wait(timeout=30.0)
        try:
            conn = self._connect()
        except Exception:
            with self._cond:
                self._live = max(0, self._live - 1)
                self._cond.notify()
            raise
        with self._cond:
            self._all.append(conn)
        return conn

    def _checkin(self, conn: Any | None) -> None:
        if conn is None:
            return
        if getattr(conn, "closed", False):
            self._discard(conn)
            return
        with self._cond:
            self._idle.append(conn)
            self._cond.notify()

    def _discard(self, conn: Any) -> None:
        self._close_quiet(conn)
        with self._cond:
            try:
                self._all.remove(conn)
            except ValueError:
                pass
            self._live = max(0, self._live - 1)
            self._cond.notify()

    @staticmethod
    def _close_quiet(conn: Any) -> None:
        try:
            if not getattr(conn, "closed", False):
                conn.close()
        except Exception:  # noqa: BLE001 — best-effort shutdown
            pass
