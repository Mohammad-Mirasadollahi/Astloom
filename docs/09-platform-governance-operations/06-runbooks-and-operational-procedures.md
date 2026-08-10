---
doc_id: as.doc.ops.runbooks-and-operational-procedures
title: Runbooks and Operational Procedures
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-docs
summary: Runbooks define repeatable operational procedures. They reduce confusion during incidents,
  releases, indexing failures, policy failures, and integration outages.
tags:
- runbook
- ops
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/06-runbooks-and-operational-procedures.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.1.1
updated_at: 2026-08-10
---

# Runbooks and Operational Procedures

## Purpose

Runbooks define repeatable operational procedures. They reduce confusion during incidents, releases, indexing failures, policy failures, and integration outages.

## Required Runbooks

### Failed Graph Indexing

1. Identify repository, commit, parser version, and failed file.
2. Check parser error and unsupported language features.
3. Mark affected graph nodes as stale or index failed.
4. Retry indexing after fix.
5. Verify graph consistency and drift status.

### Memory Retrieval Failure

1. Capture ContextBundle ID and retrieval query.
2. Inspect selected WeightProfile.
3. Check access control and redaction filters.
4. Review omitted high-scoring items.
5. Create memory repair or graph linking Task if needed.

### Policy Evaluation Failure

1. Identify Policy and RuleEvaluation records.
2. Check deterministic pre-check output.
3. Check LLM judge response if used.
4. Escalate if risk is medium or higher.
5. Update policy examples or counterexamples after resolution.

### Broker Dead-Letter Growth

1. Identify affected channel and subscriber.
2. Inspect failure reason and attempt count.
3. Pause subscriber if needed.
4. Fix endpoint, schema, or authorization issue.
5. Replay eligible messages.

### Development Port Conflict

1. Run port preflight check.
2. Identify occupied port and owning process if possible.
3. Change `ASTLOOM_DEV_PORT_BASE` or service-specific override.
4. Restart services.
5. Verify runtime summary shows expected ports.

### LLM Provider Failure

1. Detect provider outage or elevated errors.
2. Route low-risk work to fallback model if configured.
3. Pause high-risk automation if judgment is unavailable.
4. Record incident and affected Tasks.
5. Resume normal routing after provider health recovers.

### Project Scope Migrate (`.asbak`)

1. On source: `astloom backup export -o ./project.asbak`.
2. Copy the archive to the target Astloom server.
3. On target: `astloom backup validate -i ./project.asbak` then `dry-run`.
4. Restore into an empty scope, or use `--replace --yes` after explicit approval.
5. Confirm `astloom backup status` and spot-check memory/graph/docs counts.

Normative detail: `docs/09-platform-governance-operations/13-project-scoped-backup-and-restore.md`.

## Runbook Requirements

Every runbook should include trigger, symptoms, owner, severity, immediate mitigation, detailed steps, validation, rollback, and follow-up Tasks.

## Acceptance Criteria

- Critical workflows have runbooks.
- Runbooks link to metrics and logs.
- Runbooks create follow-up Tasks after incidents.
- Port conflicts have a documented remediation path.
