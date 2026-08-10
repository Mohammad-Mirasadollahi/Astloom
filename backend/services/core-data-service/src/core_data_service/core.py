from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Any, Protocol
from uuid import uuid4


class Kind(StrEnum):
    ACTIVITY = "activity"
    WORK_LOG = "work_log"
    DECISION = "decision"
    ISSUE = "issue"
    TASK = "task"
    CHANGESET = "changeset"
    REVIEW_THREAD = "review_thread"
    REVIEW_COMMENT = "review_comment"
    DISCUSSION_COMMENT = "discussion_comment"
    WORK_LABEL = "work_label"


class CoreDataError(Exception):
    def __init__(self, code: str, category: str, message: str):
        super().__init__(message)
        self.code, self.category, self.message = code, category, message


class ValidationError(CoreDataError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class ConflictError(CoreDataError):
    def __init__(self, message: str):
        super().__init__("conflict_error", "conflict_error", message)


class NotFoundError(CoreDataError):
    def __init__(self, message: str):
        super().__init__("not_found", "not_found_error", message)


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    workspace_id: str
    project_id: str

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.workspace_id.strip(), self.project_id.strip())):
            raise ValidationError("tenant_id, workspace_id, and project_id are required")


@dataclass
class Record:
    id: str
    kind: Kind
    scope: Scope
    actor_id: str
    correlation_id: str
    status: str
    data: dict[str, Any]
    created_at: str
    updated_at: str
    version: int = 1

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "status": self.status,
            "version": self.version,
            "data": self.data,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


DEFAULT_STATUS = {
    Kind.ACTIVITY: "recorded",
    Kind.WORK_LOG: "created",
    Kind.DECISION: "proposed",
    Kind.ISSUE: "open",
    Kind.TASK: "proposed",
    Kind.CHANGESET: "draft",
    Kind.REVIEW_THREAD: "open",
    Kind.REVIEW_COMMENT: "recorded",
    Kind.DISCUSSION_COMMENT: "recorded",
    Kind.WORK_LABEL: "active",
}
CREATE_EVENTS = {
    Kind.ACTIVITY: "activity.recorded",
    Kind.WORK_LOG: "worklog.created",
    Kind.DECISION: "decision.created",
    Kind.ISSUE: "issue.discovered",
    Kind.TASK: "task.created",
    Kind.CHANGESET: "changeset.created",
    Kind.REVIEW_THREAD: "review_thread.created",
    Kind.REVIEW_COMMENT: "review_comment.added",
    Kind.DISCUSSION_COMMENT: "discussion_comment.added",
    Kind.WORK_LABEL: "work_label.created",
}
TRANSITIONS = {
    Kind.TASK: {
        "proposed": {"ready", "blocked", "canceled"},
        "ready": {"in_progress", "blocked", "canceled"},
        "in_progress": {"blocked", "review", "done", "canceled"},
        "blocked": {"ready", "canceled"},
        "review": {"in_progress", "done", "reopened"},
        "done": {"reopened"},
        "canceled": {"reopened"},
        "reopened": {"ready", "in_progress", "canceled"},
    },
    Kind.DECISION: {
        "proposed": {"active", "rejected", "expired"},
        "active": {"superseded", "expired"},
        "superseded": set(),
        "rejected": set(),
        "expired": set(),
    },
    Kind.ISSUE: {
        "open": {"triaged", "accepted", "deferred", "closed"},
        "triaged": {"accepted", "mitigated", "closed", "deferred"},
        "accepted": {"mitigated", "closed"},
        "mitigated": {"closed", "open"},
        "deferred": {"triaged", "closed"},
        "closed": {"open"},
    },
    Kind.CHANGESET: {
        "draft": {"open", "closed"},
        "open": {"in_review", "closed"},
        "in_review": {"approved", "changes_requested", "closed"},
        "changes_requested": {"open", "in_review", "closed"},
        "approved": {"applying", "closed"},
        "applying": {"applied", "changes_requested"},
        "applied": {"closed"},
        "closed": set(),
    },
}
REQUIRED = {
    Kind.ACTIVITY: ("action_type", "action_summary"),
    Kind.WORK_LOG: ("session_id", "agent_id", "summary"),
    Kind.DECISION: ("title", "context", "options_considered", "chosen_option", "consequences", "owner"),
    Kind.ISSUE: ("title", "description", "severity"),
    Kind.TASK: ("title", "assignee_type", "instructions", "acceptance_criteria"),
    Kind.CHANGESET: ("title", "artifact_ref"),
    Kind.REVIEW_THREAD: ("changeset_id", "anchor_kind"),
    Kind.REVIEW_COMMENT: ("thread_id", "body", "author_ref"),
    Kind.DISCUSSION_COMMENT: ("target_kind", "target_id", "body", "author_ref"),
    Kind.WORK_LABEL: ("name",),
}
SECRET = re.compile(r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)([^\s,;]+)")
OPEN_ISSUE_STATES = {"open", "triaged", "accepted"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return SECRET.sub(r"\1[REDACTED]", value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    return value


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(encoded).hexdigest()


class Store(Protocol):
    def get(self, record_id: str, scope: Scope) -> Record: ...
    def list(self, kind: Kind, scope: Scope) -> list[Record]: ...
    def put(self, record: Record) -> None: ...
    def delete(self, record_id: str, scope: Scope) -> None: ...
    def idempotent(self, scope: Scope, command: str, key: str, payload: dict[str, Any]) -> str | None: ...
    def remember(self, scope: Scope, command: str, key: str, payload: dict[str, Any], record_id: str) -> None: ...
    def event(self, payload: dict[str, Any]) -> None: ...
    def outbox(self) -> list[dict[str, Any]]: ...


class CoreData:
    def __init__(self, store: Store):
        self.store = store

    def create(self, kind: Kind, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> Record:
        if not key:
            raise ValidationError("Idempotency-Key header is required")
        missing = [field for field in REQUIRED[kind] if not payload.get(field)]
        if missing:
            raise ValidationError("missing required fields: " + ", ".join(missing))
        if kind == Kind.ISSUE and payload["severity"] not in {"low", "medium", "high", "critical"}:
            raise ValidationError("invalid issue severity")
        payload = redact(payload)
        prior = self.store.idempotent(scope, "create:" + kind.value, key, payload)
        if prior:
            return self.store.get(prior, scope)
        timestamp = now()
        record = Record(
            str(uuid4()),
            kind,
            scope,
            actor,
            correlation_id,
            payload.pop("status", None) or DEFAULT_STATUS[kind],
            payload,
            timestamp,
            timestamp,
        )
        self.store.put(record)
        self.store.remember(scope, "create:" + kind.value, key, payload, record.id)
        self.emit(CREATE_EVENTS[kind], record, key)
        if kind == Kind.REVIEW_COMMENT:
            self._rollup_review_comment(scope, actor, correlation_id, key, record)
        return record

    def _rollup_review_comment(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        comment: Record,
    ) -> None:
        """Doc 08: request_changes/block on a review comment forces ChangeSet changes_requested."""
        verdict = str(comment.data.get("verdict") or "").strip().lower()
        if verdict not in {"request_changes", "block", "changes_requested"}:
            return
        thread_id = str(comment.data.get("thread_id") or "")
        if not thread_id:
            return
        try:
            thread = self.store.get(thread_id, scope)
        except Exception:
            return
        if thread.kind != Kind.REVIEW_THREAD:
            return
        changeset_id = str(thread.data.get("changeset_id") or "")
        if not changeset_id:
            return
        try:
            changeset = self.store.get(changeset_id, scope)
        except Exception:
            return
        if changeset.kind != Kind.CHANGESET:
            return
        if changeset.status not in {"open", "in_review"}:
            return
        target = "changes_requested"
        if target not in TRANSITIONS[Kind.CHANGESET].get(changeset.status, set()):
            # open → in_review first when needed
            if changeset.status == "open" and "in_review" in TRANSITIONS[Kind.CHANGESET]["open"]:
                self.transition(
                    scope,
                    actor,
                    correlation_id,
                    key + ":rollup-review",
                    changeset_id,
                    "in_review",
                    f"review verdict {verdict}",
                    None,
                    Kind.CHANGESET,
                )
            else:
                return
        self.transition(
            scope,
            actor,
            correlation_id,
            key + ":rollup",
            changeset_id,
            target,
            f"review verdict {verdict}",
            None,
            Kind.CHANGESET,
        )
        self.emit("changeset.review_rollup", self.store.get(changeset_id, scope), key)
    def delete_record(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        record_id: str,
        *,
        kind: Kind | None = None,
        reason: str = "retention_purge",
    ) -> None:
        """Hard-delete a record in scope (used for automated follow-up retention)."""
        if not key:
            raise ValidationError("Idempotency-Key header is required")
        payload = {"id": record_id, "reason": reason, "kind": kind.value if kind else None}
        prior = self.store.idempotent(scope, "delete:record", key, payload)
        if prior:
            return
        record = self.store.get(record_id, scope)
        if kind and record.kind != kind:
            raise ValidationError("record kind mismatch")
        self.store.delete(record_id, scope)
        self.store.remember(scope, "delete:record", key, payload, record_id)
        self.emit(
            record.kind.value + ".deleted",
            Record(
                record.id,
                record.kind,
                record.scope,
                actor,
                correlation_id,
                "deleted",
                {**record.data, "delete_reason": redact(reason)},
                record.created_at,
                now(),
                record.version,
            ),
            key,
        )

    def create_issue(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> tuple[Record, list[Record]]:
        task_specs = list(payload.get("task_specs") or [])
        if payload.get("severity") == "critical" and not task_specs and not payload.get("escalation_reason"):
            raise ValidationError("critical issues require task_specs or escalation_reason")
        issue = self.create(Kind.ISSUE, scope, actor, correlation_id, key, payload)
        tasks: list[Record] = []
        for index, spec in enumerate(task_specs):
            if not isinstance(spec, dict):
                raise ValidationError("task_specs entries must be objects")
            task_payload = dict(spec)
            task_payload.setdefault("issue_id", issue.id)
            tasks.append(self.create(Kind.TASK, scope, actor, correlation_id, f"{key}:task:{index}", task_payload))
        return issue, tasks

    def transition(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        record_id: str,
        target: str,
        reason: str,
        version: int | None,
        kind: Kind | None = None,
    ) -> Record:
        if not key:
            raise ValidationError("Idempotency-Key header is required")
        payload = {"id": record_id, "target": target, "reason": reason, "version": version, "kind": kind.value if kind else None}
        command = "transition:" + (kind.value if kind else "record")
        prior = self.store.idempotent(scope, command, key, payload)
        if prior:
            return self.store.get(prior, scope)
        record = self.store.get(record_id, scope)
        if kind and record.kind != kind:
            raise ValidationError("record kind mismatch")
        if record.kind not in TRANSITIONS:
            raise ValidationError("record does not support lifecycle transitions")
        if version is not None and record.version != version:
            raise ConflictError(record.kind.value + " version is stale")
        if target not in TRANSITIONS[record.kind].get(record.status, set()):
            raise ConflictError("invalid " + record.kind.value + " state transition")
        old = record.status
        record.status = target
        record.version += 1
        record.updated_at = now()
        record.data["last_transition"] = {"from": old, "to": target, "reason": redact(reason), "at": record.updated_at}
        self.store.put(record)
        self.store.remember(scope, command, key, payload, record.id)
        event_name = {
            Kind.TASK: "task.completed" if target == "done" else "task.state_changed",
            Kind.ISSUE: "issue.state_changed",
            Kind.DECISION: "decision.state_changed",
            Kind.CHANGESET: {
                "open": "changeset.opened",
                "approved": "changeset.approved",
                "changes_requested": "changeset.changes_requested",
                "applied": "changeset.applied",
            }.get(target, "changeset.state_changed"),
        }.get(record.kind, record.kind.value + ".state_changed")
        self.emit(event_name, record, key)
        return record

    def create_changeset(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        payload: dict[str, Any],
    ) -> Record:
        data = dict(payload)
        data.setdefault("author_ref", actor)
        data.setdefault("forbid_self_approval", True)
        return self.create(Kind.CHANGESET, scope, actor, correlation_id, key, data)

    def approve_changeset(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        changeset_id: str,
        *,
        reason: str = "approved",
        version: int | None = None,
    ) -> Record:
        record = self.store.get(changeset_id, scope)
        if record.kind != Kind.CHANGESET:
            raise ValidationError("record is not a changeset")
        if bool(record.data.get("forbid_self_approval", True)) and actor == record.data.get("author_ref"):
            raise ConflictError("self-approval of ChangeSet is forbidden")
        # Normalize into in_review so approve works from draft/open/changes_requested.
        if record.status == "draft":
            self.transition(
                scope, actor, correlation_id, key + ":open", changeset_id, "open", "open for review", None, Kind.CHANGESET
            )
            record = self.store.get(changeset_id, scope)
        if record.status == "changes_requested":
            self.transition(
                scope,
                actor,
                correlation_id,
                key + ":resume",
                changeset_id,
                "in_review",
                "resume review after changes",
                None,
                Kind.CHANGESET,
            )
            record = self.store.get(changeset_id, scope)
        if record.status == "open":
            self.transition(
                scope,
                actor,
                correlation_id,
                key + ":review",
                changeset_id,
                "in_review",
                "start review",
                None,
                Kind.CHANGESET,
            )
        return self.transition(
            scope,
            actor,
            correlation_id,
            key,
            changeset_id,
            "approved",
            reason,
            version,
            Kind.CHANGESET,
        )
    def supersede(self, scope: Scope, actor: str, correlation_id: str, key: str, record_id: str, payload: dict[str, Any]) -> Record:
        if not key:
            raise ValidationError("Idempotency-Key header is required")
        command_payload = {"id": record_id, "payload": redact(payload)}
        prior = self.store.idempotent(scope, "supersede:decision", key, command_payload)
        if prior:
            return self.store.get(prior, scope)
        old = self.store.get(record_id, scope)
        if old.kind != Kind.DECISION or old.status != "active":
            raise ConflictError("only an active decision can be superseded")
        new_payload = dict(payload, status="active", supersedes=record_id)
        new = self.create(Kind.DECISION, scope, actor, correlation_id, key + ":new", new_payload)
        old.status = "superseded"
        old.version += 1
        old.updated_at = now()
        old.data["superseded_by"] = new.id
        self.store.put(old)
        self.store.remember(scope, "supersede:decision", key, command_payload, new.id)
        self.emit("decision.superseded", old, key)
        return new

    def timeline(self, scope: Scope) -> list[Record]:
        return sorted([record for kind in Kind for record in self.store.list(kind, scope)], key=lambda item: (item.created_at, item.id))

    def task_board(self, scope: Scope) -> dict[str, list[dict[str, Any]]]:
        board = {status: [] for status in TRANSITIONS[Kind.TASK]}
        for task in self.store.list(Kind.TASK, scope):
            board.setdefault(task.status, []).append(task.public())
        return board

    def decision_history(self, scope: Scope) -> list[Record]:
        return self.store.list(Kind.DECISION, scope)

    def open_issues(self, scope: Scope) -> list[Record]:
        return [issue for issue in self.store.list(Kind.ISSUE, scope) if issue.status in OPEN_ISSUE_STATES]

    def find_related_work(self, scope: Scope, correlation_id: str | None = None, entity_id: str | None = None) -> list[Record]:
        if not correlation_id and not entity_id:
            raise ValidationError("correlation_id or entity_id is required")
        matches: list[Record] = []
        for record in self.timeline(scope):
            linked = set(record.data.get("linked_entities") or [])
            references = set(record.data.get("evidence_refs") or [])
            issue_id = record.data.get("issue_id")
            supersedes = record.data.get("supersedes")
            if correlation_id and record.correlation_id == correlation_id:
                matches.append(record)
            elif entity_id and entity_id in {record.id, issue_id, supersedes, *linked, *references}:
                matches.append(record)
        return matches

    def evidence_bundle(self, scope: Scope, evidence_ref: str) -> list[Record]:
        if not evidence_ref:
            raise ValidationError("evidence_ref is required")
        return [record for record in self.timeline(scope) if evidence_ref in set(record.data.get("evidence_refs") or [])]

    def emit(self, event_type: str, record: Record, key: str) -> None:
        self.store.event(
            {
                "event_id": str(uuid4()),
                "event_type": event_type,
                "event_version": 1,
                "occurred_at": now(),
                "source": "core-data-service",
                "producer": "core-data-service",
                "tenant_id": record.scope.tenant_id,
                "workspace_id": record.scope.workspace_id,
                "project_id": record.scope.project_id,
                "project_group_id": None,
                "actor_ref": record.actor_id,
                "correlation_id": record.correlation_id,
                "causation_id": record.id,
                "idempotency_key": key,
                "payload": record.public(),
                "evidence_refs": record.data.get("evidence_refs", []),
            }
        )
