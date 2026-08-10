---
doc_id: as.doc.gap.gap-triage-and-resolution-process
title: Gap Triage and Resolution Process
doc_type: gap
status: draft
schema_version: '1.0'
owner: platform-docs
summary: A gap register is only useful if gaps are reviewed and resolved.
tags:
- gap
- gap
phase: 10-gap-analysis
canonical_path: docs/10-gap-analysis/05-gap-triage-and-resolution-process.md
lifecycle_lane: future
concern_lane: gap
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Gap Triage and Resolution Process

## Purpose

A gap register is only useful if gaps are reviewed and resolved. This document defines the process for triaging, owning, and closing gaps.

## Triage Cadence

Recommended cadence:

- Weekly during design phase.
- Twice per week during implementation planning.
- Before every major phase gate.
- After incidents or major architecture changes.

## Severity Levels

### Critical

Blocks safe implementation or creates unacceptable security, data, compliance, or production risk.

### High

Can cause major rework, unsafe automation, unreliable architecture, or significant cost growth.

### Medium

Important for implementation quality but does not block early prototyping.

### Low

Useful improvement or clarification that can be resolved later.

## Triage Questions

For every gap, ask:

1. What can break if this stays unresolved?
2. Which phase depends on the answer?
3. Is this a product decision, architecture decision, technical spike, or operational policy?
4. Who owns the decision?
5. What evidence is needed?
6. What is the smallest resolution artifact?
7. Can this be accepted as risk temporarily?

## Resolution Artifacts

A gap can be closed by one of these artifacts:

- Architecture Decision Record.
- Updated documentation section.
- Technical spike result.
- Prototype or benchmark.
- Contract/schema update.
- Risk acceptance record.
- Product scope decision.
- Operational runbook.
- Test plan or acceptance criteria.

## Gap Lifecycle

```text
OPEN -> UNDER_REVIEW -> DECISION_NEEDED -> PLANNED -> CLOSED
OPEN -> ACCEPTED_RISK
OPEN -> REJECTED_AS_NON_GOAL
```

## Ownership Rules

- Every High or Critical gap must have an owner.
- Every accepted risk must have an approver.
- Every implementation-blocking gap must be linked to a phase gate.
- Every closed gap must update the relevant docs.

## Review Output

Each review should produce:

- updated status,
- owner assignment,
- target resolution date,
- linked Decision or Task,
- new documentation updates if needed.

## Acceptance Criteria

- No Critical gap is ownerless.
- Phase gates list unresolved blocking gaps.
- Closed gaps are reflected in design docs.
- Accepted risks have explicit owners and review dates.
