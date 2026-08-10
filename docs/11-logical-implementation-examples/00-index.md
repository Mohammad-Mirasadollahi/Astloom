---
doc_id: as.doc.examples.index
title: 11 - Logical Implementation Examples Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: This section explains Astloom through concrete implementation-oriented examples.
  It is written for engineers who need to understand how the design behaves before they start
  coding.
tags:
- index
- examples
phase: 11-logical-implementation-examples
canonical_path: docs/11-logical-implementation-examples/00-index.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols:
- tests/backend/gates/logical-examples-verification/run_gate.py::main
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 11 - Logical Implementation Examples Index

## Purpose

This section explains Astloom through concrete implementation-oriented examples. It is written for engineers who need to understand how the design behaves before they start coding.

The earlier sections define architecture, contracts, technical logic, governance, and gaps. This section turns those ideas into practical scenarios with inputs, processing steps, outputs, records, state changes, and edge cases.

## Files

- `01-end-to-end-password-migration-example.md` shows how all major systems work together for a password hashing migration.
- `02-memory-and-context-example.md` shows current-state memory, forgotten-memory weighting, retrieval, and prompt bundle creation.
- `03-docs-and-code-graph-example.md` shows code ingestion, documentation drift, AST hashing, Neo4j graph updates, and graph-guided code generation.
- `04-rule-engine-and-human-approval-example.md` shows policy evaluation, deterministic checks, LLM judge use, escalation, and approval outcomes.
- `05-interoperability-and-broker-example.md` shows Universal Agent JSON, broker routing, IDE notification, adapter behavior, and dead-letter handling.
- `06-developer-implementation-checklist.md` gives an engineering checklist for implementing each subsystem.
- `07-phase11-verification-and-acceptance.md` defines the logical-examples feature gate and named verification commands under `tests/backend/gates/logical-examples-verification/`.
- `08-turbovec-hybrid-retrieval-example.md` shows Stage-1 SQL/ACL candidate narrowing plus optional turbovec `IdMapIndex` allowlist dense rerank (see stack ADR `13/08` and RAG guide `13/11`).

## Phase 11 verification home

- Catalog: `backend/configs/logical-examples/examples-catalog.json`
- Loader: `backend/packages/logical_examples/`
- Gate package: `tests/support/logical_examples_gate/`
- Tests: `tests/backend/gates/logical-examples-verification/`

```bash
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/logical-examples-verification -q
.venv/bin/python tests/backend/gates/logical-examples-verification/run_gate.py
```

## How to Use This Section

Read this section after the technical logic documents. It should help engineers answer:

- What input does the subsystem receive?
- Which records are created?
- Which events are emitted?
- Which state changes happen?
- Which errors or edge cases must be handled?
- What should be tested before implementation is considered complete?
