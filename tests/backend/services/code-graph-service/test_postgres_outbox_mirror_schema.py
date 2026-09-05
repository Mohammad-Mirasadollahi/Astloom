"""PostgresOutboxMirror must create code_graph.outbox on Neo4j-primary bootstrap."""

from __future__ import annotations

from code_graph_service.postgres_side import PostgresOutboxMirror, _run_with_schema_heal


def test_outbox_mirror_ensure_schema_applies_base_migrations():
    executed: list[str] = []

    class _Cur:
        def execute(self, sql):
            executed.append(str(sql))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _Conn:
        def cursor(self):
            return _Cur()

    class _Pool:
        def get(self):
            return _Conn()

        def close_all(self):
            return None

    mirror = PostgresOutboxMirror.__new__(PostgresOutboxMirror)
    mirror._pool = _Pool()
    mirror.ensure_schema()
    joined = "\n".join(executed)
    assert executed[0].strip().startswith("CREATE SCHEMA IF NOT EXISTS code_graph")
    assert "CREATE TABLE IF NOT EXISTS code_graph.outbox" in joined
    assert "published_at" in joined


def test_append_event_heals_missing_outbox_relation():
    calls = {"n": 0, "healed": 0}

    class _Cur:
        def execute(self, sql, params=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError(
                    'relation "code_graph.outbox" does not exist\n'
                    "LINE 2: INSERT INTO code_graph.outbox"
                )

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _Conn:
        def cursor(self):
            return _Cur()

    class _Pool:
        def get(self):
            return _Conn()

        def close_all(self):
            return None

    mirror = PostgresOutboxMirror.__new__(PostgresOutboxMirror)
    mirror._pool = _Pool()
    mirror._json = lambda x: x

    def _ensure():
        calls["healed"] += 1

    mirror.ensure_schema = _ensure  # type: ignore[method-assign]
    mirror.append_event({"event_id": "e1", "event_type": "t", "payload": {}})
    assert calls["healed"] == 1
    assert calls["n"] == 2


def test_run_with_schema_heal_ignores_unrelated_errors():
    def _ensure():
        raise AssertionError("should not heal")

    def _op():
        raise RuntimeError("connection refused")

    try:
        _run_with_schema_heal(_ensure, _op)
    except RuntimeError as exc:
        assert "connection refused" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
