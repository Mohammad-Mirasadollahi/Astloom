---
doc_id: as.doc.ckg.structural-isolation-residuals
title: 55 - Structural Isolation And Architecture Overview Residuals
doc_type: standard
status: active
schema_version: '1.0'
owner: code-graph-lead
summary: Honest residual signals after structural edge repair — degree-zero isolation,
  untested hotspots, and Cursor MCP reload so architecture_overview reflects new heuristics.
tags:
- code-graph
- architecture-overview
- isolation
- ingest
- residuals
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/55-structural-isolation-and-architecture-overview-residuals.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/services/code-graph-service/src/code_graph_service/domain/structural_integrity.py::file_needs_contains_repair
- backend/services/code-graph-service/src/code_graph_service/application/ingest/file_ingest.py::FileIngestMixin.ingest_file
- backend/services/code-graph-service/src/code_graph_service/application/ingest/repo_ingest.py::RepoIngestMixin.sync_repo
- tests/backend/services/code-graph-service/test_structural_graph_repair.py::test_file_needs_contains_repair_when_children_lack_contains
- tests/backend/services/code-graph-service/test_structural_graph_repair.py::test_knowledge_gaps_isolation_uses_structural_degree_zero
- tests/backend/services/code-graph-service/test_structural_repair_live.py::test_live_hash_stable_edgeless_file_repairs_on_reingest
- tests/backend/services/code-graph-service/test_structural_repair_live.py::test_live_architecture_knowledge_gaps_use_structural_isolation
- tests/backend/services/code-graph-service/test_structural_repair_live.py::helper
related_docs:
- docs/07-code-knowledge-graph/14-ast-hash-stability-contract.md
- docs/07-code-knowledge-graph/23-code-intelligence-enhancements-high-level-design.md
- docs/08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md
doc_version: 1.0.2
updated_at: 2026-08-10
---

# 55 - Structural Isolation And Architecture Overview Residuals

## Purpose

After hash-stable CONTAINS/CALLS repair, `architecture_overview` knowledge-gap signals are honest residuals — not false positives from skipped re-ingest. This document defines those residuals, operator follow-ups, and the IDE reload step required for Cursor MCP clients.

## Problem And Fix (Context)

| Symptom | Root cause | Fix |
| --- | --- | --- |
| Symbols with real callers appeared isolated | Hash-stable ingest skipped files that lacked CONTAINS edges | `file_needs_contains_repair` + re-ingest / sync repair path |
| Hotspots listed `__init__` / `testing.py` noise | Untested-hotspot heuristic included trivial or test fixture symbols | Filter + `TESTED_BY` ∪ CALLS-from-test callers |

Live gates live under `tests/backend/services/code-graph-service/test_structural_repair_live.py`
(`test_live_hash_stable_edgeless_file_repairs_on_reingest`,
`test_live_architecture_knowledge_gaps_use_structural_isolation`).

## Residual Signal Semantics

| Signal | Meaning after repair | Operator action |
| --- | --- | --- |
| Structural isolate | Symbol degree on structural rels (`CALLS`, `IMPORTS`, …) is **0** | Confirm dead entrypoint, dynamic dispatch, or missing language coverage — then ingest/docs/Task |
| Untested hotspot | High fan-in / centrality without test coverage evidence | Add tests or mark intentional (public SDK / deferred) |
| Thin community | Sparse Louvain/Leiden community | Optional community tool review; not auto-delete |

Do **not** treat residual isolates as ingest bugs until `sync_repo` / file ingest reports no edgeless FILEs needing repair.

## Operator Checklist

1. Run `astloom service restart` (or equivalent) so code-graph + MCP HTTP pick up new code.
2. Trigger repo sync so hash-stable edgeless FILEs enqueue edge repair.
3. Call `astloom_code_graph_architecture_overview` and inspect `knowledge_gaps`.
4. **Reload Cursor MCP** (MCP settings → Reload, or reload window) so the **in-process** IDE overview uses the same heuristics as the host stack. Host restart alone does not refresh an already-loaded Cursor MCP process.
5. File durable Tasks only for residuals that survive sync + reload.

## Verification

| Check | Evidence |
| --- | --- |
| Unit | `test_structural_graph_repair.py` (`test_file_needs_contains_repair_when_children_lack_contains`, `test_knowledge_gaps_isolation_uses_structural_degree_zero`) |
| Live | `test_structural_repair_live.py` (`test_live_hash_stable_edgeless_file_repairs_on_reingest`, `test_live_architecture_knowledge_gaps_use_structural_isolation`) |
| Overview | Isolated degrees are 0 when listed; no `__init__` / `testing.py` hotspot noise |

## Related Documents

- [`14-ast-hash-stability-contract.md`](14-ast-hash-stability-contract.md) — hash identity used by skip/repair decisions
- [`35-usage-profile-and-cursor-mcp-onboarding.md`](../08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md) — Cursor MCP connect and reload
- [`23-code-intelligence-enhancements-high-level-design.md`](23-code-intelligence-enhancements-high-level-design.md) — architecture overview product intent
