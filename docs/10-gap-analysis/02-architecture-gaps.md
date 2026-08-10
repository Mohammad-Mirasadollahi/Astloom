---
doc_id: as.doc.gap.architecture-gaps
title: Architecture Gaps
doc_type: gap
status: active
schema_version: '1.0'
owner: platform-docs
summary: >-
  Architecture-level gaps GAP-A01–A08 with backend closures (catalogs, enforcement,
  ChangeSet MVP). UI surfaces remain deferred. Live re-validation is recorded in
  07-gap002-and-gap-a-live-verification.md.
tags:
- gap
- architecture
phase: 10-gap-analysis
canonical_path: docs/10-gap-analysis/02-architecture-gaps.md
lifecycle_lane: current
concern_lane: gap
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols:
- backend/packages/architecture_governance/__init__.py
- backend/configs/governance/bounded-context-map.json
- backend/services/core-data-service/src/core_data_service/core.py::Kind
doc_version: 1.1.4
updated_at: 2026-08-10
---

# Architecture Gaps

## Purpose

This document captures architecture-level gaps. Backend closures for GAP-A01–A08 shipped 2026-07-25; UI/IDE chrome remains deferred where noted.

## GAP-A01 - Bounded Context Map

Resolution: `backend/configs/governance/bounded-context-map.json` + `architecture_governance.forbidden_persistence_violations`.

Status: `CLOSED`

## GAP-A02 - Synchronous vs Asynchronous Boundaries

Resolution: `backend/configs/governance/sync-async-boundaries.json` + `architecture_governance.operation_mode` / `retry_policy` / `timeout_seconds`.

Status: `CLOSED`

## GAP-A03 - Read Model Strategy

Resolution: `backend/configs/governance/read-model-catalog.json` + `architecture_governance.read_model` (tagged on memory/code-graph/audit/guidance paths).

Status: `CLOSED`

## GAP-A04 - Multi-Tenant Deployment Modes

Resolution: `backend/configs/governance/tenancy-deployment-modes.json` + `ASTLOOM_TENANCY_MODE` via `resolve_tenancy_mode` (fail-fast for non-shared modes).

Status: `CLOSED`

## GAP-A05 - Agent Trust Model

Resolution: `backend/configs/governance/agent-trust-policy.json`; package `agent_trust`; adapter `trust_level` enum; rule-engine high-risk escalate with `provider_rank`.

Status: `CLOSED`

## GAP-A06 - Product Boundary Between Astloom and IDEs

Resolution: `backend/configs/governance/ide-product-boundary.json`; MCP `ASTLOOM_GUIDANCE_RESOLVE_REQUIRED` fail-closed writes. IDE plugin chrome / web UI deferred.

Status: `CLOSED` (backend); UI deferred

## GAP-A07 - Enterprise Administration Model

Resolution: `backend/configs/governance/admin-permission-matrix.json` + identity-access authorize + weight/adapter/project-profile guards. Admin UI deferred.

Status: `CLOSED` (backend); UI deferred

## GAP-A08 - Agent Collaboration Surface Completeness

Resolution: core-data `ChangeSet`, `ReviewThread`, `ReviewComment`, `DiscussionComment`, `WorkLabel` kinds + API + self-approval forbid + review-verdict rollup. Diff viewer UX deferred.

Status: `CLOSED` (backend MVP); UX deferred

## Live re-validation

Recurring live/production-like acceptance for GAP-002 and GAP-A01–A08:
`docs/10-gap-analysis/07-gap002-and-gap-a-live-verification.md`.
