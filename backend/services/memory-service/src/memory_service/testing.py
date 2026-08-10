from __future__ import annotations

from copy import deepcopy
from typing import Any

from .core import (
    ConflictError,
    MemoryItem,
    NotFoundError,
    QuestionMemory,
    Scope,
    WorkBatch,
    digest,
)


class InMemoryStore:
    """Deterministic Store fake for unit and transport-contract tests."""

    def __init__(self) -> None:
        self._memory: dict[str, MemoryItem] = {}
        self._questions: dict[str, QuestionMemory] = {}
        self._batches: dict[str, WorkBatch] = {}
        self._idempotency: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._events: list[dict[str, Any]] = []

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id, scope.project_group_id or ""))

    @staticmethod
    def _same_project(left: Scope, right: Scope) -> bool:
        return (left.tenant_id, left.workspace_id, left.project_id) == (right.tenant_id, right.workspace_id, right.project_id)

    def get_memory(self, memory_id: str, scope: Scope) -> MemoryItem:
        item = self._memory.get(memory_id)
        if item is None or not self._same_project(item.scope, scope):
            raise NotFoundError("memory item not found in project scope")
        return deepcopy(item)

    def put_memory(self, item: MemoryItem) -> None:
        self._memory[item.id] = deepcopy(item)

    def list_memory(self, scope: Scope) -> list[MemoryItem]:
        items = [item for item in self._memory.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def get_question(self, question_id: str, scope: Scope) -> QuestionMemory:
        question = self._questions.get(question_id)
        if question is None or not self._same_project(question.scope, scope):
            raise NotFoundError("question memory not found in project scope")
        return deepcopy(question)

    def find_question(self, normalized: str, scope: Scope) -> QuestionMemory | None:
        for question in self._questions.values():
            if question.normalized_question == normalized and self._same_project(question.scope, scope):
                return deepcopy(question)
        return None

    def put_question(self, question: QuestionMemory) -> None:
        self._questions[question.id] = deepcopy(question)

    def list_questions(self, scope: Scope) -> list[QuestionMemory]:
        questions = [item for item in self._questions.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(questions, key=lambda item: (-item.observations, item.updated_at, item.id), reverse=False))

    def get_batch(self, batch_id: str, scope: Scope) -> WorkBatch:
        batch = self._batches.get(batch_id)
        if batch is None or not self._same_project(batch.scope, scope):
            raise NotFoundError("work batch not found in project scope")
        return deepcopy(batch)

    def put_batch(self, batch: WorkBatch) -> None:
        self._batches[batch.id] = deepcopy(batch)

    def list_batches(self, scope: Scope) -> list[WorkBatch]:
        batches = [item for item in self._batches.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(batches, key=lambda item: (item.created_at, item.id)))

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
