"""GAP-A08 ChangeSet collaboration surface (backend, no UI)."""

from __future__ import annotations

import pytest

from core_data_service.core import ConflictError, CoreData, Kind, Scope
from core_data_service.testing import InMemoryStore

SCOPE = Scope("t", "w", "p")


def test_changeset_lifecycle_and_self_approval_forbidden():
    svc = CoreData(InMemoryStore())
    cs = svc.create_changeset(
        SCOPE,
        "agent-1",
        "corr",
        "cs-1",
        {"title": "Fix auth", "artifact_ref": "artifact://patch-1", "task_id": "task-1"},
    )
    assert cs.kind == Kind.CHANGESET
    assert cs.status == "draft"
    svc.transition(SCOPE, "agent-1", "corr", "cs-open", cs.id, "open", "ready", None, Kind.CHANGESET)
    svc.transition(SCOPE, "agent-1", "corr", "cs-review", cs.id, "in_review", "review", None, Kind.CHANGESET)
    with pytest.raises(ConflictError):
        svc.approve_changeset(SCOPE, "agent-1", "corr", "cs-approve-self", cs.id)
    approved = svc.approve_changeset(SCOPE, "reviewer-1", "corr", "cs-approve", cs.id)
    assert approved.status == "approved"


def test_review_thread_discussion_and_label():
    svc = CoreData(InMemoryStore())
    cs = svc.create_changeset(
        SCOPE,
        "agent-1",
        "corr",
        "cs-2",
        {"title": "Add API", "artifact_ref": "artifact://patch-2"},
    )
    thread = svc.create(
        Kind.REVIEW_THREAD,
        SCOPE,
        "reviewer",
        "corr",
        "rt-1",
        {"changeset_id": cs.id, "anchor_kind": "general"},
    )
    comment = svc.create(
        Kind.REVIEW_COMMENT,
        SCOPE,
        "reviewer",
        "corr",
        "rc-1",
        {"thread_id": thread.id, "body": "LGTM with nits", "author_ref": "reviewer"},
    )
    discussion = svc.create(
        Kind.DISCUSSION_COMMENT,
        SCOPE,
        "agent-1",
        "corr",
        "dc-1",
        {
            "target_kind": "changeset",
            "target_id": cs.id,
            "body": "Will address nits",
            "author_ref": "agent-1",
        },
    )
    label = svc.create(
        Kind.WORK_LABEL,
        SCOPE,
        "agent-1",
        "corr",
        "wl-1",
        {"name": "security"},
    )
    assert comment.data["thread_id"] == thread.id
    assert discussion.data["target_id"] == cs.id
    assert label.status == "active"


def test_external_fingerprint_is_projection_not_sor():
    svc = CoreData(InMemoryStore())
    cs = svc.create_changeset(
        SCOPE,
        "agent-1",
        "corr",
        "cs-3",
        {
            "title": "Mirror PR",
            "artifact_ref": "artifact://patch-3",
            "external_fingerprint": "github:pr:123",
        },
    )
    # Native SoR remains Astloom ChangeSet id; external id is metadata only.
    assert cs.id != "github:pr:123"
    assert cs.data["external_fingerprint"] == "github:pr:123"


def test_create_changeset_idempotent():
    store = InMemoryStore()
    svc = CoreData(store)
    payload = {"title": "Idem", "artifact_ref": "artifact://x"}
    a = svc.create_changeset(SCOPE, "agent", "corr", "same-key", payload)
    b = svc.create_changeset(SCOPE, "agent", "corr", "same-key", payload)
    assert a.id == b.id


def test_review_comment_verdict_rollups_changeset():
    store = InMemoryStore()
    svc = CoreData(store)
    cs = svc.create_changeset(
        SCOPE,
        "agent-1",
        "corr",
        "cs-roll",
        {"title": "Needs changes", "artifact_ref": "artifact://r"},
    )
    svc.transition(SCOPE, "agent-1", "corr", "cs-open", cs.id, "open", "ready", None, Kind.CHANGESET)
    svc.transition(SCOPE, "agent-1", "corr", "cs-rev", cs.id, "in_review", "review", None, Kind.CHANGESET)
    thread = svc.create(
        Kind.REVIEW_THREAD,
        SCOPE,
        "reviewer",
        "corr",
        "rt-roll",
        {"changeset_id": cs.id, "anchor_kind": "general"},
    )
    svc.create(
        Kind.REVIEW_COMMENT,
        SCOPE,
        "reviewer",
        "corr",
        "rc-roll",
        {
            "thread_id": thread.id,
            "body": "Please fix",
            "author_ref": "reviewer",
            "verdict": "request_changes",
        },
    )
    updated = store.get(cs.id, SCOPE)
    assert updated.status == "changes_requested"
    events = [e["event_type"] for e in store.outbox()]
    assert "changeset.review_rollup" in events
    assert "review_comment.added" in events
