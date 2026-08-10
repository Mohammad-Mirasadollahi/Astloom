---
doc_id: as.doc.examples.interoperability-and-broker-example
title: Logical Example - Interoperability and Broker
doc_type: example
status: draft
schema_version: '1.0'
owner: platform-docs
summary: A backend agent finishes a new Black Friday discount API. A frontend IDE plugin,
  QA agent, Docs Agent, and Marketing workflow need to react without direct coupling to the
  backend agent.
tags:
- example
- examples
phase: 11-logical-implementation-examples
canonical_path: docs/11-logical-implementation-examples/05-interoperability-and-broker-example.md
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

# Logical Example - Interoperability and Broker


## Purpose

A backend agent finishes a new Black Friday discount API. A frontend IDE plugin, QA agent, Docs Agent, and Marketing workflow need to react without direct coupling to the backend agent.

## Scenario

A backend agent finishes a new Black Friday discount API. A frontend IDE plugin, QA agent, Docs Agent, and Marketing workflow need to react without direct coupling to the backend agent.

## Backend Agent Message

```text
Universal Agent JSON:
    intent: API_READY
    sender: backend-agent
    domain: Campaign
    payload:
        endpoint: /api/campaigns/black-friday/discount
        method: POST
        required_params: user_id, promo_code
    status: AWAITING_FRONTEND
    correlation_id: campaign-2026-black-friday
```

## Broker Flow

```text
1. Protocol Validator checks schema and sender identity.
2. Tenant Boundary Guard checks tenant and project scope.
3. Broker resolves channels:
    - campaign-updates
    - frontend-tasks
    - qa-updates
    - docs-updates
4. Event is persisted before delivery.
5. Subscribers receive authorized messages.
```

## Subscriber Behavior

### Frontend IDE Plugin

Receives API_READY and suggests creating or updating checkout UI integration.

### QA Agent

Creates tests for required params, invalid promo code, and user eligibility.

### Docs Agent

Creates or updates API documentation.

### Marketing Workflow

Receives a governed notification that the API exists, but does not send campaign email until Product approval is complete.

## Dead-Letter Example

If the QA subscriber endpoint is down:

```text
DeliveryAttempt 1: failed
DeliveryAttempt 2: failed
DeliveryAttempt 3: failed
DeadLetter created with failure reason and replay eligibility
```

The broker does not lose the event.

## Adapter Example

If an external IDE does not understand Universal Agent JSON directly, an adapter maps the event into IDE-native notification format.

Adapter responsibilities:

- map intent to IDE action,
- hide fields the IDE cannot access,
- preserve correlation ID,
- report delivery status back to Astloom.

## Edge Cases

### Unauthorized Subscriber

A subscriber without tenant or sensitivity clearance does not receive the restricted payload.

### Dead-Letter Replay

After the QA endpoint recovers, operators replay only dead-letter records marked replay-eligible.

### Consumer Crash After Ack

If a consumer acknowledges then crashes mid-side-effect, idempotency keys prevent duplicate Task or notification creation on redelivery.

## Developer Implementation Notes

- Broker delivery is at-least-once; consumers must be idempotent.
- Every message needs schema version and correlation ID.
- Unauthorized subscribers must not receive payloads.
- Dead-letter records must be visible and replayable when safe.
