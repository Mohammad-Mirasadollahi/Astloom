from __future__ import annotations

from copy import deepcopy
from typing import Any

from .core import ConflictError, Kind, NotFoundError, Record, Scope, digest


class InMemoryStore:
    """Deterministic Store fake for unit and transport-contract tests."""

    def __init__(self) -> None:
        self._records: dict[str, Record] = {}
        self._idempotency: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._events: list[dict[str, Any]] = []

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id))

    def get(self, record_id: str, scope: Scope) -> Record:
        record = self._records.get(record_id)
        if record is None or record.scope != scope:
            raise NotFoundError("record not found in project scope")
        return deepcopy(record)

    def list(self, kind: Kind, scope: Scope) -> list[Record]:
        records = [record for record in self._records.values() if record.kind == kind and record.scope == scope]
        return deepcopy(sorted(records, key=lambda item: (item.created_at, item.id)))

    def put(self, record: Record) -> None:
        self._records[record.id] = deepcopy(record)

    def delete(self, record_id: str, scope: Scope) -> None:
        record = self._records.get(record_id)
        if record is None or record.scope != scope:
            raise NotFoundError("record not found in project scope")
        del self._records[record_id]

    def idempotent(self, scope: Scope, command: str, key: str, payload: dict[str, Any]) -> str | None:
        remembered = self._idempotency.get((self._scope_key(scope), command, key))
        if remembered is None:
            return None
        fingerprint, record_id = remembered
        if fingerprint != digest(payload):
            raise ConflictError("idempotency key was reused with a different payload")
        return record_id

    def remember(self, scope: Scope, command: str, key: str, payload: dict[str, Any], record_id: str) -> None:
        self._idempotency[(self._scope_key(scope), command, key)] = (digest(payload), record_id)

    def event(self, payload: dict[str, Any]) -> None:
        self._events.append(deepcopy(payload))

    def outbox(self) -> list[dict[str, Any]]:
        return deepcopy(sorted(self._events, key=lambda event: (event["occurred_at"], event["event_id"])))
