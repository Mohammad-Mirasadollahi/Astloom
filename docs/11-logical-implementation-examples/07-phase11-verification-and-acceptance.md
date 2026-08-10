---
doc_id: as.doc.examples.phase11-verification-and-acceptance
title: Phase 11 - Verification and Acceptance
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Phase 11 turns architecture into engineer-facing runtime examples and a coding checklist.
tags:
- standard
- examples
phase: 11-logical-implementation-examples
canonical_path: docs/11-logical-implementation-examples/07-phase11-verification-and-acceptance.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- tests/backend/gates/logical-examples-verification/run_gate.py::main
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Phase 11 - Verification and Acceptance

## Purpose

Phase 11 turns architecture into engineer-facing runtime examples and a coding checklist. Its executable gate proves that every major subsystem has a logical example with inputs, processing steps, outputs, state changes, and edge cases, and that examples map to implementation tasks and test hooks.

## Gate Artifacts

| Artifact | Path |
| --- | --- |
| Logical examples docs | `docs/11-logical-implementation-examples/` |
| Examples catalog | `backend/configs/logical-examples/examples-catalog.json` |
| Catalog loader | `backend/packages/logical_examples/` |
| Verification package | `tests/support/logical_examples_gate/` |
| Gate tests | `tests/backend/gates/logical-examples-verification/` |

## Named Commands

```bash
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/logical-examples-verification -q
.venv/bin/python tests/backend/gates/logical-examples-verification/run_gate.py
```

## Exit Checks Covered by the Gate

- Required Phase 11 documents exist and contain key topic markers.
- Examples cover core-data/orchestration, memory, docs/code-graph, rule-engine, and interoperability.
- Each example lists inputs, processing steps, outputs, state changes, edge cases, implementation tasks, and test hooks.
- Example markdown includes Edge Cases and Developer Implementation Notes.
- Developer checklist sections exist so engineers can map examples to coding readiness work.

## Acceptance

Phase 11 passes when `check_phase_gate()` returns `pass` and `run_all_checks()` returns only `passed` results. A documented waiver reference may mark the gate `waived` when an explicit owner accepts temporary failures.
