---
doc_id: as.doc.tech.core-data-model-technical-logic
title: Core Data Model Technical Logic
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: The Core Data Model must provide deterministic, auditable, queryable records for
  agent work.
tags:
- standard
- tech
phase: 06-technical-logic
canonical_path: docs/06-technical-logic/01-core-data-model-technical-logic.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Core Data Model Technical Logic


## Purpose

The Core Data Model must provide deterministic, auditable, queryable records for agent work. This layer is the write-ahead memory of Astloom. No higher-level component should depend on raw chat messages, raw terminal output, or vendor-specific agent text.

## Technical Goal

The Core Data Model must provide deterministic, auditable, queryable records for agent work. This layer is the write-ahead memory of Astloom. No higher-level component should depend on raw chat messages, raw terminal output, or vendor-specific agent text.

## Entity Invariants

### Global Invariants

Every persisted entity must satisfy:

- `id` is globally unique inside the tenant.
- `tenant_id` is present.
- `project_id` is present when the entity belongs to a project.
- `created_at` and `updated_at` are monotonic for that entity.
- `status` is one of the allowed lifecycle states.
- `source_refs` points to evidence or parent events.
- `correlation_id` links related work across the runtime pipeline.

### Activity Invariants

An Activity must represent an atomic action. It must not represent an entire session or vague intention.

Valid Activity examples:

- file edited,
- command executed,
- test suite run,
- artifact generated,
- document updated,
- message published,
- approval requested.

Invalid Activity examples:

- worked on backend,
- improved system,
- fixed everything,
- discussed architecture.

### Decision Invariants

A Decision must include rationale. A record without rationale is not a Decision. It is only a note.

Required Decision fields:

- context,
- options considered,
- selected option,
- rejected options,
- consequences,
- owner,
- supersession rules,
- linked entities.

### Issue and Task Invariants

An Issue describes a condition. A Task describes execution.

Rules:

- An Issue can exist without a Task if it is accepted risk or awaiting triage.
- A Task should have acceptance criteria before execution.
- A Task can link to multiple Issues only when work genuinely resolves multiple conditions.
- A completed Task does not automatically close an Issue unless closure criteria are satisfied.

## Write Path Logic

```text
input: raw_agent_trace

1. validate trace envelope
2. assign correlation_id if missing
3. split trace into candidate activities
4. redact sensitive payloads
5. store large outputs as artifacts
6. create Activity records
7. create or update WorkLog
8. extract Decision candidates
9. extract Issue candidates
10. decompose actionable Issues into Tasks
11. emit entity events
```

## Activity Normalization Algorithm

```text
normalize_activity(raw_event):
    action_type = map_vendor_action(raw_event.type)
    evidence_refs = persist_evidence(raw_event.outputs)
    affected_refs = extract_affected_entities(raw_event)
    sensitivity = classify_sensitivity(raw_event)

    return Activity(
        action_type=action_type,
        affected_refs=affected_refs,
        evidence_refs=evidence_refs,
        sensitivity=sensitivity,
        correlation_id=raw_event.correlation_id
    )
```

Normalization must be deterministic. Two equivalent raw events from two vendors should produce the same logical Activity type.

## Decision Extraction Logic

Decision extraction should be conservative. The system should not create Decisions for every sentence that sounds important.

Decision candidate signals:

- mentions tradeoff,
- chooses one option over another,
- affects architecture, security, data, cost, or product behavior,
- creates future constraints,
- is approved by a human,
- is referenced by code or docs.

Decision promotion flow:

1. Detect candidate rationale.
2. Link candidate to affected entities.
3. Check if an active Decision already covers the same subject.
4. If no active Decision exists, create proposed Decision.
5. If conflict exists, require human review or create supersession proposal.

## Issue Classification Logic

Issue severity should be computed from impact and urgency.

```text
severity_score = max(
    security_impact,
    data_integrity_impact,
    revenue_impact,
    production_impact,
    user_visibility,
    compliance_impact
) + urgency_modifier
```

Severity levels:

- `LOW`: local cleanup or non-blocking improvement.
- `MEDIUM`: user-visible or team-visible defect without immediate risk.
- `HIGH`: likely production, revenue, data, or security impact.
- `CRITICAL`: active outage, data loss risk, security exposure, or blocked release.

## Task Decomposition Logic

Task decomposition should create role-specific executable work.

Example Issue:

```text
Old user password hashes are SHA256 while current login expects Argon2.
```

Generated Tasks:

- Backend Task: implement dual-hash fallback.
- Data Task: backup users table and verify migration safety.
- QA Task: test legacy and new login paths.
- Docs Task: update authentication architecture docs.
- Security Task: review hashing policy and rollback plan.

Decomposition algorithm:

```text
for issue in actionable_issues:
    domains = infer_affected_domains(issue)
    for domain in domains:
        task = create_task_template(domain, issue)
        attach_acceptance_criteria(task)
        attach_required_context(task)
        route_to_owner_or_agent(task)
```

## Lifecycle State Machines

### Issue Lifecycle

```text
DISCOVERED -> TRIAGED -> ACCEPTED | IN_PROGRESS | ESCALATED
IN_PROGRESS -> RESOLVED -> VERIFIED -> CLOSED
ESCALATED -> APPROVED | REJECTED | ACCEPTED_RISK
```

### Task Lifecycle

```text
CREATED -> READY -> ASSIGNED -> IN_PROGRESS -> COMPLETED -> VERIFIED
CREATED -> BLOCKED
IN_PROGRESS -> BLOCKED
BLOCKED -> READY | CANCELLED
```

### Decision Lifecycle

```text
PROPOSED -> ACCEPTED -> ACTIVE -> SUPERSEDED -> ARCHIVED
PROPOSED -> REJECTED
```

## Deduplication Logic

Duplicate records are likely when agents retry work or external tools resend events.

Deduplication key examples:

- Activity: `source + action_type + affected_refs + evidence_hash + correlation_id`.
- Issue: `normalized_title + affected_entity + severity + open_status`.
- Task: `issue_id + assignee_type + task_intent`.
- Decision: `subject + selected_option + active_status`.

## Audit Reconstruction Logic

To reconstruct an incident:

1. Start from affected entity or incident time range.
2. Find Activities touching the entity.
3. Join Tasks through `task_id`.
4. Join Issues through `issue_id`.
5. Join Decisions through graph edges.
6. Join RuleEvaluations and approvals through correlation ID.
7. Return a chronological timeline with evidence references.

## Failure Handling

- If evidence storage fails, do not mark Activity complete.
- If Decision extraction is uncertain, create a candidate for review instead of active Decision.
- If Task decomposition is ambiguous, route to triage.
- If redaction fails, restrict the record from prompt use.
- If correlation is missing, generate a new correlation ID and preserve source metadata.
