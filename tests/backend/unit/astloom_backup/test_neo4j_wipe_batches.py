"""Unit: Neo4j wipe uses batched DETACH DELETE (avoids heap OOM)."""

from __future__ import annotations

from astloom_backup.neo4j_store import wipe_neo4j
from astloom_backup.scope import Scope


class _FakeResult:
    def __init__(self, counts: list[int]):
        self._counts = list(counts)

    def single(self):
        if not self._counts:
            return {"c": 0}
        return {"c": self._counts.pop(0)}


class _FakeSession:
    def __init__(self, counts: list[int]):
        self.queries: list[str] = []
        self._result = _FakeResult(counts)

    def run(self, query: str, **_kwargs):
        self.queries.append(query)
        return self._result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeDriver:
    def __init__(self, session: _FakeSession):
        self._session = session

    def session(self, database: str = "neo4j"):  # noqa: ARG002
        return self._session

    def close(self):
        return None


def test_wipe_neo4j_batches_until_empty(monkeypatch):
    monkeypatch.setenv("ASTLOOM_NEO4J_PASSWORD", "not-a-placeholder-secret")
    monkeypatch.setenv("ASTLOOM_NEO4J_URI", "bolt://127.0.0.1:7687")
    session = _FakeSession([500, 500, 47, 0])
    monkeypatch.setattr(
        "astloom_backup.neo4j_store._driver", lambda: _FakeDriver(session)
    )
    out = wipe_neo4j(Scope("t", "w", "p"), batch_size=500)
    assert out["nodes"] == 1047
    assert all("LIMIT $limit" in q for q in session.queries)
    assert all("DETACH DELETE" in q for q in session.queries)
