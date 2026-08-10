---
doc_id: as.doc.core.detailed-section-design
title: Core Data Model - Detailed Section Design
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: The Core Data Model is the foundation of Astloom. Without it, every later feature
  becomes unreliable. Memory cannot be trusted if raw work is not structured. Documentation
  cannot be synchronized if decisions and tasks are not linkable. Orchestration cannot route
  work if Issues .
tags:
- standard
- core
phase: 01-core-data-model
canonical_path: docs/01-core-data-model/06-detailed-section-design.md
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

# Core Data Model - Detailed Section Design


## Purpose

The Core Data Model is the foundation of Astloom. Without it, every later feature becomes unreliable. Memory cannot be trusted if raw work is not structured. Documentation cannot be synchronized if decisions and tasks are not linkable. Orchestration cannot route work if Issues .

## Why This Phase Exists

The Core Data Model is the foundation of Astloom. Without it, every later feature becomes unreliable. Memory cannot be trusted if raw work is not structured. Documentation cannot be synchronized if decisions and tasks are not linkable. Orchestration cannot route work if Issues and Tasks are mixed together. Interoperability cannot work if every agent reports progress in a different shape.

This phase turns agent behavior into organizational knowledge.

## Activity and Work Log in Detail

An Activity is the smallest meaningful unit of work. It should be specific, timestamped, and linked to evidence. Examples include editing a file, running a test, creating an artifact, opening a pull request, changing a schema, or generating a document.

A WorkLog is a session summary. It is not a raw transcript. It should explain what the agent attempted, what succeeded, what failed, what remains, and what follow-up is recommended.

### Required Activity Detail

Each Activity should capture:

- The acting agent or human.
- The related Task, if one exists.
- The action type.
- The affected files, symbols, APIs, docs, or entities.
- Evidence references such as command output, test result, artifact, or diff.
- Confidence and completion status.
- Redaction state for sensitive content.

### WorkLog Quality Rules

A WorkLog should be short enough for a manager to read and structured enough for a future agent to use. It should not include secrets, full terminal logs, or unverified claims. It should include blockers and follow-up Tasks when work is incomplete.

## Decision Tracking in Detail

A Decision protects the reason behind the system. Code says what exists. A Decision says why it exists. Agents need this because optimization without rationale can become destructive.

For example, Argon2 may be slower than SHA256, but the Decision explains that speed is less important than brute-force resistance. A future optimization agent should not replace Argon2 just because it sees a faster alternative.

### Decision Lifecycle

1. Proposed: an agent or human identifies that a choice matters.
2. Accepted: the organization chooses one option and records rationale.
3. Active: the Decision is injected into relevant prompts and linked to code/docs.
4. Superseded: a newer Decision replaces it.
5. Archived: it remains searchable for audit but is not injected by default.

### Decision Fields That Matter

A complete Decision should include context, constraints, options considered, rejected options, chosen option, consequences, generated rules, affected entities, owner, and supersession policy.

## Issue and Task Separation in Detail

An Issue describes a condition. A Task describes action. This separation prevents orchestration mistakes.

Bad modeling:

- Issue: Update old password hashes.

Better modeling:

- Issue: Old users have SHA256 password hashes and may fail login after Argon2 migration.
- Task 1: Add dual-hash login fallback.
- Task 2: Create data backup before migration.
- Task 3: Write migration verification tests.
- Task 4: Update authentication documentation.

## Architecture Flow Notes

The Core Data Model should expose a small number of reliable services:

- Entity Registry: assigns IDs and lifecycle states.
- Activity Ingestion: receives agent traces and normalizes them.
- Decision Registry: stores rationale and links it to future constraints.
- Issue Tracker: receives discoveries and classifies severity.
- Task Planner: creates executable work from Issues.
- Audit Query API: reconstructs timelines and ownership.

These services must be available to later phases through stable APIs and events.

## Module Responsibility Notes

### Normalization

Agents may produce inconsistent raw output. The normalizer converts it into stable shapes. This includes mapping vendor-specific action names, removing noisy text, redacting secrets, and linking evidence.

### Deduplication

Repeated retries should not create fake progress. The model should support idempotency keys and correlation IDs so repeated attempts can be grouped.

### Linking

Records should link to each other rather than copying content. A Task links to an Issue. An Activity links to a Task. A Decision links to code, docs, rules, and Issues. This keeps the graph queryable.

### Audit Query

Audit queries should answer:

- Who changed this file?
- Which Task caused the change?
- Which Decision justified it?
- Which Issue was being solved?
- Which tests or approvals supported it?
- Which follow-up Tasks remain open?

## Edge Cases

- An agent performs work without an assigned Task: create Activities and allow later Task linking.
- A Decision is discovered after work is done: backfill links to related Activities and code.
- An Issue is not actionable: keep it as accepted risk or escalate for human review.
- A Task fails repeatedly: create a blocker Issue or route to a different owner.
- A record contains sensitive output: store a redacted summary and restricted artifact reference.

## Output of This Phase

At the end of this phase, Astloom has a durable memory substrate. Later phases can rely on stable IDs, lifecycle states, evidence references, and relationships between work, reason, risk, and action.
