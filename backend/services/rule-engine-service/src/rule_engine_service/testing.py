from __future__ import annotations

from copy import deepcopy
from typing import Any

from .core import (
    AnomalySignal,
    ApprovalRequest,
    ConflictError,
    ImpactMap,
    NotFoundError,
    RoutedTask,
    Rule,
    RuleEvaluation,
    RuleFeedback,
    Scope,
    digest,
)


class InMemoryStore:
    """Deterministic Store fake for unit and transport-contract tests."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}
        self._evaluations: dict[str, RuleEvaluation] = {}
        self._approvals: dict[str, ApprovalRequest] = {}
        self._tasks: dict[str, RoutedTask] = {}
        self._anomalies: dict[str, AnomalySignal] = {}
        self._feedback: dict[str, RuleFeedback] = {}
        self._impacts: dict[str, ImpactMap] = {}
        self._idempotency: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._events: list[dict[str, Any]] = []

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id, scope.project_group_id or ""))

    @staticmethod
    def _same_project(left: Scope, right: Scope) -> bool:
        return (left.tenant_id, left.workspace_id, left.project_id) == (right.tenant_id, right.workspace_id, right.project_id)

    def get_rule(self, rule_id: str, scope: Scope) -> Rule:
        item = self._rules.get(rule_id)
        if item is None or not self._same_project(item.scope, scope):
            raise NotFoundError("rule not found in project scope")
        return deepcopy(item)

    def put_rule(self, rule: Rule) -> None:
        self._rules[rule.id] = deepcopy(rule)

    def list_rules(self, scope: Scope) -> list[Rule]:
        items = [item for item in self._rules.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def get_evaluation(self, evaluation_id: str, scope: Scope) -> RuleEvaluation:
        item = self._evaluations.get(evaluation_id)
        if item is None or not self._same_project(item.scope, scope):
            raise NotFoundError("evaluation not found in project scope")
        return deepcopy(item)

    def put_evaluation(self, evaluation: RuleEvaluation) -> None:
        self._evaluations[evaluation.id] = deepcopy(evaluation)

    def list_evaluations(self, scope: Scope) -> list[RuleEvaluation]:
        items = [item for item in self._evaluations.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def get_approval(self, approval_id: str, scope: Scope) -> ApprovalRequest:
        item = self._approvals.get(approval_id)
        if item is None or not self._same_project(item.scope, scope):
            raise NotFoundError("approval not found in project scope")
        return deepcopy(item)

    def put_approval(self, approval: ApprovalRequest) -> None:
        self._approvals[approval.id] = deepcopy(approval)

    def list_approvals(self, scope: Scope) -> list[ApprovalRequest]:
        items = [item for item in self._approvals.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def put_task(self, task: RoutedTask) -> None:
        self._tasks[task.id] = deepcopy(task)

    def list_tasks(self, scope: Scope) -> list[RoutedTask]:
        items = [item for item in self._tasks.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def put_anomaly(self, anomaly: AnomalySignal) -> None:
        self._anomalies[anomaly.id] = deepcopy(anomaly)

    def list_anomalies(self, scope: Scope) -> list[AnomalySignal]:
        items = [item for item in self._anomalies.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def put_feedback(self, feedback: RuleFeedback) -> None:
        self._feedback[feedback.id] = deepcopy(feedback)

    def list_feedback(self, scope: Scope) -> list[RuleFeedback]:
        items = [item for item in self._feedback.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def put_impact(self, impact: ImpactMap) -> None:
        self._impacts[impact.id] = deepcopy(impact)

    def list_impacts(self, scope: Scope) -> list[ImpactMap]:
        items = [item for item in self._impacts.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

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
