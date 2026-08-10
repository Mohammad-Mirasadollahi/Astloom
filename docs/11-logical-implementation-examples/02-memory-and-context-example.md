---
doc_id: as.doc.examples.memory-and-context-example
title: Logical Example - Memory and Context
doc_type: example
status: draft
schema_version: '1.0'
owner: platform-docs
summary: An agent is asked to fix a PayPal timeout bug. The project previously used Stripe,
  but PayPal is the current gateway. The memory system must retrieve current PayPal context
  and avoid injecting obsolete Stripe history unless requested.
tags:
- example
- examples
phase: 11-logical-implementation-examples
canonical_path: docs/11-logical-implementation-examples/02-memory-and-context-example.md
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

# Logical Example - Memory and Context


## Purpose

An agent is asked to fix a PayPal timeout bug. The project previously used Stripe, but PayPal is the current gateway. The memory system must retrieve current PayPal context and avoid injecting obsolete Stripe history unless requested.

## Scenario

An agent is asked to fix a PayPal timeout bug. The project previously used Stripe, but PayPal is the current gateway. The memory system must retrieve current PayPal context and avoid injecting obsolete Stripe history unless requested.

## Input

```text
Task: Fix timeout handling in paypal_checkout.py
Domain: payments
Risk level: HIGH
Agent role: Backend Agent
```

## Relevant Memory Items

```text
MemoryItem A:
    type: SEMANTIC
    content: Current payment gateway is PayPal API v2.
    status: ACTIVE

MemoryItem B:
    type: EPISODIC
    content: Project previously migrated away from Stripe.
    status: HISTORICAL

MemoryItem C:
    type: SEMANTIC
    content: PayPal requests require idempotency keys.
    status: ACTIVE

MemoryItem D:
    type: DEPRECATED
    content: Stripe checkout flow uses stripe_checkout.tsx.
    status: DEPRECATED
```

## Weight Profile Selection

The Memory Service selects a WeightProfile.

```text
tenant: tenant-a
project: ecommerce-platform
domain: payments
task_type: bug_fix
risk_level: HIGH
```

The profile increases weight for:

- active Decisions,
- current payment facts,
- security and revenue rules,
- recently successful PayPal fixes,
- human-verified facts.

The profile decreases weight for:

- deprecated Stripe memory,
- historical migration events,
- low-confidence generated notes,
- unrelated frontend-only facts.

## Retrieval Flow

```text
1. Start from Task domain: payments.
2. Retrieve active SemanticFacts for payments.
3. Traverse graph to PayPal docs and code symbols.
4. Apply WeightProfile.
5. Exclude deprecated Stripe memory from default context.
6. Include historical Stripe migration only if task asks about migration history.
7. Build ContextBundle.
```

## Output ContextBundle

```text
ContextBundle:
    task_id: TASK-PAYPAL-TIMEOUT
    included:
        - Current gateway is PayPal API v2.
        - PayPal requests require idempotency keys.
        - Relevant Decision about payment gateway migration.
        - paypal_checkout.py symbol docs.
        - timeout retry policy.
    omitted:
        - Stripe checkout memory: deprecated.
        - old migration event log: historical and not needed.
```

## Prompt Behavior

The agent sees:

```text
Current payment gateway is PayPal API v2.
All PayPal payment requests require idempotency keys.
Your task is to fix timeout handling in paypal_checkout.py.
```

The agent does not see old Stripe details unless it asks for historical migration context.

## Forgotten Memory Example

Suppose there is an old incident note:

```text
PayPal timeout retries once caused duplicate charges.
```

It is old and rarely retrieved, but it has high incident recovery value. The forgotten-memory classifier marks it as DORMANT_BUT_IMPORTANT instead of obsolete.

For payment timeout tasks, the WeightProfile boosts incident recovery value, so this memory is included.

## Edge Cases

### Age Alone Hides Critical Memory

If retrieval ranks only by recency, the dormant incident note is omitted and the agent repeats a known duplicate-charge failure.

### Historical Context Requested Explicitly

When the task asks about migration history, omitted Stripe migration memory may be included; otherwise it stays out of the default ContextBundle.

### Missing WeightProfile

If no WeightProfile exists for the domain, prompt assembly fails closed instead of falling back to hard-coded weights.

## Developer Implementation Notes

- Retrieval should explain included and omitted items.
- Age alone must not hide incident-critical memory.
- Weight values must come from WeightProfile, not hard-coded constants.
- ContextBundle must preserve source refs and redaction status.
