"""Unit tests for automated follow-up Task lifecycle (dedupe / reconcile / purge)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from astloom_cli.followup_task_lifecycle import (
    ORIGIN_QUALITY,
    ORIGIN_SYNC,
    create_automated_followup_task,
    purge_terminal_automated_followup_tasks,
    quality_fingerprint,
    reconcile_automated_followup_tasks,
    retention_days,
    sync_fingerprint,
)
from astloom_cli.sync_followup_tasks import create_sync_followup_tasks
from astloom_cli.sync_standards_gate import StandardsGateResult
from core_data_service.core import CoreData, Kind, Scope
from core_data_service.testing import InMemoryStore


SCOPE = Scope("t", "w", "p")


def test_fingerprints_are_stable():
    assert sync_fingerprint("code.sync_debt") == "sync-followup:code.sync_debt"
    assert quality_fingerprint("docs.size_soft", "docs/a.md") == (
        "mcp-quality:docs.size_soft:docs/a.md"
    )


def test_retention_days_env(monkeypatch):
    monkeypatch.delenv("ASTLOOM_FOLLOWUP_TASK_RETENTION_DAYS", raising=False)
    assert retention_days({}) == 30
    assert retention_days({"ASTLOOM_FOLLOWUP_TASK_RETENTION_DAYS": "0"}) == 0
    assert retention_days({"ASTLOOM_FOLLOWUP_TASK_RETENTION_DAYS": "7"}) == 7
    assert retention_days({"ASTLOOM_FOLLOWUP_TASK_RETENTION_DAYS": "x"}) == 30


def test_create_is_idempotent_per_fingerprint():
    core = CoreData(InMemoryStore())
    fp = sync_fingerprint("docs.standards_skipped")
    first = create_automated_followup_task(
        core,
        scope=SCOPE,
        actor="test",
        correlation_id="c1",
        project_id="p",
        title="t1",
        instructions="i1",
        origin=ORIGIN_SYNC,
        followup_kind="docs.standards_skipped",
        paths=["docs/a.md"],
        fingerprint=fp,
    )
    second = create_automated_followup_task(
        core,
        scope=SCOPE,
        actor="test",
        correlation_id="c2",
        project_id="p",
        title="t2",
        instructions="i2",
        origin=ORIGIN_SYNC,
        followup_kind="docs.standards_skipped",
        paths=["docs/a.md", "docs/b.md"],
        fingerprint=fp,
    )
    assert first["id"] == second["id"]
    assert len(core.store.list(Kind.TASK, SCOPE)) == 1


def test_reconcile_cancels_cleared_debt_origin_scoped():
    core = CoreData(InMemoryStore())
    sync_fp = sync_fingerprint("code.sync_debt")
    quality_fp = quality_fingerprint("code.never_ingested", "x.py")
    create_automated_followup_task(
        core,
        scope=SCOPE,
        actor="test",
        correlation_id="c1",
        project_id="p",
        title="sync debt",
        instructions="sync",
        origin=ORIGIN_SYNC,
        followup_kind="code.sync_debt",
        paths=["x.py"],
        fingerprint=sync_fp,
    )
    create_automated_followup_task(
        core,
        scope=SCOPE,
        actor="test",
        correlation_id="c2",
        project_id="p",
        title="quality debt",
        instructions="q",
        origin=ORIGIN_QUALITY,
        followup_kind="code.never_ingested",
        paths=["x.py"],
        fingerprint=quality_fp,
    )
    # Sync reconcile with empty active set cancels only sync origin.
    out = reconcile_automated_followup_tasks(
        core,
        scope=SCOPE,
        actor="test",
        correlation_id="c3",
        active_fingerprints=set(),
        origins={ORIGIN_SYNC},
    )
    assert out["tasks_canceled"] == 1
    tasks = {t.data["fingerprint"]: t for t in core.store.list(Kind.TASK, SCOPE)}
    assert tasks[sync_fp].status == "canceled"
    assert tasks[quality_fp].status == "proposed"


def test_purge_respects_retention_window():
    core = CoreData(InMemoryStore())
    fp = sync_fingerprint("code.sync_debt")
    created = create_automated_followup_task(
        core,
        scope=SCOPE,
        actor="test",
        correlation_id="c1",
        project_id="p",
        title="sync debt",
        instructions="sync",
        origin=ORIGIN_SYNC,
        followup_kind="code.sync_debt",
        paths=["x.py"],
        fingerprint=fp,
    )
    reconcile_automated_followup_tasks(
        core,
        scope=SCOPE,
        actor="test",
        correlation_id="c2",
        active_fingerprints=set(),
        origins={ORIGIN_SYNC},
    )
    task = core.store.get(created["id"], SCOPE)
    # Age the terminal task beyond retention.
    task.updated_at = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    core.store.put(task)

    purged = purge_terminal_automated_followup_tasks(
        core,
        scope=SCOPE,
        actor="test",
        correlation_id="c3",
        retention_days_value=30,
        now=datetime.now(UTC),
    )
    assert purged["tasks_purged"] == 1
    assert core.store.list(Kind.TASK, SCOPE) == []


def test_purge_disabled_when_retention_zero():
    core = CoreData(InMemoryStore())
    fp = sync_fingerprint("code.sync_debt")
    created = create_automated_followup_task(
        core,
        scope=SCOPE,
        actor="test",
        correlation_id="c1",
        project_id="p",
        title="sync debt",
        instructions="sync",
        origin=ORIGIN_SYNC,
        followup_kind="code.sync_debt",
        paths=["x.py"],
        fingerprint=fp,
    )
    reconcile_automated_followup_tasks(
        core,
        scope=SCOPE,
        actor="test",
        correlation_id="c2",
        active_fingerprints=set(),
        origins={ORIGIN_SYNC},
    )
    task = core.store.get(created["id"], SCOPE)
    task.updated_at = (datetime.now(UTC) - timedelta(days=400)).isoformat()
    core.store.put(task)
    purged = purge_terminal_automated_followup_tasks(
        core,
        scope=SCOPE,
        actor="test",
        correlation_id="c3",
        retention_days_value=0,
    )
    assert purged["tasks_purged"] == 0
    assert len(core.store.list(Kind.TASK, SCOPE)) == 1


def test_create_sync_followup_tasks_surfaces_lifecycle_fields(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "astloom_cli.sync_followup_tasks.repo_root",
        lambda: tmp_path,
    )

    class _FakeCore:
        def __init__(self):
            self.inner = CoreData(InMemoryStore())

        def __getattr__(self, name):
            return getattr(self.inner, name)

    class _FakeBackends:
        def __init__(self):
            self.core = _FakeCore()

        @classmethod
        def from_env(cls):
            return cls()

        def core_scope(self, scope_dict):
            return Scope(
                scope_dict["tenant_id"],
                scope_dict["workspace_id"],
                scope_dict["project_id"],
            )

        def close(self):
            return None

    monkeypatch.setattr(
        "astloom_cli.sync_followup_tasks.open_platform_backends",
        lambda scope: (
            _FakeBackends(),
            Scope("t", "w", "p"),
            {"tenant_id": "t", "workspace_id": "w", "project_id": "p"},
        ),
    )
    gate = StandardsGateResult(
        mode="skip",
        skipped=True,
        skipped_docs=["docs/a.md"],
        docs_nonconforming=["docs/a.md"],
    )

    class _Scope:
        tenant_id = "t"
        workspace_id = "w"
        project_id = "p"

    out = create_sync_followup_tasks(
        scope=_Scope(),
        standards_gate=gate,
        include_code_audit=False,
    )
    assert out["specs_count"] == 1
    assert out["tasks_created_count"] == 1
    assert "tasks_canceled" in out
    assert "tasks_purged" in out
    assert Path(out["mirror_path"]).is_file()
    # include_code_audit=False must preserve code.sync_debt in active set.
    assert "sync-followup:code.sync_debt" in out["active_fingerprints"]


def test_create_sync_followup_preserves_code_debt_when_audit_fails(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "astloom_cli.sync_followup_tasks.repo_root",
        lambda: tmp_path,
    )

    class _FakeCore:
        def __init__(self):
            self.inner = CoreData(InMemoryStore())

        def __getattr__(self, name):
            return getattr(self.inner, name)

    class _FakeBackends:
        def __init__(self):
            self.core = _FakeCore()

        def close(self):
            return None

        def core_scope(self, scope_dict):
            return Scope(
                scope_dict["tenant_id"],
                scope_dict["workspace_id"],
                scope_dict["project_id"],
            )

    monkeypatch.setattr(
        "astloom_cli.sync_followup_tasks.open_platform_backends",
        lambda scope: (
            _FakeBackends(),
            Scope("t", "w", "p"),
            {"tenant_id": "t", "workspace_id": "w", "project_id": "p"},
        ),
    )

    def _boom():
        raise RuntimeError("audit down")

    monkeypatch.setattr(
        "astloom_cli.commands.quality_audit.collect.build_quality_audit_report",
        _boom,
    )
    # Patch where sync_followup imports it inside the function — use a module-level boom via
    # injecting into the import path used by create_sync_followup_tasks.
    import astloom_cli.commands.quality_audit.collect as collect_mod

    monkeypatch.setattr(collect_mod, "build_quality_audit_report", _boom)

    # Seed an open code.sync_debt Task that must not be canceled on audit failure.
    from astloom_cli.followup_task_lifecycle import (
        ORIGIN_SYNC,
        create_automated_followup_task,
        sync_fingerprint,
    )

    backends = _FakeBackends()
    create_automated_followup_task(
        backends.core,
        scope=Scope("t", "w", "p"),
        actor="seed",
        correlation_id="seed",
        project_id="p",
        title="debt",
        instructions="i",
        origin=ORIGIN_SYNC,
        followup_kind="code.sync_debt",
        paths=["x.py"],
        fingerprint=sync_fingerprint("code.sync_debt"),
    )
    monkeypatch.setattr(
        "astloom_cli.sync_followup_tasks.open_platform_backends",
        lambda scope: (
            backends,
            Scope("t", "w", "p"),
            {"tenant_id": "t", "workspace_id": "w", "project_id": "p"},
        ),
    )

    gate = StandardsGateResult(
        mode="skip",
        skipped=True,
        skipped_docs=[],
        docs_nonconforming=[],
    )

    class _Scope:
        tenant_id = "t"
        workspace_id = "w"
        project_id = "p"

    out = create_sync_followup_tasks(
        scope=_Scope(),
        standards_gate=gate,
        include_code_audit=True,
    )
    assert any("code_audit:" in e for e in out["create_errors"])
    assert "sync-followup:code.sync_debt" in out["active_fingerprints"]
    assert out["tasks_canceled"] == 0
    assert len(backends.core.store.list(Kind.TASK, Scope("t", "w", "p"))) == 1
