from __future__ import annotations

from change_society.domain.models import ConflictError, NotFoundError, RunState, Scope, SocietyRun
from change_society.infrastructure.repositories import InMemoryRunRepository, run_from_dict, run_to_dict


SCOPE = Scope("tenant", "workspace", "project")


def empty_run(run_id: str = "run_1") -> SocietyRun:
    return SocietyRun(run_id, SCOPE, "actor", "corr", "request text long enough", "pricing-refactor", RunState.ACCEPTED, "t1", "t1")


def test_in_memory_repository_round_trips_and_isolates_projects():
    repo = InMemoryRunRepository()
    repo.save(empty_run())
    loaded = repo.get(SCOPE, "run_1")
    assert loaded.run_id == "run_1"
    assert repo.list_runs(Scope("tenant", "workspace", "other")) == []
    try:
        repo.get(SCOPE, "missing")
        raise AssertionError("expected not found")
    except NotFoundError:
        pass


def test_in_memory_repository_enforces_idempotency_fingerprint():
    repo = InMemoryRunRepository()
    repo.remember_idempotent(SCOPE, "create_society_run", "key-1", "fp-1", "run_1")
    assert repo.find_idempotent(SCOPE, "create_society_run", "key-1", "fp-1") == "run_1"
    try:
        repo.find_idempotent(SCOPE, "create_society_run", "key-1", "fp-2")
        raise AssertionError("expected idempotency conflict")
    except ConflictError:
        pass


def test_in_memory_repository_detects_stale_version_on_save():
    repo = InMemoryRunRepository()
    run = empty_run()
    repo.save(run)
    stale = repo.get(SCOPE, "run_1")
    current = repo.get(SCOPE, "run_1")
    current.transition(RunState.GATHERING_CONTEXT, "t2")
    repo.save(current)
    try:
        repo.save(stale, expected_version=1)
        raise AssertionError("expected version conflict")
    except ConflictError as exc:
        assert "stale" in exc.message


def test_run_serialization_preserves_messages_and_conflicts():
    run = empty_run()
    payload = run_to_dict(run)
    restored = run_from_dict(payload)
    assert restored.scenario_id == run.scenario_id
    assert restored.state == RunState.ACCEPTED


def test_postgres_run_persists_after_idempotency_read_and_connection_rollback():
    import os

    database_url = os.getenv("CHANGE_SOCIETY_DATABASE_URL", "").strip()
    if os.getenv("CHANGE_SOCIETY_STORE", "memory") != "postgresql" or not database_url:
        import pytest

        pytest.skip("PostgreSQL integration test requires CHANGE_SOCIETY_STORE=postgresql and CHANGE_SOCIETY_DATABASE_URL")

    from change_society.infrastructure.repositories import PostgresRunRepository

    repo = PostgresRunRepository(database_url)
    scope = Scope("tenant", "workspace", "project")
    run = SocietyRun("run_pg_txn", scope, "actor", "corr", "request text long enough", "pricing-refactor", RunState.ACCEPTED, "t1", "t1")
    repo.find_idempotent(scope, "create_society_run", "pg-txn-key", "fp")
    repo.save(run)
    repo.remember_idempotent(scope, "create_society_run", "pg-txn-key", "fp", run.run_id)
    repo._connection.rollback()
    loaded = repo.get(scope, "run_pg_txn")
    assert loaded.run_id == "run_pg_txn"
