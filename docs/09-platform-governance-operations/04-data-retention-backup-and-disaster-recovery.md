---
doc_id: as.doc.ops.data-retention-backup-and-disaster-recovery
title: Data Retention, Backup, and Disaster Recovery
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom stores operational evidence, code graph data, memory, documentation links,
  rules, approvals, and broker events. The platform must define how long data is retained,
  how it is backed up, and how it is restored after failure.
tags:
- standard
- ops
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/04-data-retention-backup-and-disaster-recovery.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.3.1
updated_at: 2026-08-10
related_docs:
- docs/superpowers/specs/2026-08-01-project-backup-restore-design.md
- docs/09-platform-governance-operations/13-project-scoped-backup-and-restore.md
- backend/runbooks/backup-restore/README.md
---

# Data Retention, Backup, and Disaster Recovery

## Purpose

Astloom stores operational evidence, code graph data, memory, documentation links, rules, approvals, and broker events. The platform must define how long data is retained, how it is backed up, and how it is restored after failure.

## Data Classes

- Structured work records: Activity, WorkLog, Decision, Issue, Task.
- Memory records: MemoryItem, SemanticFact, ContextBundle, WeightProfile.
- Code graph records: File, Class, Function, Method, relationships, embeddings.
- Documentation records: Doc, DocAnchor, DriftFinding.
- Governance records: Policy, RuleEvaluation, EscalationTicket, approval records.
- Broker records: Channel, Subscription, DeliveryAttempt, DeadLetter.
- Evidence artifacts: logs, diffs, test outputs, generated artifacts.

## Retention Rules

Retention should vary by data class and sensitivity.

General principles:

- Decisions and approvals should be retained longer than routine Activities.
- Security and compliance evidence may require extended retention.
- Prompt-visible summaries can expire earlier than audit evidence.
- Deprecated memory can be excluded from prompts while retained for audit.
- Customer data should follow privacy and deletion rules.
- Automated follow-up Tasks (`retention_class=automated_followup`) are canceled when
  debt clears and hard-deleted after a short terminal window — see
  `docs/01-core-data-model/09-automated-followup-task-lifecycle-and-retention.md`.
  Do not apply MemoryItem decay/TTL to these Tasks.

## Backup Requirements

Backups should include:

- primary structured database,
- Neo4j graph database,
- broker state when persistent,
- object/artifact storage,
- configuration profiles,
- schema versions,
- encryption metadata.

### Project-scoped portable backup

Operators can export one project scope to a `.asbak` bundle and restore it on
another Astloom server
(`astloom backup export|validate|dry-run|restore|status`).
The bundle covers analytical stores (core data, memory + embeddings, code graph,
docs-sync, guidance/common-context, profiles, rules, adapter metadata,
orchestration, audit, reporting) with fail-closed conflict handling, schema
fingerprint gates, post-restore count verification, and optional scope remap.
MCP exposes `astloom_backup_status` and `astloom_backup_dry_run` only.
Connector secrets and full-server broker replay remain out of scope for `.asbak`.

Normative operator runbook:
`docs/09-platform-governance-operations/13-project-scoped-backup-and-restore.md`.
Design: `docs/superpowers/specs/2026-08-01-project-backup-restore-design.md`.
Package boundary: `backend/runbooks/backup-restore/README.md`.

## Restore Requirements

A restore is incomplete unless indexes, graph relationships, memory state, and broker replay state remain consistent.

Restore validation should check:

- entity count consistency,
- graph relationship consistency,
- latest migration version,
- ability to reconstruct audit timeline,
- ability to build a ContextBundle,
- ability to run drift detection,
- ability to publish and consume broker events.

## Disaster Recovery Strategy

The platform should define RPO and RTO per environment. Production needs stricter recovery targets than development.

Recovery procedure:

1. Stop writes if corruption is suspected.
2. Snapshot current failed state for forensics.
3. Restore latest valid backup.
4. Replay safe event logs if available.
5. Verify schema and graph consistency.
6. Resume services gradually.
7. Create incident report and follow-up Tasks.

## Acceptance Criteria

- Backups are scheduled and monitored.
- Restore is tested regularly.
- Audit evidence can be restored with source references.
- Deprecated memory remains auditable within retention period.
- Customer data deletion requirements are enforceable.
