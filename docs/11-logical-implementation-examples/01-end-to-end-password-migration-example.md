---
doc_id: as.doc.examples.end-to-end-password-migration-example
title: End-to-End Example - Password Hashing Migration
doc_type: example
status: draft
schema_version: '1.0'
owner: platform-docs
summary: A backend agent changes password hashing from SHA256 to Argon2. The system must record
  the work, preserve the reason, detect migration risk, create follow-up tasks, update memory,
  check documentation drift, evaluate security policy, and request approval if required.
tags:
- example
- examples
phase: 11-logical-implementation-examples
canonical_path: docs/11-logical-implementation-examples/01-end-to-end-password-migration-example.md
lifecycle_lane: current
concern_lane: example
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# End-to-End Example - Password Hashing Migration


## Purpose

A backend agent changes password hashing from SHA256 to Argon2. The system must record the work, preserve the reason, detect migration risk, create follow-up tasks, update memory, check documentation drift, evaluate security policy, and request approval if required.

## Scenario

A backend agent changes password hashing from SHA256 to Argon2. The system must record the work, preserve the reason, detect migration risk, create follow-up tasks, update memory, check documentation drift, evaluate security policy, and request approval if required.

## User Request

```text
Improve password storage security by replacing SHA256 with Argon2.
```

## Expected Runtime Flow

### Step 1 - Task Creation

The user request creates a Task.

Created record:

```text
Task:
    title: Replace password hashing with Argon2
    assignee_type: Backend Agent
    risk_level: HIGH
    acceptance_criteria:
        - Argon2 is used for new password hashes.
        - Legacy users can still log in.
        - Migration path is documented.
        - Security approval is recorded.
```

### Step 2 - Agent Work Activity

The backend agent edits authentication code and tests.

Created Activities:

```text
Activity 1: file edited: src/auth/hash.py
Activity 2: file edited: tests/auth/test_hashing.py
Activity 3: command executed: auth tests
Activity 4: test result recorded
```

Every Activity links to the Task, changed files, evidence refs, and correlation ID.

### Step 3 - Decision Tracking

The system or reviewer records the reason for Argon2.

Created Decision:

```text
Decision:
    title: Use Argon2 for password hashing
    context: SHA256 is too fast and weak against brute force attacks.
    selected_option: Argon2
    rejected_options: SHA256, bcrypt with low cost
    consequence: Login may be slower but security is improved.
    generated_rule: Do not replace Argon2 with faster hash without security approval.
```

### Step 4 - Issue Detection

The agent discovers that old users still have SHA256 hashes.

Created Issue:

```text
Issue:
    title: Legacy SHA256 password hashes require migration path
    severity: CRITICAL
    affected_entities: User authentication, login flow, user database
```

### Step 5 - Task Decomposition

The Issue creates multiple Tasks.

Generated Tasks:

```text
Backend Task: implement dual-hash fallback and lazy migration.
Data Task: verify backup and migration safety.
QA Task: test legacy and Argon2 login paths.
Docs Task: update authentication documentation.
Security Task: review hashing change and approve release.
```

### Step 6 - Memory Update

Semantic memory updates current state.

New SemanticFact:

```text
subject: Authentication.PasswordHashing
predicate: uses_algorithm
object: Argon2
status: ACTIVE
source_refs: Decision, merged code, passing tests
```

Old SHA256 memory is not deleted. It is marked historical or deprecated for default prompts.

### Step 7 - Documentation Drift Check

The docs system detects that authentication docs reference SHA256.

Created DriftFinding:

```text
type: STALE_DOC
symbol: src/auth/hash.py::hash_password
old_doc_hash: previous hash
new_code_hash: current hash
severity: CRITICAL
```

### Step 8 - Rule Evaluation

The Rule Engine evaluates security policy.

RuleEvaluation:

```text
policy: Authentication changes require security approval.
verdict: ESCALATE
confidence: HIGH
evidence_refs: changed auth file, Decision, tests, DriftFinding
```

### Step 9 - Escalation Ticket

Human security approval is requested.

EscalationTicket:

```text
approver: Security Owner
options: approve, reject, request changes
status: PENDING
```

### Step 10 - Broker Events

The Broker publishes events:

```text
task.created
issue.discovered
decision.created
drift.detected
escalation.created
```

Subscribed IDE plugins, dashboards, and agents receive authorized updates.

## Edge Cases

### Legacy Login Fails

If tests show legacy users cannot log in, the Backend Task remains incomplete and the Issue remains open.

### Security Rejects Change

If Security rejects the change, the Task moves to BLOCKED or CANCELLED and remediation Tasks are created.

### Documentation Not Updated

If docs are not updated, CI blocks merge because the drift is critical.

### Conflicting Memory Exists

If memory still says SHA256 is current, the State Reconciler creates a conflict and blocks high-risk context injection.

## Developer Implementation Notes

- Implement Task and Issue state transitions before orchestration.
- Store evidence refs for tests and diffs.
- Do not inject legacy SHA256 facts as current state.
- Security approval must be linked to the final merge or release Activity.
- Drift detection must run before merge.
