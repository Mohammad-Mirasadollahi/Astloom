---
doc_id: as.doc.interop.data-contracts-and-events
title: Interoperability and Enterprise Ecosystem - Data Contracts and Events
doc_type: contract
status: active
schema_version: '1.0'
owner: platform-docs
summary: '- `AgentMessage(id, sender, intent, domain, payload, status, refs, correlation_id)`
  - `Channel(id, name, domain, subscribers, retention_policy, access_policy)` - `Subscription(id,
  channel_id, subscriber_type, endpoint, filter, status)` - `Adapter(id, vendor, capability_map,
  auth_.'
tags:
- contract
- interop
phase: 05-interoperability-ecosystem
canonical_path: docs/05-interoperability-ecosystem/04-data-contracts-and-events.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Interoperability and Enterprise Ecosystem - Data Contracts and Events


## Purpose

- `AgentMessage(id, sender, intent, domain, payload, status, refs, correlation_id)` - `Channel(id, name, domain, subscribers, retention_policy, access_policy)` - `Subscription(id, channel_id, subscriber_type, endpoint, filter, status)` - `Adapter(id, vendor, capability_map, auth_.

## Core Entities

- `AgentMessage(id, sender, intent, domain, payload, status, refs, correlation_id)`
- `Channel(id, name, domain, subscribers, retention_policy, access_policy)`
- `Subscription(id, channel_id, subscriber_type, endpoint, filter, status)`
- `Adapter(id, vendor, capability_map, auth_profile, trust_level, status)`
- `DepartmentWorkflow(id, domain, trigger_event, tasks, approvals, owners)`

## Universal Agent JSON Required Fields

- `message_id`
- `sender`
- `intent`
- `domain`
- `payload`
- `status`
- `refs`
- `correlation_id`
- `created_at`

## Events

- `agent.message_received`
- `broker.event_published`
- `subscription.delivered`
- `subscription.failed`
- `adapter.normalized_output`
- `ide.notification_sent`
- `department.task_created`
- `dead_letter.created`

## Contract Rules

- Broker messages must be structured, replayable, and authorized.
- Adapters must declare capabilities and schema versions.
- Failed deliveries must be visible in a dead-letter queue.
- Cross-domain workflow events must preserve audit and approval references.
- Tenant and project boundaries must be enforced before delivery or context injection.
