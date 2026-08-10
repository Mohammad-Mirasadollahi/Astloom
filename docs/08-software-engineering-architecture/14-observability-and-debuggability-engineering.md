---
doc_id: as.doc.sea.observability-and-debuggability-engineering
title: 14 - Observability And Debuggability Engineering
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom should be made observable and debuggable. Observability
  is required because the platform coordinates services, agents, documents, code graphs, rules,
  adapters, and humans. Engineers must be able to understand system behavior without guessing.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/14-observability-and-debuggability-engineering.md
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

# 14 - Observability And Debuggability Engineering

## Purpose

This document defines how Astloom should be made observable and debuggable. Observability is required because the platform coordinates services, agents, documents, code graphs, rules, adapters, and humans. Engineers must be able to understand system behavior without guessing.

## Observability Pillars

Astloom should use:

- structured logs.
- metrics.
- distributed traces.
- domain events.
- audit records.
- health checks.
- readiness checks.
- diagnostic endpoints.
- explainability outputs.

Each pillar answers a different question.

| Pillar | Question Answered |
| --- | --- |
| logs | what happened inside a service |
| metrics | how often and how much |
| traces | where time was spent across services |
| events | what domain facts occurred |
| audit | what evidence supports an action |
| health | is the process alive |
| readiness | can the service handle traffic |
| diagnostics | what configuration and dependencies are effective |
| explanations | why a decision or retrieval happened |

## Correlation Model

Every request, command, event, worker job, and audit record should carry correlation metadata.

Required fields:

- correlation_id
- causation_id when triggered by another event.
- workspace_id.
- actor_ref when available.
- service_name.
- operation_name.
- request_id or event_id.

Correlation IDs must flow through APIs, events, workers, logs, traces, and audit records.

## Logging Standards

Logs should be structured and machine-readable.

Required log fields:

- timestamp.
- level.
- service_name.
- environment.
- operation_name.
- correlation_id.
- workspace_id when available.
- actor_ref when safe.
- message.
- error_code when applicable.
- duration_ms when applicable.

Logs must not include:

- secrets.
- raw credentials.
- full prompts containing sensitive data.
- unredacted external payloads.
- unnecessary personal data.

## Metrics Standards

Metrics should measure service health, workflow quality, and product behavior.

Common metrics:

- request count.
- request latency.
- error count.
- event publish count.
- event consume count.
- retry count.
- dead-letter count.
- worker lag.
- database query latency.
- graph query latency.
- memory retrieval latency.
- rule evaluation latency.
- docs drift count.
- contract validation failures.

Metrics should include labels carefully. High-cardinality labels should be avoided.

## Tracing Standards

Traces should show cross-service workflows.

Trace spans should include:

- API request handling.
- command handler execution.
- repository calls.
- broker publish.
- worker consume.
- external provider calls.
- graph queries.
- memory ranking.
- rule evaluation.
- docs drift detection.

Span names should be stable so dashboards remain useful.

## Health And Readiness

Health checks answer whether the process is alive. Readiness checks answer whether the service can do useful work.

Readiness should verify critical dependencies such as:

- database connectivity.
- broker connectivity.
- graph database connectivity.
- required config loaded.
- migration state compatible.
- required topic subscriptions present.

A service should not be marked ready if it cannot safely handle requests.

## Diagnostic Endpoints

Diagnostic output should help operators and developers understand effective runtime state.

Diagnostics may include:

- service version.
- build revision.
- config schema version.
- contract version set.
- enabled feature flags.
- dependency status.
- migration version.
- effective port.
- environment profile.

Diagnostics must redact secrets.

## Debugging Critical Workflows

Each critical workflow should define its debugging path.

Memory retrieval debugging should show:

- query input summary.
- candidate count.
- filters applied.
- weight profile version.
- score factors.
- selected items.
- rejected high-ranking items and reason when useful.

Rule evaluation debugging should show:

- rule version.
- evidence inputs.
- deterministic checks.
- semantic checks.
- result.
- explanation.
- escalation target.

Code graph debugging should show:

- repository version.
- parser version.
- changed files.
- affected symbols.
- graph snapshot.
- stale edge handling.
- query path explanation.

Docs sync debugging should show:

- changed anchors.
- affected documents.
- drift reason.
- created tasks or suppressed tasks.
- owner resolution.

## Alerting Strategy

Alerts should be actionable.

Alert examples:

- dead-letter queue above threshold.
- migration validation failure.
- graph ingestion failure rate high.
- memory retrieval latency over budget.
- rule evaluation timeout rate high.
- docs drift backlog aging.
- adapter callback verification failure.
- audit event write failure.
- port preflight failure in shared environment.

Every alert should link to a runbook.

## Acceptance Criteria

Observability and debuggability are acceptable when:

- every service emits structured logs with correlation IDs.
- critical workflows can be traced across services.
- metrics exist for reliability, latency, failures, and backlog.
- explanations exist for memory, rules, graph impact, and docs drift.
- diagnostics expose useful runtime state without secrets.
- alerts are actionable and linked to runbooks.
