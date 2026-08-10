---
doc_id: as.doc.ckg.dead-code-quality-hardening-plan
title: Dead-Code Quality Hardening Implementation Plan
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-engineering
summary: Implementation plan to harden dead-code unused-candidates quality (path_prefix,
  guidance floor, live probe) without a Memory candidate SoT.
tags:
- dead-code
- code-graph
- plan
- quality
phase: 07-code-knowledge-graph
canonical_path: docs/superpowers/plans/2026-08-04-dead-code-quality-hardening.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols:
- backend/services/code-graph-service/src/code_graph_service/application/queries.py::QueryUseCases
- backend/services/mcp-gateway-service/src/mcp_gateway_service/backends/code_graph/query.py::unused_candidates
- backend/services/mcp-gateway-service/src/mcp_gateway_service/backends/code_graph/query.py::search
- backend/packages/astloom_cli/commands/quality_audit/collect.py::build_quality_audit_report
related_docs:
- docs/07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md
- docs/07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Dead-Code Quality Hardening Implementation Plan

## Purpose

Ship quality hardening for dead-code unused-candidates (`path_prefix`, guidance score floor, live HTTP probe) while keeping the Code-Knowledge Graph as the only candidate source of truth.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement task-by-task.

**Goal:** Raise dead-code detection and cleanup-loop quality (precision, scoped coverage, agent loop) without a separate candidate Memory SoT.

**Architecture:** Keep the Code-Knowledge Graph as the only candidate truth. Add optional `path_prefix` so `project_scan` reports only under a package while reachability still uses the full graph. Tighten guidance/quality-audit so agents act only on `safe_to_delete` with `score ≥ 0.8` in the same change. Prove with unit + real MCP HTTP live probes.

**Tech Stack:** `code-graph-service` domain, MCP gateway, `programming-cursor-mcp.json`, seed skill, quality-audit CLI, pytest live HTTP.

## Global Constraints

- No dedicated dead-code Memory/queue SoT (graph + optional human Task later).
- Astloom never deletes repository files.
- Scores only decrease; triage cannot raise `safe_to_delete`.
- English docs; bump `doc_version` on normative doc 36.
- Tests ship with the behavior change.

---

## Task 1: `path_prefix` on unused candidates

**Files:**
- `backend/services/code-graph-service/src/code_graph_service/domain/unused_candidates.py`
- `backend/services/code-graph-service/src/code_graph_service/application/queries.py`
- `backend/services/mcp-gateway-service/src/mcp_gateway_service/backends/code_graph/query.py`
- `backend/configs/usage-profiles/programming-cursor-mcp.json`

- [x] Add optional `path_prefix`; filter report pool by path; keep full-graph liveness
- [x] Echo `path_prefix` on response when set
- [x] Wire MCP + profile schema
- [x] Unit: prefix filters noise; cross-package caller keeps callee live

## Task 2: Guidance + quality audit

**Files:**
- `backend/services/common-context-service/src/common_context_service/seed_mcp_first_prompts/skills/astloom-remove-dead-code.md`
- `backend/packages/astloom_cli/commands/quality_audit/categories.py`
- `backend/packages/astloom_cli/commands/quality_audit/collect.py` (hint text if needed)

- [x] Skill: same-change cleanup; prefer `path_prefix` for discovery; graph SoT not Memory
- [x] Audit fix_hint mentions `path_prefix` + score floor

## Task 3: Normative doc + live probe

**Files:**
- `docs/07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md`
- `tests/live/code-graph-service/test_unused_candidates_mcp_http_live.py`
- fixtures under `tests/live/code-graph-service/fixtures/dead_code_sample/`

- [x] Doc: `path_prefix`, quality hardening, no Memory SoT; bump version
- [x] Live: ingest fixture, scan with `path_prefix`, assert orphan found and live not safe-delete
- [x] Restart Astloom MCP; run live probe for real

## Related Documents

- [`../../07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md`](../../07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md) — normative dead-code loop.
- [`../../07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md`](../../07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md) — sister stale-docs loop.
