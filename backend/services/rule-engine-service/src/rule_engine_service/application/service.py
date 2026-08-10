"""RuleEngineService application use-cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from ..domain.constants import SECRET, SENSITIVE_DOMAINS, TASK_TRIGGERS
from ..domain.enums import (
    ApprovalState,
    EvaluationMode,
    EvaluationState,
    RuleState,
    Severity,
    Verdict,
)
from ..domain.errors import ValidationError
from ..domain.judge import HeuristicJudge, Judge
from ..domain.models import (
    AnomalySignal,
    ApprovalRequest,
    ImpactMap,
    RoutedTask,
    Rule,
    RuleEvaluation,
    RuleFeedback,
    Scope,
)
from ..domain.ports import Store
from ..domain.util import now, sanitize, severity_score


class RuleEngineService:
    def __init__(self, store: Store, judge: Judge | None = None):
        self.store = store
        self.judge = judge or HeuristicJudge()

    def create_rule(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> Rule:
        self._require_key(key)
        payload = sanitize(payload)
        missing = [field for field in ("title", "natural_language_rule", "severity", "owner", "evaluation_mode") if not payload.get(field)]
        if missing:
            raise ValidationError("missing required fields: " + ", ".join(missing))
        try:
            severity = Severity(payload["severity"])
            mode = EvaluationMode(payload["evaluation_mode"])
            state = RuleState(payload.get("state") or RuleState.ACTIVE.value)
        except ValueError as exc:
            raise ValidationError("invalid severity, evaluation_mode, or state") from exc
        command_payload = {
            "title": payload["title"],
            "natural_language_rule": payload["natural_language_rule"],
            "severity": severity.value,
            "owner": payload["owner"],
            "evaluation_mode": mode.value,
            "state": state.value,
            "domain": payload.get("domain") or "engineering",
            "examples": list(payload.get("examples") or []),
            "counterexamples": list(payload.get("counterexamples") or []),
            "match_tags": sorted(set(payload.get("match_tags") or [])),
            "required_approval_role": payload.get("required_approval_role"),
            "precedence": int(payload.get("precedence") or 100),
        }
        prior = self.store.idempotent(scope, "create_rule", key, command_payload)
        if prior:
            return self.store.get_rule(prior, scope)
        timestamp = now()
        rule = Rule(
            str(uuid4()),
            scope,
            actor,
            correlation_id,
            command_payload["title"],
            command_payload["natural_language_rule"],
            severity,
            command_payload["owner"],
            mode,
            state,
            command_payload["domain"],
            command_payload["examples"],
            command_payload["counterexamples"],
            command_payload["match_tags"],
            command_payload["required_approval_role"],
            command_payload["precedence"],
            1,
            timestamp,
            timestamp,
        )
        self.store.put_rule(rule)
        self.store.remember(scope, "create_rule", key, command_payload, rule.id)
        self.emit("RuleCreated", rule.public(), scope, actor, correlation_id, key, rule.id, [])
        return rule

    def update_rule_version(self, scope: Scope, actor: str, correlation_id: str, key: str, rule_id: str, payload: dict[str, Any]) -> Rule:
        self._require_key(key)
        payload = sanitize(payload)
        command_payload = {"rule_id": rule_id, **{k: payload[k] for k in payload}}
        prior = self.store.idempotent(scope, "update_rule_version", key, command_payload)
        if prior:
            return self.store.get_rule(prior, scope)
        rule = self.store.get_rule(rule_id, scope)
        if "natural_language_rule" in payload:
            rule.natural_language_rule = str(payload["natural_language_rule"])
        if "severity" in payload:
            rule.severity = Severity(payload["severity"])
        if "state" in payload:
            rule.state = RuleState(payload["state"])
        if "match_tags" in payload:
            rule.match_tags = sorted(set(payload["match_tags"] or []))
        if "examples" in payload:
            rule.examples = list(payload["examples"] or [])
        if "counterexamples" in payload:
            rule.counterexamples = list(payload["counterexamples"] or [])
        if "evaluation_mode" in payload:
            rule.evaluation_mode = EvaluationMode(payload["evaluation_mode"])
        if "required_approval_role" in payload:
            rule.required_approval_role = payload.get("required_approval_role")
        rule.version += 1
        rule.updated_at = now()
        rule.actor_id = actor
        rule.correlation_id = correlation_id
        self.store.put_rule(rule)
        self.store.remember(scope, "update_rule_version", key, command_payload, rule.id)
        self.emit("RuleUpdated", rule.public(), scope, actor, correlation_id, key, rule.id, [])
        return rule

    def evaluate_rules(self, scope: Scope, actor: str, correlation_id: str, key: str, subject: dict[str, Any], shadow: bool = False) -> dict[str, Any]:
        self._require_key(key)
        subject = sanitize(subject)
        if not subject.get("subject_ref"):
            raise ValidationError("subject_ref is required")
        command_payload = {"subject": subject, "shadow": shadow}
        prior = self.store.idempotent(scope, "evaluate_rules", key, command_payload)
        if prior:
            evaluation_ids = [item for item in prior.split(",") if item]
            evaluations = [self.store.get_evaluation(item_id, scope) for item_id in evaluation_ids]
            return self._replay_evaluation_bundle(scope, subject, evaluations, shadow)

        allowed_states = {RuleState.SHADOW, RuleState.ACTIVE} if shadow else {RuleState.ACTIVE}
        rules = sorted(
            [rule for rule in self.store.list_rules(scope) if rule.state in allowed_states],
            key=lambda item: (-item.precedence, item.created_at, item.id),
        )
        applicable = [rule for rule in rules if self._rule_applies(rule, subject)]
        evaluations: list[RuleEvaluation] = []
        timestamp = now()
        for rule in applicable:
            evaluation = self._evaluate_one(scope, actor, correlation_id, rule, subject, shadow, timestamp)
            self.store.put_evaluation(evaluation)
            evaluations.append(evaluation)
            self.emit("RuleEvaluationCompleted", evaluation.public(), scope, actor, correlation_id, key, evaluation.id, evaluation.evidence_refs)
            if evaluation.verdict in {Verdict.BLOCK, Verdict.ESCALATE} and not shadow:
                self.emit("RuleViolationDetected", evaluation.public(), scope, actor, correlation_id, key, evaluation.id, evaluation.evidence_refs)

        anomalies = self._detect_anomalies(scope, actor, correlation_id, subject, timestamp)
        impact = self._build_impact(scope, subject, timestamp)
        tasks = self._route_tasks(scope, actor, correlation_id, subject, impact, evaluations, timestamp)
        approvals = []
        if not shadow:
            approvals = self._auto_request_approvals(scope, actor, correlation_id, evaluations, timestamp)

        joined = ",".join(item.id for item in evaluations)
        self.store.remember(scope, "evaluate_rules", key, command_payload, joined)
        bundle = self._evaluation_bundle(scope, subject, evaluations, shadow)
        bundle["impact"] = impact.public() if impact else None
        bundle["tasks"] = [task.public() for task in tasks]
        bundle["approvals"] = [item.public() for item in approvals]
        bundle["anomalies"] = [item.public() for item in anomalies]
        return bundle

    def run_shadow(self, scope: Scope, actor: str, correlation_id: str, key: str, subject: dict[str, Any]) -> dict[str, Any]:
        return self.evaluate_rules(scope, actor, correlation_id, key, subject, shadow=True)

    def request_approval(self, scope: Scope, actor: str, correlation_id: str, key: str, evaluation_id: str, approver: str | None = None) -> ApprovalRequest:
        self._require_key(key)
        payload = {"evaluation_id": evaluation_id, "approver": approver}
        prior = self.store.idempotent(scope, "request_approval", key, payload)
        if prior:
            return self.store.get_approval(prior, scope)
        evaluation = self.store.get_evaluation(evaluation_id, scope)
        rule = self.store.get_rule(evaluation.rule_id, scope)
        timestamp = now()
        approval = ApprovalRequest(
            str(uuid4()),
            scope,
            actor,
            correlation_id,
            evaluation.id,
            rule.id,
            approver or rule.required_approval_role or rule.owner,
            ApprovalState.REQUESTED,
            ["approve", "reject", "needs_changes"],
            (datetime.now(UTC) + timedelta(hours=24 if rule.severity != Severity.CRITICAL else 4)).isoformat(),
            None,
            evaluation.evidence_refs,
            timestamp,
            timestamp,
        )
        self.store.put_approval(approval)
        evaluation.state = EvaluationState.ESCALATED
        evaluation.updated_at = timestamp
        self.store.put_evaluation(evaluation)
        self.store.remember(scope, "request_approval", key, payload, approval.id)
        self.emit("ApprovalRequested", approval.public(), scope, actor, correlation_id, key, approval.id, approval.evidence_refs)
        return approval

    def resolve_approval(self, scope: Scope, actor: str, correlation_id: str, key: str, approval_id: str, status: str, reason: str) -> ApprovalRequest:
        self._require_key(key)
        payload = {"approval_id": approval_id, "status": status, "reason": sanitize(reason)}
        prior = self.store.idempotent(scope, "resolve_approval", key, payload)
        if prior:
            return self.store.get_approval(prior, scope)
        approval = self.store.get_approval(approval_id, scope)
        approval.resolve(ApprovalState(status), payload["reason"], now())
        self.store.put_approval(approval)
        self.store.remember(scope, "resolve_approval", key, payload, approval.id)
        self.emit("ApprovalResolved", approval.public(), scope, actor, correlation_id, key, approval.id, approval.evidence_refs)
        return approval

    def route_task(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> RoutedTask:
        self._require_key(key)
        payload = sanitize(payload)
        missing = [field for field in ("subject_ref", "title", "assignee_type", "reason") if not payload.get(field)]
        if missing:
            raise ValidationError("missing required fields: " + ", ".join(missing))
        command_payload = {
            "subject_ref": payload["subject_ref"],
            "title": payload["title"],
            "assignee_type": payload["assignee_type"],
            "reason": payload["reason"],
            "evidence_refs": sorted(set(payload.get("evidence_refs") or [])),
        }
        prior = self.store.idempotent(scope, "route_task", key, command_payload)
        if prior:
            return next(task for task in self.store.list_tasks(scope) if task.id == prior)
        for existing in self.store.list_tasks(scope):
            if existing.subject_ref == command_payload["subject_ref"] and existing.assignee_type == command_payload["assignee_type"]:
                self.store.remember(scope, "route_task", key, command_payload, existing.id)
                return existing
        task = RoutedTask(
            str(uuid4()),
            scope,
            actor,
            correlation_id,
            command_payload["subject_ref"],
            command_payload["title"],
            command_payload["assignee_type"],
            command_payload["reason"],
            command_payload["evidence_refs"],
            now(),
        )
        self.store.put_task(task)
        self.store.remember(scope, "route_task", key, command_payload, task.id)
        self.emit("TaskRouted", task.public(), scope, actor, correlation_id, key, task.id, task.evidence_refs)
        return task

    def record_feedback(self, scope: Scope, actor: str, correlation_id: str, key: str, evaluation_id: str, label: str, note: str) -> RuleFeedback:
        self._require_key(key)
        payload = {"evaluation_id": evaluation_id, "label": sanitize(label), "note": sanitize(note)}
        if payload["label"] not in {"false_positive", "true_positive", "needs_tuning"}:
            raise ValidationError("label must be false_positive, true_positive, or needs_tuning")
        prior = self.store.idempotent(scope, "record_feedback", key, payload)
        if prior:
            return next(item for item in self.store.list_feedback(scope) if item.id == prior)
        self.store.get_evaluation(evaluation_id, scope)
        feedback = RuleFeedback(str(uuid4()), scope, actor, correlation_id, evaluation_id, payload["label"], payload["note"], now())
        self.store.put_feedback(feedback)
        self.store.remember(scope, "record_feedback", key, payload, feedback.id)
        self.emit("RuleFeedbackRecorded", feedback.public(), scope, actor, correlation_id, key, feedback.id, [evaluation_id])
        return feedback

    def explain_decision(self, scope: Scope, evaluation_id: str) -> dict[str, Any]:
        evaluation = self.store.get_evaluation(evaluation_id, scope)
        rule = self.store.get_rule(evaluation.rule_id, scope)
        return {
            "evaluation": evaluation.public(),
            "rule": rule.public(),
            "why_applied": evaluation.rationale,
            "used_llm": evaluation.used_llm,
            "evidence_refs": evaluation.evidence_refs,
        }

    def list_evaluations(self, scope: Scope) -> list[RuleEvaluation]:
        return self.store.list_evaluations(scope)

    def get_approval_queue(self, scope: Scope) -> list[ApprovalRequest]:
        return [item for item in self.store.list_approvals(scope) if item.status == ApprovalState.REQUESTED]

    def list_anomalies(self, scope: Scope) -> list[AnomalySignal]:
        return self.store.list_anomalies(scope)

    def get_rule_health(self, scope: Scope) -> dict[str, Any]:
        rules = self.store.list_rules(scope)
        evaluations = self.store.list_evaluations(scope)
        feedback = self.store.list_feedback(scope)
        return {
            "rule_count": len(rules),
            "active_rules": sum(1 for rule in rules if rule.state == RuleState.ACTIVE),
            "shadow_rules": sum(1 for rule in rules if rule.state == RuleState.SHADOW),
            "evaluation_count": len(evaluations),
            "blocked_or_escalated": sum(1 for item in evaluations if item.verdict in {Verdict.BLOCK, Verdict.ESCALATE}),
            "llm_evaluations": sum(1 for item in evaluations if item.used_llm),
            "feedback_count": len(feedback),
            "open_approvals": len(self.get_approval_queue(scope)),
        }

    def _evaluate_one(self, scope: Scope, actor: str, correlation_id: str, rule: Rule, subject: dict[str, Any], shadow: bool, timestamp: str) -> RuleEvaluation:
        evidence = sorted(set((subject.get("evidence_refs") or []) + [subject["subject_ref"], rule.id]))
        used_llm = False
        judge_replay: dict[str, Any] = {}
        if rule.evaluation_mode == EvaluationMode.MANUAL:
            verdict, confidence, rationale = Verdict.ESCALATE, 1.0, "manual policy always requires human review"
        elif rule.evaluation_mode == EvaluationMode.DETERMINISTIC:
            verdict, confidence, rationale = self._deterministic(rule, subject)
        elif rule.evaluation_mode == EvaluationMode.HYBRID:
            verdict, confidence, rationale = self._deterministic(rule, subject)
            if verdict == Verdict.ALLOW and self._needs_semantic(rule, subject):
                judged = self.judge.judge(rule, subject)
                used_llm = True
                verdict, confidence, rationale = judged.verdict, judged.confidence, judged.rationale
                evidence = sorted(set(evidence + judged.matched_examples))
                judge_replay = dict(judged.replay_metadata or {})
        else:
            judged = self.judge.judge(rule, subject)
            used_llm = True
            verdict, confidence, rationale = judged.verdict, judged.confidence, judged.rationale
            evidence = sorted(set(evidence + judged.matched_examples))
            judge_replay = dict(judged.replay_metadata or {})
            if confidence < 0.7 and rule.severity in {Severity.HIGH, Severity.CRITICAL}:
                verdict, rationale = Verdict.ESCALATE, rationale + "; low-confidence high-risk fallback to escalate"

        if self._is_sensitive(rule, subject) and verdict in {Verdict.BLOCK, Verdict.WARN}:
            verdict = Verdict.ESCALATE
            rationale += "; fail-closed for sensitive domain"

        risk = severity_score(rule.severity)
        if verdict == Verdict.ESCALATE:
            risk = max(risk, 0.9)
        state = {
            Verdict.ALLOW: EvaluationState.PASSED,
            Verdict.WARN: EvaluationState.PASSED,
            Verdict.BLOCK: EvaluationState.FAILED,
            Verdict.ESCALATE: EvaluationState.ESCALATED,
        }[verdict]
        return RuleEvaluation(
            str(uuid4()),
            scope,
            actor,
            correlation_id,
            rule.id,
            subject["subject_ref"],
            verdict,
            confidence,
            rationale,
            evidence,
            used_llm,
            state,
            shadow,
            risk,
            timestamp,
            timestamp,
            judge_replay=judge_replay,
        )

    def _deterministic(self, rule: Rule, subject: dict[str, Any]) -> tuple[Verdict, float, str]:
        tags = {tag.lower() for tag in subject.get("tags") or []}
        paths = " ".join(subject.get("paths") or []).lower()
        summary = str(subject.get("summary") or "").lower()
        trust_level = str(subject.get("agent_trust_level") or subject.get("trust_level") or "standard")
        try:
            from architecture_governance import provider_rank, trust_allows_high_risk

            if (rule.domain in SENSITIVE_DOMAINS or tags & SENSITIVE_DOMAINS) and not trust_allows_high_risk(
                trust_level
            ):
                provider = str(subject.get("provider") or subject.get("vendor") or trust_level)
                try:
                    rank = provider_rank(provider)
                except Exception:
                    try:
                        rank = provider_rank(trust_level)
                    except Exception:
                        rank = -1
                return (
                    Verdict.ESCALATE,
                    1.0,
                    (
                        f"trust level {trust_level!r} below high-risk floor for '{rule.title}' "
                        f"(provider_rank={rank}) — require approval"
                    ),
                )
        except Exception:
            pass
        matched = bool(set(rule.match_tags) & tags) or any(tag in paths or tag in summary for tag in rule.match_tags)
        if not matched and rule.domain not in tags:
            return Verdict.ALLOW, 0.95, f"deterministic pre-check: rule '{rule.title}' not applicable"
        if SECRET.search(summary) or "secret" in tags:
            return Verdict.BLOCK, 1.0, f"deterministic pre-check blocked secret-bearing change for '{rule.title}'"
        if rule.domain in SENSITIVE_DOMAINS or tags & SENSITIVE_DOMAINS:
            return Verdict.BLOCK, 0.98, f"deterministic pre-check blocked sensitive change for '{rule.title}'"
        if tags & TASK_TRIGGERS:
            return Verdict.WARN, 0.9, f"deterministic pre-check warned for contract-impacting change under '{rule.title}'"
        return Verdict.ALLOW, 0.9, f"deterministic pre-check allowed change under '{rule.title}'"

    def _needs_semantic(self, rule: Rule, subject: dict[str, Any]) -> bool:
        tags = set(subject.get("tags") or [])
        return bool(tags & {"ambiguous", "refactor", "semantic"}) or rule.domain in {"compliance", "security"}

    def _is_sensitive(self, rule: Rule, subject: dict[str, Any]) -> bool:
        tags = set(subject.get("tags") or [])
        return rule.domain in SENSITIVE_DOMAINS or bool(tags & SENSITIVE_DOMAINS)

    def _rule_applies(self, rule: Rule, subject: dict[str, Any]) -> bool:
        tags = {tag.lower() for tag in subject.get("tags") or []}
        if not rule.match_tags:
            return True
        return bool(set(rule.match_tags) & tags) or rule.domain in tags

    def _detect_anomalies(self, scope: Scope, actor: str, correlation_id: str, subject: dict[str, Any], timestamp: str) -> list[AnomalySignal]:
        anomalies: list[AnomalySignal] = []
        paths = subject.get("paths") or []
        if len(paths) >= 8:
            anomaly = AnomalySignal(
                str(uuid4()),
                scope,
                actor,
                correlation_id,
                subject["subject_ref"],
                "unusually_many_files",
                min(1.0, len(paths) / 20),
                f"change touches {len(paths)} files",
                [subject["subject_ref"]],
                timestamp,
            )
            self.store.put_anomaly(anomaly)
            self.emit("AnomalyDetected", anomaly.public(), scope, actor, correlation_id, "", anomaly.id, anomaly.evidence_refs)
            anomalies.append(anomaly)
        tags = set(subject.get("tags") or [])
        if tags & SENSITIVE_DOMAINS and not subject.get("linked_task"):
            anomaly = AnomalySignal(
                str(uuid4()),
                scope,
                actor,
                correlation_id,
                subject["subject_ref"],
                "high_risk_without_task",
                0.8,
                "sensitive change without linked task",
                [subject["subject_ref"]],
                timestamp,
            )
            self.store.put_anomaly(anomaly)
            self.emit("AnomalyDetected", anomaly.public(), scope, actor, correlation_id, "", anomaly.id, anomaly.evidence_refs)
            anomalies.append(anomaly)
        return anomalies

    def _build_impact(self, scope: Scope, subject: dict[str, Any], timestamp: str) -> ImpactMap | None:
        tags = {tag.lower() for tag in subject.get("tags") or []}
        change_type = str(subject.get("change_type") or "").lower()
        affected: list[dict[str, Any]] = []
        if tags & {"api", "route", "contract"} or change_type == "api":
            affected.extend(
                [
                    {"entity": "frontend_clients", "relation": "depends_on", "confidence": 0.9},
                    {"entity": "mobile_clients", "relation": "depends_on", "confidence": 0.85},
                    {"entity": "api_docs", "relation": "explains", "confidence": 0.8},
                    {"entity": "contract_tests", "relation": "implements", "confidence": 0.88},
                ]
            )
        if tags & {"schema", "migration"} or change_type == "schema":
            affected.extend(
                [
                    {"entity": "dashboards", "relation": "depends_on", "confidence": 0.84},
                    {"entity": "migration_verification", "relation": "implements", "confidence": 0.9},
                    {"entity": "data_docs", "relation": "explains", "confidence": 0.75},
                ]
            )
        if not affected:
            return None
        risk = Severity.HIGH if tags & SENSITIVE_DOMAINS else Severity.MEDIUM
        impact = ImpactMap(str(uuid4()), scope, subject["subject_ref"], affected, risk, [], min(item["confidence"] for item in affected), timestamp)
        self.store.put_impact(impact)
        self.emit("ImpactMapCreated", impact.public(), scope, "system", subject.get("correlation_id") or "", "", impact.id, [subject["subject_ref"]])
        return impact

    def _route_tasks(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        subject: dict[str, Any],
        impact: ImpactMap | None,
        evaluations: list[RuleEvaluation],
        timestamp: str,
    ) -> list[RoutedTask]:
        if impact is None:
            return []
        blocked = any(item.verdict in {Verdict.BLOCK, Verdict.ESCALATE} and not item.shadow for item in evaluations)
        # Still generate downstream tasks for API/schema changes even when blocked — work must be planned.
        routes = {
            "frontend_clients": ("frontend", "Update frontend clients for API/schema change"),
            "mobile_clients": ("mobile", "Update mobile clients for API change"),
            "api_docs": ("docs", "Update API documentation"),
            "contract_tests": ("qa", "Update contract tests"),
            "dashboards": ("data", "Update dashboards for schema change"),
            "migration_verification": ("backend", "Verify data migration"),
            "data_docs": ("docs", "Update data documentation"),
        }
        tasks: list[RoutedTask] = []
        task_refs: list[str] = []
        for entity in impact.affected_entities:
            if entity["confidence"] < 0.8:
                continue
            assignee, title = routes.get(entity["entity"], ("platform", f"Review impact on {entity['entity']}"))
            existing = next(
                (task for task in self.store.list_tasks(scope) if task.subject_ref == subject["subject_ref"] and task.assignee_type == assignee),
                None,
            )
            if existing:
                tasks.append(existing)
                task_refs.append(existing.id)
                continue
            task = RoutedTask(
                str(uuid4()),
                scope,
                actor,
                correlation_id,
                subject["subject_ref"],
                title,
                assignee,
                f"impact:{entity['relation']}; blocked={blocked}",
                [subject["subject_ref"], impact.id],
                timestamp,
            )
            self.store.put_task(task)
            self.emit("TaskRouted", task.public(), scope, actor, correlation_id, "", task.id, task.evidence_refs)
            tasks.append(task)
            task_refs.append(task.id)
        impact.generated_task_refs = task_refs
        self.store.put_impact(impact)
        return tasks

    def _auto_request_approvals(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        evaluations: list[RuleEvaluation],
        timestamp: str,
    ) -> list[ApprovalRequest]:
        approvals: list[ApprovalRequest] = []
        try:
            from approval_modes import decide_route, resolve_effective_mode

            mode_profile = resolve_effective_mode()
        except Exception:  # noqa: BLE001 — fail closed to human queue
            mode_profile = {"mode": "manual"}
            decide_route = None  # type: ignore[assignment]

        for evaluation in evaluations:
            if evaluation.verdict != Verdict.ESCALATE:
                continue
            rule = self.store.get_rule(evaluation.rule_id, scope)
            risk_level = rule.severity.value
            subject_class = rule.domain or (rule.match_tags[0] if rule.match_tags else "")
            route = "human"
            route_reason = "mode unavailable; fail closed"
            if decide_route is not None:
                decision = decide_route(
                    subject_class=subject_class,
                    risk_level=risk_level,
                    profile=mode_profile,
                )
                route = decision.route
                route_reason = decision.reason
            status = ApprovalState.APPROVED if route == "auto" else ApprovalState.REQUESTED
            approval = ApprovalRequest(
                str(uuid4()),
                scope,
                actor,
                correlation_id,
                evaluation.id,
                rule.id,
                rule.required_approval_role or rule.owner,
                status,
                ["approve", "reject", "needs_changes"],
                (datetime.now(UTC) + timedelta(hours=4 if rule.severity == Severity.CRITICAL else 24)).isoformat(),
                route_reason if route == "auto" else None,
                evaluation.evidence_refs,
                timestamp,
                timestamp,
            )
            self.store.put_approval(approval)
            event = "ApprovalResolved" if route == "auto" else "ApprovalRequested"
            self.emit(event, approval.public(), scope, actor, correlation_id, "", approval.id, approval.evidence_refs)
            approvals.append(approval)
        return approvals

    def _evaluation_bundle(self, scope: Scope, subject: dict[str, Any], evaluations: list[RuleEvaluation], shadow: bool) -> dict[str, Any]:
        final = Verdict.ALLOW
        for evaluation in evaluations:
            if evaluation.verdict == Verdict.ESCALATE:
                final = Verdict.ESCALATE
                break
            if evaluation.verdict == Verdict.BLOCK and final != Verdict.ESCALATE:
                final = Verdict.BLOCK
            elif evaluation.verdict == Verdict.WARN and final == Verdict.ALLOW:
                final = Verdict.WARN
        return {
            "subject_ref": subject["subject_ref"],
            "shadow": shadow,
            "final_verdict": final.value,
            "blocked": final in {Verdict.BLOCK, Verdict.ESCALATE} and not shadow,
            "evaluations": [item.public() for item in evaluations],
        }

    def _replay_evaluation_bundle(
        self, scope: Scope, subject: dict[str, Any], evaluations: list[RuleEvaluation], shadow: bool
    ) -> dict[str, Any]:
        """Rebuild full evaluate response on idempotent retry (impact/tasks/approvals)."""
        bundle = self._evaluation_bundle(scope, subject, evaluations, shadow)
        subject_ref = subject["subject_ref"]
        impacts = [item for item in self.store.list_impacts(scope) if item.change_ref == subject_ref]
        evaluation_ids = {item.id for item in evaluations}
        bundle["impact"] = impacts[-1].public() if impacts else None
        bundle["tasks"] = [item.public() for item in self.store.list_tasks(scope) if item.subject_ref == subject_ref]
        bundle["approvals"] = [
            item.public() for item in self.store.list_approvals(scope) if item.evaluation_id in evaluation_ids
        ]
        bundle["anomalies"] = [
            item.public() for item in self.store.list_anomalies(scope) if item.subject_ref == subject_ref
        ]
        return bundle

    def _require_key(self, key: str) -> None:
        if not key:
            raise ValidationError("Idempotency-Key header is required")

    def emit(self, event_type: str, payload: dict[str, Any], scope: Scope, actor: str, correlation_id: str, key: str, causation_id: str, evidence_refs: list[str]) -> None:
        self.store.event(
            {
                "event_id": str(uuid4()),
                "event_type": event_type,
                "event_version": 1,
                "occurred_at": now(),
                "producer": "rule-engine-service",
                "tenant_id": scope.tenant_id,
                "workspace_id": scope.workspace_id,
                "project_id": scope.project_id,
                "project_group_id": scope.project_group_id,
                "actor_ref": actor,
                "correlation_id": correlation_id,
                "causation_id": causation_id,
                "idempotency_key": key,
                "payload": payload,
                "evidence_refs": evidence_refs,
            }
        )
