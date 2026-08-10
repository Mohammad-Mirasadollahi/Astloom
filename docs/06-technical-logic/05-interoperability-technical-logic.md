---
doc_id: as.doc.tech.interoperability-technical-logic
title: Interoperability Technical Logic
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: The Interoperability layer allows different agents, IDEs, tools, and departments
  to communicate through stable contracts. It hides vendor-specific formats behind adapters
  and exposes structured events through a broker.
tags:
- standard
- tech
phase: 06-technical-logic
canonical_path: docs/06-technical-logic/05-interoperability-technical-logic.md
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

# Interoperability Technical Logic


## Purpose

The Interoperability layer allows different agents, IDEs, tools, and departments to communicate through stable contracts. It hides vendor-specific formats behind adapters and exposes structured events through a broker.

## Technical Goal

The Interoperability layer allows different agents, IDEs, tools, and departments to communicate through stable contracts. It hides vendor-specific formats behind adapters and exposes structured events through a broker.

## Universal Agent JSON Contract

A valid message must include:

```text
message_id
schema_version
sender
sender_type
tenant_id
project_id
intent
domain
payload
status
refs
correlation_id
created_at
```

Optional fields:

```text
capabilities
requires_response
reply_to
priority
expires_at
sensitivity
idempotency_key
```

## Message Validation Logic

```text
validate_message(message):
    validate_schema_version(message)
    validate_required_fields(message)
    validate_sender_identity(message)
    validate_tenant_and_project_scope(message)
    validate_intent_allowed_for_sender(message)
    validate_payload_shape_for_intent(message)
    validate_refs_exist_or_are_external(message)
    validate_sensitivity_and_access_policy(message)
```

Invalid messages should be rejected before reaching internal orchestration.

## Intent Model

Intent describes why the message exists.

Common intents:

- `TASK_STARTED`
- `TASK_COMPLETED`
- `TASK_BLOCKED`
- `API_READY`
- `DOC_DRIFT_FOUND`
- `TEST_FAILURE_DETECTED`
- `HUMAN_APPROVAL_REQUIRED`
- `APPROVAL_RESOLVED`
- `DEPLOYMENT_COMPLETED`
- `DOWNSTREAM_TASK_REQUESTED`

Every intent should define required payload fields and allowed status values.

## Broker Routing Logic

The broker routes validated messages to channels and subscribers.

```text
publish(message):
    validate_message(message)
    channel_set = resolve_channels(message.intent, message.domain, message.refs)
    for channel in channel_set:
        assert publisher_allowed(message.sender, channel)
        persist_event(channel, message)
        deliver_to_subscribers(channel, message)
```

Subscription filters may include:

- domain,
- intent,
- project,
- severity,
- affected entity,
- owner team,
- sensitivity level.

## Delivery Semantics

The platform should support at-least-once delivery with idempotent consumers.

Required delivery behavior:

- persist before delivery,
- retry transient failures,
- preserve delivery attempts,
- dead-letter permanent failures,
- support replay by channel and time range,
- preserve correlation ID.

Exactly-once delivery should not be assumed. Consumers must use idempotency keys.

## Adapter Runtime Logic

Adapters translate vendor-specific inputs and outputs into Universal Agent JSON.

Adapter pipeline:

```text
receive_vendor_event()
identify_vendor_schema_version()
map_vendor_fields_to_astloom_contract()
normalize_status_and_intent()
attach capability profile
redact or restrict sensitive fields
validate Universal Agent JSON
publish to broker
```

Capability profile examples:

- can_edit_code,
- can_run_tests,
- can_open_pr,
- can_modify_infrastructure,
- can_access_customer_data,
- requires_human_review,
- max_trust_level.

## Context Injection Bridge

External tools should not receive full project memory. The bridge builds scoped context packages.

Context authorization checks:

- tenant match,
- project match,
- user or agent role,
- Task assignment,
- sensitivity clearance,
- policy constraints,
- data retention rules.

If a tool cannot receive restricted context, the bridge should provide a redacted summary or deny injection.

## Tenant Boundary Logic

Tenant boundaries apply before routing, retrieval, and delivery.

Rules:

- A message from one tenant cannot reference private entities from another tenant.
- Broker channels are tenant-scoped unless explicitly configured otherwise.
- ContextBundles are tenant and project scoped.
- Adapter credentials are scoped to tenant and integration.
- Cross-tenant analytics must use anonymized aggregate data only.

## Dead-Letter Logic

A message enters the dead-letter queue when:

- subscriber endpoint repeatedly fails,
- schema version is unsupported,
- authorization fails after publish,
- payload cannot be transformed,
- message expires before delivery.

Dead-letter records should include:

- original message reference,
- channel,
- subscriber,
- failure reason,
- attempt count,
- last error,
- replay eligibility.

## Cross-Domain Workflow Logic

Engineering events can create department workflows.

Example mapping:

```text
if event.intent == DEPLOYMENT_COMPLETED and event.domain == Campaign:
    create DevOps monitoring Task
    create Support knowledge base Task
    create Marketing launch confirmation Task
```

Business workflows require stronger governance because their effects may be public, financial, or legal.

## Failure Handling

- If adapter mapping fails, store raw external event in restricted evidence and emit adapter failure.
- If schema version is unknown, reject or route to compatibility adapter.
- If broker delivery fails, retry and then dead-letter.
- If context injection is denied, return an explicit denied response with reason code.
- If two agents update the same Task, use Task state machine and idempotency checks.
