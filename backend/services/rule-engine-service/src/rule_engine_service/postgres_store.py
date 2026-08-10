"""
Module contract: PostgreSQL Store adapter for rule-engine durability.
Role: Persist rules, evaluations (incl. judge_replay), approvals, outbox under rule_engine schema.
SoT: migrations under migrations/; domain models in domain/models.py.
Allowed failure: connection/psycopg errors raise; missing rows → NotFoundError.
Forbidden: silent drop of judge_replay or outbox events; cross-project reads.
"""

from __future__ import annotations

from typing import Any

from .core import (
    AnomalySignal,
    ApprovalRequest,
    ApprovalState,
    ConflictError,
    EvaluationMode,
    EvaluationState,
    ImpactMap,
    NotFoundError,
    RoutedTask,
    Rule,
    RuleEvaluation,
    RuleFeedback,
    RuleState,
    Scope,
    Severity,
    Verdict,
    digest,
)


def _timestamp(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


class PostgresStore:
    """PostgreSQL adapter for the Rule Engine Store port."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Rule Engine database URL must use PostgreSQL")
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgreSQL persistence") from exc
        normalized_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self._connection = psycopg.connect(normalized_url, autocommit=True, row_factory=dict_row)
        self._json = Jsonb

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id, scope.project_group_id or ""))

    def _rule(self, row: dict[str, Any], scope: Scope) -> Rule:
        return Rule(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["title"], row["natural_language_rule"],
            Severity(row["severity"]), row["owner"], EvaluationMode(row["evaluation_mode"]), RuleState(row["state"]),
            row["domain"], row["examples"], row["counterexamples"], row["match_tags"], row["required_approval_role"],
            row["precedence"], row["version"], _timestamp(row["created_at"]), _timestamp(row["updated_at"]),
        )

    def _evaluation(self, row: dict[str, Any], scope: Scope) -> RuleEvaluation:
        return RuleEvaluation(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["rule_id"], row["subject_ref"],
            Verdict(row["verdict"]), row["confidence"], row["rationale"], row["evidence_refs"], row["used_llm"],
            EvaluationState(row["state"]), row["shadow"], row["risk_score"], _timestamp(row["created_at"]),
            _timestamp(row["updated_at"]), row["version"],
            judge_replay=dict(row.get("judge_replay") or {}),
        )

    def _approval(self, row: dict[str, Any], scope: Scope) -> ApprovalRequest:
        return ApprovalRequest(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["evaluation_id"], row["rule_id"],
            row["approver"], ApprovalState(row["status"]), row["options"], _timestamp(row["deadline"]),
            row["decision_reason"], row["evidence_refs"], _timestamp(row["created_at"]),
            _timestamp(row["updated_at"]), row["version"],
        )

    def _task(self, row: dict[str, Any], scope: Scope) -> RoutedTask:
        return RoutedTask(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["subject_ref"], row["title"],
            row["assignee_type"], row["reason"], row["evidence_refs"], _timestamp(row["created_at"]),
        )

    def _anomaly(self, row: dict[str, Any], scope: Scope) -> AnomalySignal:
        return AnomalySignal(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["subject_ref"], row["signal_type"],
            row["score"], row["rationale"], row["evidence_refs"], _timestamp(row["created_at"]),
        )

    def _feedback(self, row: dict[str, Any], scope: Scope) -> RuleFeedback:
        return RuleFeedback(
            row["id"], scope, row["actor_id"], row["correlation_id"], row["evaluation_id"], row["label"],
            row["note"], _timestamp(row["created_at"]),
        )

    def _impact(self, row: dict[str, Any], scope: Scope) -> ImpactMap:
        return ImpactMap(
            row["id"], scope, row["change_ref"], row["affected_entities"], Severity(row["risk_level"]),
            row["generated_task_refs"], row["confidence"], _timestamp(row["created_at"]),
        )

    def get_rule(self, rule_id: str, scope: Scope) -> Rule:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM rule_engine.rules WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (rule_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("rule not found in project scope")
        return self._rule(row, scope)

    def put_rule(self, rule: Rule) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO rule_engine.rules
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,title,
                    natural_language_rule,severity,owner,evaluation_mode,state,domain,examples,counterexamples,
                    match_tags,required_approval_role,precedence,version,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET natural_language_rule=EXCLUDED.natural_language_rule,
                   severity=EXCLUDED.severity,state=EXCLUDED.state,examples=EXCLUDED.examples,
                   counterexamples=EXCLUDED.counterexamples,match_tags=EXCLUDED.match_tags,
                   evaluation_mode=EXCLUDED.evaluation_mode,required_approval_role=EXCLUDED.required_approval_role,
                   precedence=EXCLUDED.precedence,version=EXCLUDED.version,updated_at=EXCLUDED.updated_at""",
                (rule.id, rule.scope.tenant_id, rule.scope.workspace_id, rule.scope.project_id, rule.scope.project_group_id,
                 rule.actor_id, rule.correlation_id, rule.title, rule.natural_language_rule, rule.severity.value,
                 rule.owner, rule.evaluation_mode.value, rule.state.value, rule.domain, self._json(rule.examples),
                 self._json(rule.counterexamples), self._json(rule.match_tags), rule.required_approval_role,
                 rule.precedence, rule.version, rule.created_at, rule.updated_at),
            )

    def list_rules(self, scope: Scope) -> list[Rule]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM rule_engine.rules WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._rule(row, scope) for row in cursor.fetchall()]

    def get_evaluation(self, evaluation_id: str, scope: Scope) -> RuleEvaluation:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM rule_engine.evaluations WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (evaluation_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("evaluation not found in project scope")
        return self._evaluation(row, scope)

    def put_evaluation(self, evaluation: RuleEvaluation) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO rule_engine.evaluations
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,rule_id,subject_ref,
                    verdict,confidence,rationale,evidence_refs,used_llm,state,shadow,risk_score,version,created_at,updated_at,
                    judge_replay)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET verdict=EXCLUDED.verdict,confidence=EXCLUDED.confidence,
                   rationale=EXCLUDED.rationale,state=EXCLUDED.state,version=EXCLUDED.version,updated_at=EXCLUDED.updated_at,
                   judge_replay=EXCLUDED.judge_replay""",
                (evaluation.id, evaluation.scope.tenant_id, evaluation.scope.workspace_id, evaluation.scope.project_id,
                 evaluation.scope.project_group_id, evaluation.actor_id, evaluation.correlation_id, evaluation.rule_id,
                 evaluation.subject_ref, evaluation.verdict.value, evaluation.confidence, evaluation.rationale,
                 self._json(evaluation.evidence_refs), evaluation.used_llm, evaluation.state.value, evaluation.shadow,
                 evaluation.risk_score, evaluation.version, evaluation.created_at, evaluation.updated_at,
                 self._json(evaluation.judge_replay)),
            )

    def list_evaluations(self, scope: Scope) -> list[RuleEvaluation]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM rule_engine.evaluations WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._evaluation(row, scope) for row in cursor.fetchall()]

    def get_approval(self, approval_id: str, scope: Scope) -> ApprovalRequest:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM rule_engine.approvals WHERE id=%s AND tenant_id=%s
                   AND workspace_id=%s AND project_id=%s""",
                (approval_id, scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise NotFoundError("approval not found in project scope")
        return self._approval(row, scope)

    def put_approval(self, approval: ApprovalRequest) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO rule_engine.approvals
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,evaluation_id,rule_id,
                    approver,status,options,deadline,decision_reason,evidence_refs,version,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status,decision_reason=EXCLUDED.decision_reason,
                   version=EXCLUDED.version,updated_at=EXCLUDED.updated_at""",
                (approval.id, approval.scope.tenant_id, approval.scope.workspace_id, approval.scope.project_id,
                 approval.scope.project_group_id, approval.actor_id, approval.correlation_id, approval.evaluation_id,
                 approval.rule_id, approval.approver, approval.status.value, self._json(approval.options),
                 approval.deadline, approval.decision_reason, self._json(approval.evidence_refs), approval.version,
                 approval.created_at, approval.updated_at),
            )

    def list_approvals(self, scope: Scope) -> list[ApprovalRequest]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM rule_engine.approvals WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._approval(row, scope) for row in cursor.fetchall()]

    def put_task(self, task: RoutedTask) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO rule_engine.routed_tasks
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,subject_ref,title,
                    assignee_type,reason,evidence_refs,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (task.id, task.scope.tenant_id, task.scope.workspace_id, task.scope.project_id, task.scope.project_group_id,
                 task.actor_id, task.correlation_id, task.subject_ref, task.title, task.assignee_type, task.reason,
                 self._json(task.evidence_refs), task.created_at),
            )

    def list_tasks(self, scope: Scope) -> list[RoutedTask]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM rule_engine.routed_tasks WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._task(row, scope) for row in cursor.fetchall()]

    def put_anomaly(self, anomaly: AnomalySignal) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO rule_engine.anomalies
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,subject_ref,
                    signal_type,score,rationale,evidence_refs,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (anomaly.id, anomaly.scope.tenant_id, anomaly.scope.workspace_id, anomaly.scope.project_id,
                 anomaly.scope.project_group_id, anomaly.actor_id, anomaly.correlation_id, anomaly.subject_ref,
                 anomaly.signal_type, anomaly.score, anomaly.rationale, self._json(anomaly.evidence_refs), anomaly.created_at),
            )

    def list_anomalies(self, scope: Scope) -> list[AnomalySignal]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM rule_engine.anomalies WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._anomaly(row, scope) for row in cursor.fetchall()]

    def put_feedback(self, feedback: RuleFeedback) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO rule_engine.feedback
                   (id,tenant_id,workspace_id,project_id,project_group_id,actor_id,correlation_id,evaluation_id,
                    label,note,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (feedback.id, feedback.scope.tenant_id, feedback.scope.workspace_id, feedback.scope.project_id,
                 feedback.scope.project_group_id, feedback.actor_id, feedback.correlation_id, feedback.evaluation_id,
                 feedback.label, feedback.note, feedback.created_at),
            )

    def list_feedback(self, scope: Scope) -> list[RuleFeedback]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM rule_engine.feedback WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._feedback(row, scope) for row in cursor.fetchall()]

    def put_impact(self, impact: ImpactMap) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO rule_engine.impact_maps
                   (id,tenant_id,workspace_id,project_id,project_group_id,change_ref,affected_entities,risk_level,
                    generated_task_refs,confidence,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET generated_task_refs=EXCLUDED.generated_task_refs,
                   affected_entities=EXCLUDED.affected_entities""",
                (impact.id, impact.scope.tenant_id, impact.scope.workspace_id, impact.scope.project_id,
                 impact.scope.project_group_id, impact.change_ref, self._json(impact.affected_entities),
                 impact.risk_level.value, self._json(impact.generated_task_refs), impact.confidence, impact.created_at),
            )

    def list_impacts(self, scope: Scope) -> list[ImpactMap]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM rule_engine.impact_maps WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s
                   ORDER BY created_at,id""",
                (scope.tenant_id, scope.workspace_id, scope.project_id),
            )
            return [self._impact(row, scope) for row in cursor.fetchall()]

    def idempotent(self, scope: Scope, command: str, key: str, payload: dict[str, Any]) -> str | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT fingerprint,record_id FROM rule_engine.idempotency
                   WHERE scope_key=%s AND command=%s AND idempotency_key=%s""",
                (self._scope_key(scope), command, key),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        if row["fingerprint"] != digest(payload):
            raise ConflictError("idempotency key was reused with a different payload")
        return row["record_id"]

    def remember(self, scope: Scope, command: str, key: str, payload: dict[str, Any], record_id: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO rule_engine.idempotency
                   (scope_key,command,idempotency_key,fingerprint,record_id) VALUES (%s,%s,%s,%s,%s)""",
                (self._scope_key(scope), command, key, digest(payload), record_id),
            )

    def event(self, payload: dict[str, Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO rule_engine.outbox (event_id,event_type,payload,occurred_at) VALUES (%s,%s,%s,%s)",
                (payload["event_id"], payload["event_type"], self._json(payload), payload["occurred_at"]),
            )

    def outbox(self) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM rule_engine.outbox ORDER BY occurred_at,event_id")
            return [row["payload"] for row in cursor.fetchall()]

    def close(self) -> None:
        self._connection.close()
