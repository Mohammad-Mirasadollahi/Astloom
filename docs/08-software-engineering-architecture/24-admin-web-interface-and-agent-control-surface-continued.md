---
doc_id: as.doc.sea.admin-web-interface-and-agent-control-surface-continued
title: 24 - Admin Web Interface And Agent Control Surface (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/08-software-engineering-architecture/24-admin-web-interface-and-agent-control-surface.md`
  — remaining sections after the soft size budget.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/24-admin-web-interface-and-agent-control-surface-continued.md
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

# 24 - Admin Web Interface And Agent Control Surface (Continued)

## Purpose

Continuation of `docs/08-software-engineering-architecture/24-admin-web-interface-and-agent-control-surface.md` — remaining sections after the soft size budget.

## Feedback And Learning Control

Users must be able to tell the system what was wrong and how it should behave next time.

Correction types:

- wrong_answer.
- wrong_memory.
- stale_memory.
- wrong_scope.
- wrong_task_decomposition.
- wrong_rule_interpretation.
- wrong_documentation_draft.
- wrong_code_impact_analysis.
- wrong_connector_mapping.
- missing_context.
- unsafe_action.

FeedbackRecord should include:

- feedback_id.
- target_type.
- target_ref.
- correction_type.
- corrected_value.
- reason.
- project_scope.
- created_by.
- created_at.
- affected_memory_refs.
- affected_rule_refs.
- affected_task_refs.
- status.

Feedback effects may include:

- lower answer confidence.
- supersede MemoryItem.
- update QuestionAnswer.
- create Gap.
- create Task.
- adjust retrieval feedback signals.
- create rule improvement suggestion.
- require human review.

The system should learn through explicit structured feedback, not hidden mutation.

## Rule Management Workflow

Users should be able to define rules for agents and workflows.

Rule creation should include:

- name.
- scope.
- owner.
- description.
- condition.
- severity.
- examples.
- allowed actions.
- blocked actions.
- escalation target.
- test cases.
- rollout mode.

Rollout modes:

- draft.
- shadow.
- active.
- disabled.
- deprecated.

High-risk rule changes require approval and audit.

## Work Batch Management

The Work Batches view should show:

- active batches.
- batch type.
- objective.
- readiness score.
- boundary signals.
- changed files.
- changed symbols.
- deferred memory consolidation.
- deferred documentation generation.
- deferred code review.
- immediate guardrails.
- failed deferred actions.

Allowed actions:

- force consolidation.
- mark ready for review.
- request code review.
- request documentation generation.
- split batch.
- merge batches.
- cancel batch.
- retry failed deferred action.

## Automation Jobs

The Automation Jobs view should show:

- job type.
- status.
- current step.
- risk level.
- approval requirement.
- logs.
- evidence report.
- retryability.
- failure reason.
- repair hint.

Job types:

- installation.
- connector registration.
- migration.
- upgrade.
- drift detection.
- repair.
- diagnostics.

## Reports

Reports should be accessible from the web interface.

Report categories:

- initial code generation speed.
- bug reduction.
- architecture quality.
- rework reduction.
- token consumption.
- documentation drift.
- connector health.
- memory quality.
- agent productivity.
- approval bottlenecks.

Reports must show scope, baseline, time range, sample size, caveats, and evidence drilldown.

## API And Query Model

The admin-console should use public APIs and query models.

Forbidden:

- direct database reads.
- direct service-internal imports.
- bypassing authorization in frontend filters.
- unscoped queries.

Required query capabilities:

- activity timeline query.
- object detail query.
- memory management query.
- task board query.
- rule management query.
- feedback mutation.
- audit search query.
- report query.
- project scope query.

## Product State Requirements

Every major view should support:

- loading.
- empty.
- permission_denied.
- degraded.
- error.
- partial_data.
- stale_data.
- audit_sensitive.
- project_scope_warning.
- project_group_scope_warning.
- action_requires_approval.
- action_completed.
- action_failed.

## Security And Audit Requirements

Security requirements:

- every view enforces permission at API level.
- project scope is mandatory for scoped objects.
- cross-project access shows warning and audit marker.
- sensitive evidence is redacted unless user has permission.
- high-risk changes require approval.
- all corrections create audit events.
- rule changes are versioned.
- memory changes preserve previous value for audit.

## Acceptance Criteria

The web interface is acceptable when:

- users can track every meaningful agent and platform action from the Activity Timeline.
- users can inspect object detail pages for Activity, WorkLog, Decision, Issue, Task, MemoryItem, QuestionMemory, Rule, WorkBatch, AutomationJob, Connector, Report, and AuditRecord.
- users can manage memory, repeated questions, FAQ candidates, tasks, tickets, rules, agents, connectors, batches, automation jobs, reports, and audit records.
- users can create tasks for agents with scope, objective, constraints, acceptance criteria, evidence, tools, and risk level.
- users can correct wrong behavior through structured FeedbackRecord objects.
- corrections affect future behavior through memory confidence, retrieval feedback, rule suggestions, task state, gaps, or review workflows.
- users can define and test rules, including shadow mode and approval-controlled activation.
- project or ProjectGroup scope is always visible and enforced.
- high-risk operations are permission-controlled, approval-gated, and auditable.
- admin-console uses public APIs and never reads service databases directly.


## Related Documents

- Parent document: `docs/08-software-engineering-architecture/24-admin-web-interface-and-agent-control-surface.md`
