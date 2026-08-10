"""Deterministic synthetic workflow generator (GAP-T08).

Role: expand an integer seed into stable multi-service payloads for technical-logic
stitching. SoT: seed + template version. Allowed: placeholder auth tokens only.
Forbidden: real secrets, customer data, non-deterministic timestamps.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

TEMPLATE_VERSION = "synthetic-workflow-v1"
AUTH_PLACEHOLDER = "fixture-auth-placeholder"


@dataclass(frozen=True)
class SyntheticScope:
    tenant_id: str
    workspace_id: str
    project_id: str


@dataclass(frozen=True)
class SyntheticWorkflow:
    seed: int
    template_version: str
    correlation_id: str
    actor: str
    scope: SyntheticScope
    activity: dict[str, Any]
    worklog: dict[str, Any]
    decision: dict[str, Any]
    issue: dict[str, Any]
    memory: dict[str, Any]
    docs_note: dict[str, Any]
    rule: dict[str, Any]
    rule_subject: dict[str, Any]
    broker_event: dict[str, Any]
    auth_token: str = AUTH_PLACEHOLDER
    evidence_refs: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def _stable_token(seed: int, label: str) -> str:
    digest = hashlib.sha256(f"{TEMPLATE_VERSION}:{seed}:{label}".encode()).hexdigest()
    return digest[:12]


def generate_workflow(seed: int = 0, *, correlation_id: str | None = None) -> SyntheticWorkflow:
    """Return a deterministic multi-domain workflow for the given integer seed."""
    token = _stable_token(seed, "scenario")
    corr = correlation_id or f"corr-synthetic-{seed}-{token}"
    actor = "technical-logic-agent" if seed == 0 else f"synthetic-agent-{token[:6]}"
    scope = SyntheticScope("t", "w", "p")
    if seed == 0:
        # Preserve classic Argon2 security-migration stitch (technical-logic gate).
        activity = {
            "action_type": "edit",
            "action_summary": "migrate password hashing to Argon2",
            "evidence_refs": ["diff-auth"],
        }
        worklog = {
            "session_id": "sess-1",
            "agent_id": actor,
            "summary": "Prepared Argon2 migration",
        }
        decision = {
            "title": "Use Argon2",
            "context": "password hashing",
            "options_considered": ["sha256", "argon2"],
            "chosen_option": "argon2",
            "consequences": ["slower hashes", "stronger resistance"],
            "owner": "security",
            "status": "active",
        }
        issue = {
            "title": "Legacy SHA256 password hashes remain",
            "description": "Old users may fail login after Argon2 cutover",
            "severity": "critical",
            "evidence_refs": ["diff-auth"],
            "task_specs": [
                {
                    "title": "Add dual-hash login fallback",
                    "assignee_type": "backend",
                    "instructions": "accept sha256 then upgrade",
                    "acceptance_criteria": ["login works for old hashes"],
                }
            ],
        }
        memory = {
            "kind": "semantic",
            "title": "Password hashing current state",
            "body": "PaymentGateway unchanged. Password hashing target is Argon2.",
            "tags": ["security", "auth", "argon2"],
            "evidence_refs": ["diff-auth"],
            "source_refs": ["worklog-1"],
            "confidence": 0.95,
        }
        docs_note = {
            "title": "Auth hashing ADR",
            "body": "Passwords must use Argon2.",
            "symbol": "auth.hash_password",
        }
        rule = {
            "title": "Auth changes require approval",
            "natural_language_rule": "Authentication and security production changes require human approval",
            "severity": "critical",
            "owner": "security-lead",
            "evaluation_mode": "hybrid",
            "domain": "security",
            "match_tags": ["security", "auth", "production"],
            "examples": ["changed auth middleware without approval"],
            "counterexamples": ["docs-only edit"],
            "required_approval_role": "security-approver",
            "precedence": 200,
        }
        rule_subject = {
            "subject_ref": "change-auth-1",
            "summary": "Migrate production auth hashing to Argon2",
            "change_type": "code",
            "tags": ["security", "auth", "production"],
            "paths": ["src/auth.py"],
            "evidence_refs": ["diff-auth"],
        }
        broker_event = {
            "event_type": "agent.work.completed",
            "department": "security",
            "summary": "Argon2 migration prepared",
            "payload": {"seed": seed, "auth": AUTH_PLACEHOLDER},
        }
        evidence = ["diff-auth"]
    else:
        activity = {
            "action_type": "edit",
            "action_summary": f"synthetic change {token}",
            "evidence_refs": [f"diff-{token}"],
        }
        worklog = {
            "session_id": f"sess-{token}",
            "agent_id": actor,
            "summary": f"Prepared synthetic workflow {token}",
        }
        decision = {
            "title": f"Decision {token}",
            "context": "synthetic",
            "options_considered": ["a", "b"],
            "chosen_option": "a",
            "consequences": ["deterministic"],
            "owner": "platform",
            "status": "active",
        }
        issue = {
            "title": f"Issue {token}",
            "description": f"Synthetic issue for seed {seed}",
            "severity": "medium",
            "evidence_refs": [f"diff-{token}"],
            "task_specs": [
                {
                    "title": f"Task {token}",
                    "description": "Synthetic task",
                    "priority": "p2",
                }
            ],
        }
        memory = {
            "kind": "semantic",
            "title": f"Memory {token}",
            "body": f"Synthetic memory body for seed {seed}",
            "tags": ["synthetic", token[:4]],
            "evidence_refs": [f"diff-{token}"],
            "source_refs": [f"source-{token}"],
            "confidence": 0.8,
        }
        docs_note = {
            "title": f"Doc {token}",
            "body": f"Synthetic documentation note {token}",
            "symbol": f"mod.fn_{token[:6]}",
        }
        rule = {
            "title": f"Rule {token}",
            "natural_language_rule": "Synthetic hybrid rule for workflow gate",
            "severity": "medium",
            "owner": "platform",
            "evaluation_mode": "hybrid",
            "domain": "platform",
            "match_tags": ["synthetic"],
            "examples": [f"example-{token}"],
            "counterexamples": ["docs-only"],
            "required_approval_role": None,
            "precedence": 50,
        }
        rule_subject = {
            "subject_ref": f"change-{token}",
            "summary": f"Synthetic subject {token}",
            "change_type": "code",
            "tags": ["synthetic"],
            "paths": [f"src/{token}.py"],
            "evidence_refs": [f"diff-{token}"],
        }
        broker_event = {
            "event_type": "agent.work.completed",
            "department": "platform",
            "summary": f"Synthetic workflow {token}",
            "payload": {"seed": seed, "auth": AUTH_PLACEHOLDER},
        }
        evidence = [f"diff-{token}"]

    return SyntheticWorkflow(
        seed=seed,
        template_version=TEMPLATE_VERSION,
        correlation_id=corr,
        actor=actor,
        scope=scope,
        activity=activity,
        worklog=worklog,
        decision=decision,
        issue=issue,
        memory=memory,
        docs_note=docs_note,
        rule=rule,
        rule_subject=rule_subject,
        broker_event=broker_event,
        auth_token=AUTH_PLACEHOLDER,
        evidence_refs=evidence,
    )
