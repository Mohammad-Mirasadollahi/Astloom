---
doc_id: as.doc.memory.batched-memory-and-deferred-knowledge-workflows-continued
title: 08 - Batched Memory And Deferred Knowledge Workflows (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/02-memory-and-context/08-batched-memory-and-deferred-knowledge-workflows.md`
  — remaining sections after the soft size budget.
tags:
- standard
- memory
phase: 02-memory-and-context
canonical_path: docs/02-memory-and-context/08-batched-memory-and-deferred-knowledge-workflows-continued.md
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

# 08 - Batched Memory And Deferred Knowledge Workflows (Continued)

## Purpose

Continuation of `docs/02-memory-and-context/08-batched-memory-and-deferred-knowledge-workflows.md` — remaining sections after the soft size budget.

## Immediate Actions That Bypass Batching

Some actions must not wait.

Immediate actions:

- secret leak detection.
- destructive operation approval.
- high-risk policy block.
- production credential change detection.
- authentication or authorization risk escalation.
- tenant isolation violation detection.
- critical infrastructure failure alert.
- malware or unsafe command signal.

These actions may still be linked to the WorkBatch, but they execute immediately.

## Product Experience

The web interface should expose WorkBatch state.

Views:

- active batches.
- batch timeline.
- deferred actions.
- readiness score.
- boundary signals.
- immediate guardrails.
- pending documentation updates.
- pending code review.
- memory candidates.
- consolidation results.
- failed deferred actions.

User actions:

- force consolidation.
- mark ready for review.
- request code review.
- request documentation generation.
- split batch.
- merge batches.
- cancel batch.
- mark exploratory.
- approve documentation draft.
- retry failed deferred action.

## Example Flow: One-Line Edit During Active Work

Initial state:

- agent is implementing a feature.
- one line changes in a private helper function.
- tests have not run.

System behavior:

1. records raw Activity.
2. attaches activity to active WorkBatch.
3. updates changed_symbols.
4. LLM classifies work as active feature implementation.
5. documentation_generation is deferred.
6. code_review is deferred.
7. memory_consolidation is deferred.
8. no long-term memory is created yet.

Result:

- evidence is preserved.
- no noisy memory is created.
- no premature documentation is generated.

## Example Flow: Completed Feature

Initial state:

- agent finishes feature implementation.
- tests pass.
- agent produces final response.

System behavior:

1. boundary signal is detected.
2. WorkBatch moves to ready_for_consolidation.
3. memory consolidation summarizes final outcome.
4. docs sync checks final changed symbols.
5. documentation draft is generated for affected public API.
6. code review runs with full batch context.
7. tasks are created only for final unresolved issues.

Result:

- one consolidated memory update.
- one coherent documentation update.
- one code review using final context.

## Example Flow: High-Risk Change

Initial state:

- agent changes authorization middleware.
- work is still active.

System behavior:

1. raw Activity is recorded and attached to WorkBatch.
2. policy detects high-risk authorization change.
3. immediate risk evaluation runs.
4. security review may be requested immediately.
5. ordinary documentation generation still waits for batch boundary.

Result:

- critical risk is not delayed.
- low-value durable knowledge work is still batched.

## Acceptance Criteria

This design is acceptable when:

- raw events are captured without forcing noisy long-term memory writes.
- WorkBatch groups related agent actions into meaningful units.
- LLM batching decisions are structured, explainable, policy-constrained, and configurable.
- memory consolidation, documentation generation, code review, and long-term memory promotion can be deferred until meaningful boundaries.
- single-line or micro-edits do not trigger immediate documentation unless high-risk policy requires it.
- critical security, secret, destructive, tenant isolation, and production policy events bypass batching.
- deferred actions run from final batch state and preserve evidence references.
- users can inspect, force, cancel, split, merge, or retry batches from the web interface.


## Related Documents

- Parent document: `docs/02-memory-and-context/08-batched-memory-and-deferred-knowledge-workflows.md`
