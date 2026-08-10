---
doc_id: as.doc.sea.transaction-idempotency-and-concurrency-standards
title: 32 - Transaction, Idempotency, And Concurrency Standards
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines standards for safe state changes, retries, background jobs,
  concurrent workflows, and event-driven processing.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/32-transaction-idempotency-and-concurrency-standards.md
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

# 32 - Transaction, Idempotency, And Concurrency Standards

## Purpose

This document defines standards for safe state changes, retries, background jobs, concurrent workflows, and event-driven processing.

## Transaction Boundary Standard

Each use case must define its transaction boundary explicitly. A transaction should protect one aggregate or one consistency boundary. Cross-service workflows should use events, sagas, outbox, inbox, and compensating actions instead of distributed database transactions.

## Idempotency Standard

Retryable operations must be idempotent. This includes:

- API commands that may be retried by clients.
- broker message consumers.
- graph upserts.
- documentation generation jobs.
- embedding generation jobs.
- memory consolidation jobs.
- connector sync jobs.
- deployment automation steps.

Idempotency keys must include enough scope to avoid accidental cross-project collisions.

## Outbox And Inbox

State changes that publish events should use an outbox pattern. Event consumers that modify state should use an inbox or processed-message record. This prevents duplicate processing when retries happen.

## Concurrency Control

Astloom should use optimistic concurrency for user-facing aggregate updates and versioned records. Background jobs should use leases, locks, or compare-and-swap behavior when multiple workers can process the same work.

## Retry Standard

Retries must be:

- bounded.
- observable.
- idempotency-aware.
- classified by retryable failure type.
- backed off with jitter where appropriate.
- routed to dead-letter handling when exhausted.

Unbounded retries are forbidden.

## Race Conditions To Design For

- two agents updating the same task.
- graph ingestion and docs sync seeing different revisions.
- memory consolidation running while a user edits memory.
- rule evaluation changing while an automation job is running.
- connector sync receiving duplicate external events.
- common context proposal and user override happening together.

## Acceptance Criteria

A workflow is acceptable when retries do not duplicate logical state, concurrent updates are detected, event publication is durable, failed messages can be inspected, and every high-risk state transition has an audit trail.
