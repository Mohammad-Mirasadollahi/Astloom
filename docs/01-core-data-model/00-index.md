---
doc_id: as.doc.core.index
title: 01 - Core Data Model Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: Turn every agent action, architectural reason, discovered problem, and executable
  assignment into durable structured knowledge.
tags:
- index
- core
phase: 01-core-data-model
canonical_path: docs/01-core-data-model/00-index.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.1.1
updated_at: 2026-08-10
---

# 01 - Core Data Model Index


## Purpose

Turn every agent action, architectural reason, discovered problem, and executable assignment into durable structured knowledge.

## Mission

Turn every agent action, architectural reason, discovered problem, and executable assignment into durable structured knowledge.

## Files

- `01-feature-specification.md` defines the feature scope and functional requirements.
- `02-high-level-design.md` defines actors, components, boundaries, integrations, and system-level flow.
- `03-low-level-design.md` defines modules, state machines, validation rules, idempotency, and failure handling.
- `04-data-contracts-and-events.md` defines entities, contracts, and events.
- `05-risks-challenges-and-acceptance.md` defines challenges, mitigations, and acceptance criteria.
- `06-detailed-section-design.md` provides deep rationale, lifecycle details, examples, edge cases, and phase output.
- `07-agent-collaboration-work-surface.md` defines the Astloom-native Issue/Task/AgentTicket/ChangeSet/Review/Comment/Label surface for agents (GitHub-like in role, not GitHub as SoR).
- `08-changeset-review-and-discussion-contracts.md` defines contracts, state machines, commands, queries, and events for ChangeSet, reviews, discussion, and labels.
- `09-automated-followup-task-lifecycle-and-retention.md` defines identity, reconcile-to-cancel, and retention for sync/quality automated Tasks (not Memory TTL).

## Features Covered

- Activity and Work Log
- Decision Tracking
- Issue and Task Separation
- Agent collaboration work surface (ChangeSet, ReviewThread, DiscussionComment, WorkLabel)
- Automated follow-up Task lifecycle and retention

## Related Technical Logic

- `../06-technical-logic/01-core-data-model-technical-logic.md` explains entity invariants, write paths, state transitions, idempotency, audit reconstruction, and task decomposition logic.
- External tracker/VCS projection rules: `../05-interoperability-ecosystem/10-external-vcs-and-tracker-mapping.md`.
