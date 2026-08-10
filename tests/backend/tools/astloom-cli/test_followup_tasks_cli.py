"""CLI parser smoke for followup-tasks subcommands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from astloom_cli.followup_task_lifecycle import (
    ORIGIN_QUALITY,
    ORIGIN_SYNC,
    RETENTION_CLASS,
    adopt_legacy_quality_tasks,
    create_automated_followup_task,
    is_automated_followup,
    list_automated_followup_tasks,
    parse_legacy_quality_title,
    parse_legacy_sync_title,
    quality_fingerprint,
    sync_fingerprint,
    terminal_purge_candidates,
)
from astloom_cli.parser import build_parser
from core_data_service.core import CoreData, Kind, Scope
from core_data_service.testing import InMemoryStore


def test_parser_followup_tasks_subcommands():
    parser = build_parser()
    listed = parser.parse_args(["followup-tasks", "list", "--status", "open"])
    assert listed.command == "followup-tasks"
    assert listed.followup_tasks_command == "list"
    assert listed.status == "open"

    status = parser.parse_args(["followup-tasks", "status", "--origin", "sync"])
    assert status.followup_tasks_command == "status"
    assert status.origin == "sync"

    adopt = parser.parse_args(["followup-tasks", "adopt-legacy", "--dry-run"])
    assert adopt.followup_tasks_command == "adopt-legacy"
    assert adopt.dry_run is True

    recon = parser.parse_args(["followup-tasks", "reconcile", "--dry-run"])
    assert recon.followup_tasks_command == "reconcile"
    assert recon.dry_run is True

    purge = parser.parse_args(["followup-tasks", "purge", "--days", "7", "--yes"])
    assert purge.followup_tasks_command == "purge"
    assert purge.days == 7
    assert purge.yes is True


def test_list_and_purge_candidates_helpers():
    core = CoreData(InMemoryStore())
    scope = Scope("t", "w", "p")
    fp = sync_fingerprint("docs.standards_skipped")
    created = create_automated_followup_task(
        core,
        scope=scope,
        actor="test",
        correlation_id="c1",
        project_id="p",
        title="t",
        instructions="i",
        origin=ORIGIN_SYNC,
        followup_kind="docs.standards_skipped",
        paths=["docs/a.md"],
        fingerprint=fp,
    )
    open_rows = list_automated_followup_tasks(
        core, scope=scope, origins={ORIGIN_SYNC}, status_group="open"
    )
    assert len(open_rows) == 1
    assert open_rows[0]["id"] == created["id"]

    record = core.store.get(created["id"], scope)
    record.status = "canceled"
    record.updated_at = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    core.store.put(record)
    cand = terminal_purge_candidates(core, scope=scope, retention_days_value=30)
    assert len(cand) == 1
    assert cand[0].id == created["id"]


def test_adopt_legacy_quality_stamps_and_cancels_dupes():
    assert parse_legacy_quality_title(
        "Quality: code.stale_edited — backend/packages/x.py"
    ) == ("code.stale_edited", "backend/packages/x.py")
    assert parse_legacy_sync_title("Remediate 1 sync-skipped nonconforming doc(s)") == (
        "docs.standards_skipped",
        sync_fingerprint("docs.standards_skipped"),
    )

    core = CoreData(InMemoryStore())
    scope = Scope("t", "w", "p")
    title = "Quality: code.never_ingested — path/a.py"
    for i in range(2):
        core.create(
            Kind.TASK,
            scope,
            "test",
            f"c{i}",
            f"legacy-{i}",
            {
                "title": title,
                "assignee_type": "backend",
                "instructions": "old",
                "acceptance_criteria": ["remediate"],
            },
        )
    core.create(
        Kind.TASK,
        scope,
        "test",
        "c-sync",
        "legacy-sync",
        {
            "title": "Code graph debt: 0 never-ingested, 2 stale-edited",
            "assignee_type": "backend",
            "instructions": "old",
            "acceptance_criteria": ["remediate"],
        },
    )
    core.create(
        Kind.TASK,
        scope,
        "test",
        "c-orphan",
        "legacy-orphan",
        {
            "title": "Quality: split soft-budget docs (404/441 lines)",
            "assignee_type": "backend",
            "instructions": "old",
            "acceptance_criteria": ["remediate"],
        },
    )
    out = adopt_legacy_quality_tasks(
        core,
        scope=scope,
        actor="test",
        correlation_id="adopt-1",
        dry_run=False,
    )
    assert out["tasks_adopted"] == 3
    assert out["tasks_canceled_dupes"] == 1
    assert out["tasks_canceled_orphans"] == 1
    tasks = core.store.list(Kind.TASK, scope)
    auto = [t for t in tasks if is_automated_followup(t)]
    assert len(auto) == 3
    opens = [t for t in auto if t.status in {"proposed", "ready", "reopened"}]
    assert len(opens) == 2
    fps = {t.data["fingerprint"] for t in opens}
    assert quality_fingerprint("code.never_ingested", "path/a.py") in fps
    assert sync_fingerprint("code.sync_debt") in fps
    assert ORIGIN_SYNC in {t.data["origin"] for t in opens}
    assert ORIGIN_QUALITY in {t.data["origin"] for t in opens}
    assert all(t.data["retention_class"] == RETENTION_CLASS for t in auto)
