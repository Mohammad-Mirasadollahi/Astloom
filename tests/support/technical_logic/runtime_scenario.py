from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .checks import _ensure_paths

_SUPPORT = Path(__file__).resolve().parents[1]
if str(_SUPPORT) not in sys.path:
    sys.path.insert(0, str(_SUPPORT))

from synthetic_workflow import generate_workflow  # noqa: E402


@dataclass
class RuntimeScenarioReport:
    scenario_id: str
    status: str
    correlation_id: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "status": self.status,
            "correlation_id": self.correlation_id,
            "steps": self.steps,
            "evidence_refs": self.evidence_refs,
            "passed": self.status == "passed",
        }


def run_runtime_scenario(correlation_id: str = "corr-technical-logic-runtime") -> RuntimeScenarioReport:
    """
    Stitch Phases 1 through 5 in-process:

    activity/worklog/decision/issue/task -> memory -> docs drift -> rules escalate -> broker department tasks

    Payloads come from ``generate_workflow(seed=0)`` (GAP-T08).
    """
    _ensure_paths()
    from core_data_service.core import CoreData, Kind
    from core_data_service.core import Scope as CoreScope
    from core_data_service.testing import InMemoryStore as CoreStore
    from memory_service.core import MemoryService
    from memory_service.core import Scope as MemoryScope
    from memory_service.testing import InMemoryStore as MemoryStore
    from docs_sync_service.core import DocsSyncService
    from docs_sync_service.core import Scope as DocsScope
    from docs_sync_service.testing import InMemoryStore as DocsStore
    from rule_engine_service.core import RuleEngineService
    from rule_engine_service.core import Scope as RulesScope
    from rule_engine_service.testing import InMemoryStore as RulesStore
    from adapter_service.core import AdapterService
    from adapter_service.core import Scope as AdapterScope
    from adapter_service.testing import InMemoryStore as AdapterStore

    wf = generate_workflow(0, correlation_id=correlation_id)
    steps: list[dict[str, Any]] = []
    evidence: list[str] = []
    actor = wf.actor

    core = CoreData(CoreStore())
    core_scope = CoreScope(wf.scope.tenant_id, wf.scope.workspace_id, wf.scope.project_id)
    activity = core.create(
        Kind.ACTIVITY,
        core_scope,
        actor,
        correlation_id,
        "rt-activity",
        dict(wf.activity),
    )
    worklog = core.create(
        Kind.WORK_LOG,
        core_scope,
        actor,
        correlation_id,
        "rt-worklog",
        dict(wf.worklog),
    )
    decision = core.create(
        Kind.DECISION,
        core_scope,
        actor,
        correlation_id,
        "rt-decision",
        dict(wf.decision),
    )
    issue_payload = dict(wf.issue)
    issue_payload["evidence_refs"] = list(
        dict.fromkeys([*(issue_payload.get("evidence_refs") or []), decision.id])
    )
    issue, tasks = core.create_issue(
        core_scope,
        actor,
        correlation_id,
        "rt-issue",
        issue_payload,
    )
    steps.append(
        {
            "service": "core-data-service",
            "activity_id": activity.id,
            "worklog_id": worklog.id,
            "decision_id": decision.id,
            "issue_id": issue.id,
            "task_ids": [task.id for task in tasks],
        }
    )
    evidence.extend(
        ["diff-auth", activity.id, worklog.id, decision.id, issue.id, *[task.id for task in tasks]]
    )

    memory = MemoryService(MemoryStore())
    memory_scope = MemoryScope(wf.scope.tenant_id, wf.scope.workspace_id, wf.scope.project_id)
    memory_payload = dict(wf.memory)
    memory_payload["evidence_refs"] = [decision.id]
    memory_payload["source_refs"] = [worklog.id]
    memory_item = memory.create_memory(
        memory_scope,
        actor,
        correlation_id,
        "rt-memory",
        memory_payload,
    )
    bundle = memory.retrieve_context(
        memory_scope, actor, correlation_id, "argon2 password hashing auth", token_budget=120
    )
    steps.append(
        {
            "service": "memory-service",
            "memory_id": memory_item.id,
            "bundle_id": bundle.bundle_id,
            "selected": len(bundle.items),
        }
    )
    evidence.append(memory_item.id)

    docs = DocsSyncService(DocsStore())
    docs_scope = DocsScope(wf.scope.tenant_id, wf.scope.workspace_id, wf.scope.project_id)
    symbol = docs.index_symbol(
        docs_scope,
        actor,
        correlation_id,
        "rt-symbol",
        {
            "repo": "astloom",
            "file_path": "src/auth.py",
            "symbol_path": wf.docs_note["symbol"],
            "kind": "function",
            "body": "def hash_password(value):\n    return sha256(value)\n",
            "tags": ["auth", "security"],
            "doc_required": True,
        },
    )
    document = docs.index_document(
        docs_scope,
        actor,
        correlation_id,
        "rt-doc",
        {
            "path": "docs/auth.md",
            "frontmatter": {
                "doc_id": "doc-auth-hash",
                "title": wf.docs_note["title"],
                "owner": "security",
                "status": "active",
                "schema_version": "1.0.0",
                "linked_symbols": [wf.docs_note["symbol"]],
                "decision_refs": [decision.id],
            },
            "body": "Uses SHA256 today.",
        },
    )
    docs.register_anchor(
        docs_scope,
        actor,
        correlation_id,
        "rt-anchor",
        {"doc_id": document.id, "symbol_id": symbol.id, "recorded_hash": symbol.body_hash},
    )
    docs.index_symbol(
        docs_scope,
        actor,
        correlation_id,
        "rt-symbol-2",
        {
            "repo": "astloom",
            "file_path": "src/auth.py",
            "symbol_path": wf.docs_note["symbol"],
            "kind": "function",
            "body": "def hash_password(value):\n    return argon2(value)\n",
            "tags": ["auth", "security"],
            "doc_required": True,
        },
    )
    findings = docs.detect_drift(docs_scope, actor, correlation_id, "rt-drift", [symbol.id])
    steps.append(
        {
            "service": "docs-sync-service",
            "symbol_id": symbol.id,
            "document_id": document.id,
            "findings": [item.id for item in findings],
        }
    )
    evidence.extend([symbol.id, document.id, *[item.id for item in findings]])

    rules = RuleEngineService(RulesStore())
    rules_scope = RulesScope(wf.scope.tenant_id, wf.scope.workspace_id, wf.scope.project_id)
    rules.create_rule(rules_scope, actor, correlation_id, "rt-rule", dict(wf.rule))
    subject = dict(wf.rule_subject)
    subject["subject_ref"] = symbol.id
    subject["evidence_refs"] = [decision.id, "diff-auth"]
    evaluation = rules.evaluate_rules(
        rules_scope,
        actor,
        correlation_id,
        "rt-eval",
        subject,
    )
    steps.append(
        {
            "service": "rule-engine-service",
            "final_verdict": evaluation["final_verdict"],
            "blocked": evaluation["blocked"],
            "approvals": len(evaluation["approvals"]),
        }
    )
    evidence.extend([item["id"] for item in evaluation["evaluations"]])

    adapter = AdapterService(AdapterStore())
    adapter_scope = AdapterScope(wf.scope.tenant_id, wf.scope.workspace_id, wf.scope.project_id)
    connector = adapter.register_connector(
        adapter_scope,
        actor,
        correlation_id,
        "rt-connector",
        {
            "vendor": "acme",
            "name": "acme-agent",
            "capabilities": ["can_edit_code", "can_report_task_state"],
            "auth_profile": "token",
            "credential": wf.auth_token,
        },
    )
    adapter.validate_connector(
        adapter_scope, actor, correlation_id, "rt-connector-validate", connector.id
    )
    adapter.subscribe(
        adapter_scope,
        actor,
        correlation_id,
        "rt-sub-dept",
        {
            "channel": "department.workflows",
            "subscriber_type": "webhook",
            "endpoint": "https://example.invalid/hooks",
        },
    )
    published = adapter.publish_agent_event(
        adapter_scope,
        actor,
        correlation_id,
        "rt-publish",
        {
            "message_id": "msg-technical-logic-release",
            "schema_version": "1.0.0",
            "sender": "acme",
            "sender_type": "agent",
            "tenant_id": wf.scope.tenant_id,
            "project_id": wf.scope.project_id,
            "intent": "CODE_RELEASED",
            "domain": "engineering",
            "payload": {
                "summary": wf.broker_event["summary"],
                "decision_id": decision.id,
            },
            "status": "completed",
            "refs": [decision.id, issue.id],
            "correlation_id": correlation_id,
            "created_at": activity.created_at,
        },
    )
    departments = {task["department"] for task in published["department_tasks"]}
    steps.append(
        {
            "service": "adapter-service",
            "event_id": published["event"]["id"],
            "departments": sorted(departments),
        }
    )
    evidence.append(published["event"]["id"])

    ok = (
        activity.correlation_id == correlation_id
        and worklog.correlation_id == correlation_id
        and decision.correlation_id == correlation_id
        and issue.correlation_id == correlation_id
        and findings
        and evaluation["blocked"] is True
        and evaluation["approvals"]
        and {"marketing", "support", "devops"} <= departments
        and all(ref for ref in evidence)
    )
    return RuntimeScenarioReport(
        "password-hashing-migration",
        "passed" if ok else "failed",
        correlation_id,
        steps,
        evidence,
    )
