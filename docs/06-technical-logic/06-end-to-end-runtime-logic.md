---
doc_id: as.doc.tech.end-to-end-runtime-logic
title: End-to-End Runtime Logic
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: The Astloom runtime converts unstructured agent activity into governed, searchable,
  synchronized, and interoperable system state. The runtime is event-driven, but it does not
  treat events as the final truth. Events are evidence. State is derived from evidence through
  validation.
tags:
- standard
- tech
phase: 06-technical-logic
canonical_path: docs/06-technical-logic/06-end-to-end-runtime-logic.md
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

# End-to-End Runtime Logic


## Purpose

The Astloom runtime converts unstructured agent activity into governed, searchable, synchronized, and interoperable system state. The runtime is event-driven, but it does not treat events as the final truth. Events are evidence. State is derived from evidence through validation.

## Runtime Objective

The Astloom runtime converts unstructured agent activity into governed, searchable, synchronized, and interoperable system state. The runtime is event-driven, but it does not treat events as the final truth. Events are evidence. State is derived from evidence through validation, consolidation, policy evaluation, and human approval when required.

## End-to-End Pipeline

The canonical pipeline is:

1. Ingest raw agent action or external tool message.
2. Normalize it into platform entities and events.
3. Persist records with correlation IDs and evidence references.
4. Update graph links between work, code, docs, decisions, rules, and owners.
5. Classify memory updates and current-state changes.
6. Evaluate policies and risk rules.
7. Detect documentation drift and dependency impact.
8. Create tasks or escalation tickets when needed.
9. Publish broker events to authorized subscribers.
10. Build future ContextBundles from the updated platform state.

## Runtime Control Loop

```text
for each inbound_signal:
    envelope = validate_transport(inbound_signal)
    normalized = normalize_to_platform_contract(envelope)
    persisted = persist_entities_and_events(normalized)
    graph_delta = update_knowledge_graph(persisted)
    memory_delta = update_memory_state(graph_delta)
    risk_result = evaluate_rules_and_risk(graph_delta, memory_delta)

    if risk_result.requires_human_approval:
        ticket = create_escalation_ticket(risk_result)
        publish(ticket.created)
        stop_automation_until(ticket.resolved)
    else:
        impacts = analyze_dependency_impact(graph_delta)
        tasks = route_downstream_tasks(impacts)
        publish_runtime_events(persisted, graph_delta, memory_delta, tasks)
```

## Correlation Model

Every runtime action must preserve a correlation chain. The chain starts from a user request, scheduled job, external agent message, CI event, or human approval. All Activities, Decisions, Issues, Tasks, MemoryItems, DriftFindings, RuleEvaluations, EscalationTickets, and broker events created from that input share a correlation ID.

Correlation makes these queries possible:

- Which user request caused this file change?
- Which agent created the Task?
- Which Decision justified the change?
- Which RuleEvaluation blocked it?
- Which human approved it?
- Which downstream tasks were created?

## Evidence Model

Astloom should store derived records, but derived records are never enough. Every derived record must link to evidence. Evidence can be a diff, command output, test report, code symbol hash, document anchor, approval response, model judge rationale, or external message.

Evidence rules:

- Raw evidence can be restricted.
- Prompt-visible evidence must be redacted.
- Large evidence must be stored by reference.
- Derived summaries must never replace audit evidence.

## State Derivation Rule

Astloom uses events to derive current state. Current state is what agents usually need. Events are retrieved when the agent needs history, audit, or root-cause analysis.

Example:

```text
Event 1: Stripe integration existed.
Event 2: PayPal migration started.
Event 3: PayPal migration completed.
Current state: PaymentGateway = PayPal.
Default prompt: PaymentGateway = PayPal.
Historical prompt: include migration events only when requested.
```

## Model Call Boundaries

The runtime should not call an LLM for every operation. The default order is:

1. Schema validation.
2. Deterministic checks.
3. Graph lookup.
4. Index lookup.
5. Statistical or heuristic scoring.
6. LLM judgment only for ambiguous semantic cases.
7. Human approval for high-risk or low-confidence cases.

## Failure Strategy

The runtime should fail closed for risky domains and fail soft for low-risk informational workflows.

Fail closed examples:

- Authentication changes.
- Permission changes.
- Billing changes.
- Production deployment changes.
- Customer data migrations.

Fail soft examples:

- Optional documentation suggestions.
- Low-priority notifications.
- Non-critical analytics enrichment.

## Idempotency Strategy

Repeated messages, retries, and reconnects must not create duplicate Tasks or conflicting Decisions. Idempotency keys should be based on source, event type, correlation ID, entity reference, and semantic fingerprint.

Example fingerprint inputs:

- Repository and commit hash.
- Task ID.
- Agent ID.
- Code symbol ID.
- Policy ID.
- Document ID.

## Runtime Output

A successful runtime cycle produces one or more of:

- persisted entities,
- graph edges,
- semantic memory updates,
- drift findings,
- rule evaluations,
- tasks,
- escalation tickets,
- broker events,
- context bundle inputs for future agents.
