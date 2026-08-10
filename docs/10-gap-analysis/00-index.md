---
doc_id: as.doc.gap.index
title: 10 - Gap Analysis Index
doc_type: index
status: draft
schema_version: '1.0'
owner: platform-docs
summary: This section captures known gaps, unresolved assumptions, and areas that need deeper
  thinking before implementation. The goal is not to block the project. The goal is to make
  uncertainty explicit so the team can review, prioritize, and resolve it later.
tags:
- index
- gap
phase: 10-gap-analysis
canonical_path: docs/10-gap-analysis/00-index.md
lifecycle_lane: future
concern_lane: gap
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols:
- tests/backend/gates/gap-register-verification/run_gate.py::main
doc_version: 1.0.2
updated_at: 2026-08-10
---

# 10 - Gap Analysis Index

## Purpose

This section captures known gaps, unresolved assumptions, and areas that need deeper thinking before implementation. The goal is not to block the project. The goal is to make uncertainty explicit so the team can review, prioritize, and resolve it later.

## Files

- `01-gap-register.md` provides the master gap register.
- `02-architecture-gaps.md` captures system architecture and product design gaps.
- `03-technical-implementation-gaps.md` captures implementation, algorithm, data, and integration gaps.
- `04-governance-operations-gaps.md` captures security, compliance, operational, and process gaps.
- `05-gap-triage-and-resolution-process.md` defines how gaps should be reviewed, owned, prioritized, and closed.
- `06-phase10-verification-and-acceptance.md` defines the gap-register feature gate and named verification commands under `tests/backend/gates/gap-register-verification/`.
- `07-gap002-and-gap-a-live-verification.md` is the **live** acceptance runbook for GAP-002 and GAP-A01–A08 (Compose + real HTTP/MCP; unit-only green is not enough).

## Phase 10 verification home

- Catalog: `backend/configs/governance/gap-register.json`
- Loader: `backend/packages/governance_catalog/`
- Gate package: `tests/support/gap_register_gate/`
- Tests: `tests/backend/gates/gap-register-verification/`

```bash
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/gap-register-verification -q
.venv/bin/python tests/backend/gates/gap-register-verification/run_gate.py
```

## Gap Record Format

Each gap should include:

- Gap ID
- Title
- Category
- Severity
- Impact
- Why it matters
- Current assumption
- Decision needed
- Suggested owner
- Resolution path
- Status

## Status Values

- `OPEN`: identified but not analyzed.
- `UNDER_REVIEW`: owner is investigating.
- `DECISION_NEEDED`: requires architectural or product decision.
- `PLANNED`: accepted and scheduled.
- `CLOSED`: resolved and reflected in documentation or implementation.
- `ACCEPTED_RISK`: known risk accepted by owner.
