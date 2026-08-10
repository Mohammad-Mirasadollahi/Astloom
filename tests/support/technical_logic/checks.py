from __future__ import annotations

import sys
from typing import Any

from .catalog import PHASE_SLICES, ROOT
from .gate import CheckResult


def _ensure_paths() -> None:
    for relative in (
        "backend/services/core-data-service/src",
        "backend/services/memory-service/src",
        "backend/services/docs-sync-service/src",
        "backend/services/rule-engine-service/src",
        "backend/services/adapter-service/src",
    ):
        path = str(ROOT / relative)
        if path not in sys.path:
            sys.path.insert(0, path)


def verify_contracts() -> list[CheckResult]:
    _ensure_paths()
    from core_data_service.api import app as core_app
    from core_data_service.core import CoreData
    from core_data_service.testing import InMemoryStore as CoreStore
    from memory_service.api import app as memory_app
    from memory_service.core import MemoryService
    from memory_service.testing import InMemoryStore as MemoryStore
    from docs_sync_service.api import app as docs_app
    from docs_sync_service.core import DocsSyncService
    from docs_sync_service.testing import InMemoryStore as DocsStore
    from rule_engine_service.api import app as rules_app
    from rule_engine_service.core import RuleEngineService
    from rule_engine_service.testing import InMemoryStore as RulesStore
    from adapter_service.api import app as adapter_app
    from adapter_service.core import AdapterService
    from adapter_service.testing import InMemoryStore as AdapterStore

    results: list[CheckResult] = []
    suites = (
        ("core-data-service", core_app(CoreData(CoreStore())), "/api/v1/projects/{project_id}/activities"),
        ("memory-service", memory_app(MemoryService(MemoryStore())), "/api/v1/projects/{project_id}/memory-items"),
        ("docs-sync-service", docs_app(DocsSyncService(DocsStore())), "/api/v1/projects/{project_id}/symbols"),
        ("rule-engine-service", rules_app(RuleEngineService(RulesStore())), "/api/v1/projects/{project_id}/rules"),
        ("adapter-service", adapter_app(AdapterService(AdapterStore())), "/api/v1/projects/{project_id}/connectors"),
    )
    for subject, api, route in suites:
        routes = {item.path for item in api.routes}
        ok = route in routes
        results.append(
            CheckResult(
                f"contract-{subject}",
                "contract",
                subject,
                "passed" if ok else "failed",
                f"route {route} {'registered' if ok else 'missing'}",
                [route],
                "docs/06-technical-logic/07-technical-test-strategy.md",
            )
        )
    return results


def verify_state_machines() -> list[CheckResult]:
    _ensure_paths()
    from core_data_service.core import ConflictError, CoreData, Kind, Scope
    from core_data_service.testing import InMemoryStore

    service = CoreData(InMemoryStore())
    scope = Scope("t", "w", "p")
    task = service.create(
        Kind.TASK,
        scope,
        "agent",
        "corr",
        "task-1",
        {"title": "t", "assignee_type": "backend", "instructions": "do", "acceptance_criteria": ["ok"]},
    )
    try:
        service.transition(scope, "agent", "corr", "bad", task.id, "done", "skip", 1)
        return [CheckResult("state-illegal", "state_machine", "core-data-service", "failed", "illegal transition was accepted", [task.id])]
    except ConflictError:
        service.transition(scope, "agent", "corr", "ok", task.id, "ready", "triaged", 1)
        return [CheckResult("state-illegal", "state_machine", "core-data-service", "passed", "illegal transition rejected; legal transition accepted", [task.id])]


def verify_idempotency() -> list[CheckResult]:
    _ensure_paths()
    from core_data_service.core import CoreData, Kind, Scope
    from core_data_service.testing import InMemoryStore
    from adapter_service.core import AdapterService, Scope as AdapterScope
    from adapter_service.testing import InMemoryStore as AdapterStore

    results: list[CheckResult] = []
    service = CoreData(InMemoryStore())
    scope = Scope("t", "w", "p")
    payload = {"action_type": "edit", "action_summary": "changed file"}
    first = service.create(Kind.ACTIVITY, scope, "agent", "corr", "idem-1", dict(payload))
    second = service.create(Kind.ACTIVITY, scope, "agent", "corr", "idem-1", dict(payload))
    ok = first.id == second.id
    results.append(
        CheckResult(
            "idempotency-activity",
            "idempotency",
            "core-data-service",
            "passed" if ok else "failed",
            "duplicate idempotency key reused same record" if ok else "duplicate created distinct records",
            [first.id, second.id],
        )
    )

    adapter = AdapterService(AdapterStore())
    adapter_scope = AdapterScope("t", "w", "p")
    connector_payload = {
        "vendor": "acme",
        "name": "acme-agent",
        "capabilities": ["can_report_task_state"],
        "auth_profile": "token",
        "credential": "secret",
    }
    first_conn = adapter.register_connector(adapter_scope, "ops", "corr", "idem-conn", dict(connector_payload))
    second_conn = adapter.register_connector(adapter_scope, "ops", "corr", "idem-conn", dict(connector_payload))
    ok_conn = first_conn.id == second_conn.id
    results.append(
        CheckResult(
            "idempotency-connector",
            "idempotency",
            "adapter-service",
            "passed" if ok_conn else "failed",
            "duplicate connector key reused same record" if ok_conn else "duplicate connector created",
            [first_conn.id, second_conn.id],
        )
    )
    return results


def verify_redaction() -> list[CheckResult]:
    _ensure_paths()
    from memory_service.core import MemoryService, Scope
    from memory_service.testing import InMemoryStore
    from adapter_service.core import AdapterService, Scope as AdapterScope
    from adapter_service.testing import InMemoryStore as AdapterStore

    results: list[CheckResult] = []
    service = MemoryService(InMemoryStore())
    scope = Scope("t", "w", "p")
    item = service.create_memory(
        scope,
        "agent",
        "corr",
        "secret-1",
        {
            "kind": "restricted",
            "title": "Secret",
            "body": "token=super-secret-value must never enter prompts",
            "tags": ["security"],
            "evidence_refs": ["e1"],
            "source_refs": ["s1"],
            "confidence": 0.9,
        },
    )
    body = item.public()["body"]
    ok = "super-secret-value" not in body and "[REDACTED]" in body
    results.append(
        CheckResult(
            "redaction-memory",
            "redaction",
            "memory-service",
            "passed" if ok else "failed",
            "secret token redacted" if ok else "secret token leaked",
            [item.id],
        )
    )

    adapter = AdapterService(AdapterStore())
    adapter_scope = AdapterScope("t", "w", "p")
    injected = adapter.inject_context(
        adapter_scope,
        "ops",
        "corr",
        "redact-1",
        {
            "tool_ref": "ide://plugin",
            "sensitivity_clearance": "public",
            "items": [{"title": "Leak", "body": "api_key=super-secret-value", "sensitivity": "restricted"}],
        },
    )
    package_body = injected["package"]["items"][0]["body"]
    ok_adapter = injected["status"] == "allowed" and "super-secret-value" not in package_body and "[REDACTED]" in package_body
    results.append(
        CheckResult(
            "redaction-adapter-context",
            "redaction",
            "adapter-service",
            "passed" if ok_adapter else "failed",
            "restricted context redacted for tool injection" if ok_adapter else "restricted context leaked",
            [injected["package"]["tool_ref"]],
        )
    )
    return results


def verify_retrieval() -> list[CheckResult]:
    _ensure_paths()
    from memory_service.core import MemoryService, Scope
    from memory_service.testing import InMemoryStore

    service = MemoryService(InMemoryStore())
    scope = Scope("t", "w", "p")
    service.create_memory(
        scope,
        "agent",
        "corr",
        "mem-current",
        {
            "kind": "semantic",
            "title": "Current hashing",
            "body": "Password hashing target is Argon2.",
            "tags": ["auth", "argon2"],
            "evidence_refs": ["e1"],
            "source_refs": ["s1"],
            "confidence": 0.95,
        },
    )
    bundle = service.retrieve_context(scope, "agent", "corr", "argon2 password hashing", token_budget=120)
    ok = any("Argon2" in str(item.get("memory", {}).get("body", "")) for item in bundle.items)
    return [
        CheckResult(
            "retrieval-memory",
            "retrieval",
            "memory-service",
            "passed" if ok else "failed",
            "relevant current memory retrieved" if ok else "retrieval missed current memory",
            [bundle.bundle_id],
            "docs/06-technical-logic/02-memory-context-technical-logic.md",
        )
    ]


def verify_docs_drift() -> list[CheckResult]:
    _ensure_paths()
    from docs_sync_service.core import DocsSyncService, Scope
    from docs_sync_service.testing import InMemoryStore

    service = DocsSyncService(InMemoryStore())
    scope = Scope("t", "w", "p")
    symbol = service.index_symbol(
        scope,
        "agent",
        "corr",
        "sym-1",
        {
            "repo": "astloom",
            "file_path": "src/auth.py",
            "symbol_path": "auth.hash_password",
            "kind": "function",
            "body": "def hash_password(value):\n    return sha256(value)\n",
            "tags": ["auth"],
            "doc_required": True,
        },
    )
    document = service.index_document(
        scope,
        "agent",
        "corr",
        "doc-1",
        {
            "path": "docs/auth.md",
            "frontmatter": {
                "doc_id": "doc-auth-hash",
                "title": "Password hashing",
                "owner": "security",
                "status": "active",
                "schema_version": "1.0.0",
                "linked_symbols": ["auth.hash_password"],
                "decision_refs": [],
            },
            "body": "Uses SHA256 today.",
        },
    )
    service.register_anchor(scope, "agent", "corr", "anchor-1", {"doc_id": document.id, "symbol_id": symbol.id, "recorded_hash": symbol.body_hash})
    service.index_symbol(
        scope,
        "agent",
        "corr",
        "sym-2",
        {
            "repo": "astloom",
            "file_path": "src/auth.py",
            "symbol_path": "auth.hash_password",
            "kind": "function",
            "body": "def hash_password(value):\n    return argon2(value)\n",
            "tags": ["auth"],
            "doc_required": True,
        },
    )
    findings = service.detect_drift(scope, "agent", "corr", "drift-1", [symbol.id])
    ok = bool(findings)
    return [
        CheckResult(
            "docs-drift-auth",
            "docs_drift",
            "docs-sync-service",
            "passed" if ok else "failed",
            "code/doc drift detected after symbol change" if ok else "expected drift finding missing",
            [symbol.id, document.id, *[item.id for item in findings]],
            "docs/06-technical-logic/03-docs-sync-technical-logic.md",
        )
    ]


def verify_rule_evaluation() -> list[CheckResult]:
    _ensure_paths()
    from rule_engine_service.core import RuleEngineService, Scope
    from rule_engine_service.testing import InMemoryStore

    service = RuleEngineService(InMemoryStore())
    scope = Scope("t", "w", "p")
    service.create_rule(
        scope,
        "agent",
        "corr",
        "rule-1",
        {
            "title": "Auth changes require approval",
            "natural_language_rule": "Authentication production changes require human approval",
            "severity": "critical",
            "owner": "security-lead",
            "evaluation_mode": "hybrid",
            "domain": "security",
            "match_tags": ["security", "auth", "production"],
            "required_approval_role": "security-approver",
        },
    )
    evaluation = service.evaluate_rules(
        scope,
        "agent",
        "corr",
        "eval-1",
        {
            "subject_ref": "auth.hash_password",
            "summary": "Migrate production auth hashing",
            "change_type": "code",
            "tags": ["security", "auth", "production"],
            "paths": ["src/auth.py"],
            "evidence_refs": ["diff-auth"],
        },
    )
    ok = evaluation["blocked"] is True and bool(evaluation["approvals"])
    return [
        CheckResult(
            "rule-evaluation-auth",
            "rule_evaluation",
            "rule-engine-service",
            "passed" if ok else "failed",
            "critical auth change blocked for approval" if ok else "rule evaluation did not block",
            [item["id"] for item in evaluation["evaluations"]],
            "docs/06-technical-logic/04-rules-orchestration-technical-logic.md",
        )
    ]


def verify_broker_delivery() -> list[CheckResult]:
    _ensure_paths()
    from adapter_service.core import AdapterService, Scope, ValidationError
    from adapter_service.testing import InMemoryStore

    service = AdapterService(InMemoryStore())
    scope = Scope("t", "w", "p")
    results: list[CheckResult] = []

    try:
        service.publish_agent_event(
            scope,
            "ops",
            "corr",
            "bad-schema",
            {"message_id": "x", "schema_version": "9.9.9", "intent": "TASK_STARTED"},
        )
        results.append(
            CheckResult(
                "broker-invalid-schema",
                "broker_delivery",
                "adapter-service",
                "failed",
                "invalid schema was accepted",
                [],
                "docs/06-technical-logic/05-interoperability-technical-logic.md",
            )
        )
    except ValidationError:
        results.append(
            CheckResult(
                "broker-invalid-schema",
                "broker_delivery",
                "adapter-service",
                "passed",
                "invalid schema rejected",
                [],
                "docs/06-technical-logic/05-interoperability-technical-logic.md",
            )
        )

    connector = service.register_connector(
        scope,
        "ops",
        "corr",
        "broker-conn",
        {
            "vendor": "acme",
            "name": "acme-agent",
            "capabilities": ["can_report_task_state"],
            "auth_profile": "token",
            "credential": "secret",
        },
    )
    service.validate_connector(scope, "ops", "corr", "broker-conn-v", connector.id)
    ok_sub = service.subscribe(
        scope,
        "ops",
        "corr",
        "broker-ok",
        {"channel": "agent.tasks", "subscriber_type": "agent", "endpoint": "vendor://acme/inbox"},
    )
    denied_sub = service.subscribe(
        scope,
        "ops",
        "corr",
        "broker-deny",
        {
            "channel": "agent.tasks",
            "subscriber_type": "agent",
            "endpoint": "vendor://evil/inbox",
            "fail_mode": "unauthorized",
        },
    )
    failing = service.subscribe(
        scope,
        "ops",
        "corr",
        "broker-fail",
        {
            "channel": "department.workflows",
            "subscriber_type": "webhook",
            "endpoint": "https://example.invalid/hook",
            "fail_mode": "always",
        },
    )
    message = {
        "message_id": "msg-broker-1",
        "schema_version": "1.0.0",
        "sender": "acme",
        "sender_type": "agent",
        "tenant_id": "t",
        "project_id": "p",
        "intent": "TASK_STARTED",
        "domain": "engineering",
        "payload": {"summary": "started"},
        "status": "running",
        "refs": ["task:1"],
        "correlation_id": "corr",
        "created_at": "2026-07-18T12:00:00+00:00",
    }
    published = service.publish_agent_event(scope, "ops", "corr", "broker-pub", message)
    delivered = {item["subscription_id"] for item in published["deliveries"] if item["status"] == "delivered"}
    ok_delivery = ok_sub.id in delivered and denied_sub.id not in delivered
    results.append(
        CheckResult(
            "broker-authorized-delivery",
            "broker_delivery",
            "adapter-service",
            "passed" if ok_delivery else "failed",
            "authorized subscriber delivered; unauthorized denied" if ok_delivery else "delivery authorization failed",
            [ok_sub.id, denied_sub.id],
            "docs/06-technical-logic/05-interoperability-technical-logic.md",
        )
    )

    release = {
        **message,
        "message_id": "msg-broker-release",
        "intent": "CODE_RELEASED",
        "status": "completed",
        "payload": {"summary": "released"},
    }
    failed = service.publish_agent_event(scope, "ops", "corr", "broker-dlq", release)
    dead = service.get_dead_letter_queue(scope)
    ok_dead = any(item["subscription_id"] == failing.id and item["status"] == "dead_lettered" for item in failed["deliveries"]) and bool(dead)
    results.append(
        CheckResult(
            "broker-dead-letter",
            "broker_delivery",
            "adapter-service",
            "passed" if ok_dead else "failed",
            "failed subscriber created dead-letter" if ok_dead else "dead-letter missing",
            [failing.id, *[item.id for item in dead]],
            "docs/06-technical-logic/05-interoperability-technical-logic.md",
        )
    )
    return results


def verify_catalog_coverage() -> list[CheckResult]:
    """Ensure every catalog check_type for phases 1-5 is exercised by run_all_checks (excluding this meta check)."""
    implemented = {
        "contract",
        "state_machine",
        "idempotency",
        "redaction",
        "retrieval",
        "docs_drift",
        "rule_evaluation",
        "broker_delivery",
    }
    results: list[CheckResult] = []
    for item in PHASE_SLICES:
        missing = [check_type for check_type in item.check_types if check_type not in implemented]
        ok = not missing
        results.append(
            CheckResult(
                f"catalog-coverage-{item.service}",
                "catalog_coverage",
                item.service,
                "passed" if ok else "failed",
                "catalog check types implemented" if ok else f"missing check types: {', '.join(missing)}",
                list(item.check_types),
                str(item.logic_doc.relative_to(ROOT)),
            )
        )
    return results


def run_all_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(verify_contracts())
    results.extend(verify_state_machines())
    results.extend(verify_idempotency())
    results.extend(verify_redaction())
    results.extend(verify_retrieval())
    results.extend(verify_docs_drift())
    results.extend(verify_rule_evaluation())
    results.extend(verify_broker_delivery())
    results.extend(verify_catalog_coverage())
    return results


def checks_public(results: list[CheckResult]) -> list[dict[str, Any]]:
    return [item.public() for item in results]
