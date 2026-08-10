---
doc_id: as.doc.ops.observability-slo-and-incident-response
title: Observability, SLO, and Incident Response
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom must be observable enough for operators to diagnose slow agents, failed
  indexing, prompt retrieval mistakes, policy failures, broker delivery problems, and documentation
  drift issues.
tags:
- standard
- ops
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/02-observability-slo-and-incident-response.md
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

# Observability, SLO, and Incident Response

## Purpose

Astloom must be observable enough for operators to diagnose slow agents, failed indexing, prompt retrieval mistakes, policy failures, broker delivery problems, and documentation drift issues.

## Observability Signals

### Logs

Logs should be structured and include correlation ID, tenant ID, project ID, service name, event type, severity, and sanitized message.

### Metrics

Required metrics:

- request count and latency,
- job queue depth,
- job duration,
- indexing duration,
- graph upsert latency,
- memory retrieval latency,
- prompt token count,
- LLM call count,
- LLM failure rate,
- rule evaluation verdict count,
- escalation count,
- broker delivery attempts,
- dead-letter count,
- documentation drift count,
- port conflict count in development.

### Traces

Distributed traces should connect user request, agent action, memory retrieval, rule evaluation, graph query, broker publish, and downstream task creation.

## Suggested SLOs

Initial SLO examples:

- API read endpoints: 99 percent under target latency.
- ContextBundle generation: predictable latency for normal tasks.
- Broker event delivery: high delivery success within retry window.
- Indexing job completion: bounded time per repository size tier.
- Critical escalation creation: near-real-time after risk detection.

Exact numbers should be defined per environment and customer needs.

## Alerting

Alerts should exist for:

- failed critical policy evaluation,
- high dead-letter rate,
- indexing backlog growth,
- context retrieval failures,
- prompt redaction failure,
- graph store unavailable,
- broker unavailable,
- repeated LLM provider failures,
- failed backup or restore verification,
- development port conflict in shared dev environments.

## Incident Response Flow

1. Detect alert or user-reported issue.
2. Identify correlation IDs and affected tenant/project.
3. Retrieve timeline from Activity, WorkLog, RuleEvaluation, broker, and graph events.
4. Classify severity and affected domains.
5. Stop risky automation if needed.
6. Create incident Issue and response Tasks.
7. Preserve evidence.
8. Resolve or mitigate.
9. Write postmortem and update Decisions, Rules, or WeightProfiles if needed.

## Acceptance Criteria

- Every user-visible failure has a correlation ID.
- Operators can trace one workflow across services.
- Critical failures create alerts.
- Incident timelines can be reconstructed without raw chat history.
- Postmortem outcomes can update platform memory and rules.
