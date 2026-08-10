---
doc_id: as.doc.gap.gap-register-continued
title: Master Gap Register (Continued)
doc_type: gap
status: draft
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/10-gap-analysis/01-gap-register.md` — remaining sections after
  the soft size budget.
tags:
- gap
phase: 10-gap-analysis
canonical_path: docs/10-gap-analysis/01-gap-register-continued.md
lifecycle_lane: future
concern_lane: gap
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
doc_version: 1.0.1
updated_at: 2026-08-10
linked_symbols: []
---

# Master Gap Register (Continued)

## Purpose

Continuation of `docs/10-gap-analysis/01-gap-register.md` — remaining sections after the soft size budget.

## GAP-T05 - LLM Judge Determinism

Category: Technical Implementation

Severity: High

Impact: LLM-as-judge needs structured verdicts and replay metadata.

Why it matters: Non-reproducible verdicts break governance.

Current assumption: LiteLLMJudge behind Judge port; HeuristicJudge for local/tests.

Decision needed: Operating standard + adapter + replay tests.

Suggested owner: AI Platform Lead

Resolution path: Standard + LiteLLMJudge + schema + replay tests.

Status: CLOSED

Closed in: `docs/04-rule-engine-orchestration/11-llm-judge-operating-standard.md` + `litellm_judge.py` (2026-07-24).

## GAP-T06 - SDK Language Packaging And Adapter Harness

Category: Technical Implementation

Severity: High

Impact: Ship installable Python and TypeScript SDKs with generator and adapter harness.

Why it matters: Without packaging and harness, integrators cannot build safely.

Current assumption: Private registry policy; generated stubs; capability-validated adapters.

Decision needed: Release plan implemented.

Suggested owner: Developer Experience Lead

Resolution path: Packages + generator + adapter harness + CI.

Status: CLOSED

Closed in: `docs/05-interoperability-ecosystem/11-sdk-release-and-adapter-harness.md` + `astloom_sdk` + `adapter_harness` (2026-07-24).

## GAP-T07 - Port Preflight Tool

Category: Developer Experience

Severity: Medium

Impact: Port conflicts must block startup with owning-process diagnostics and resolved maps.

Why it matters: Silent bind failures look like application bugs.

Current assumption: astloom ports check is the preflight mechanism.

Decision needed: Install/startup wiring + alternate port suggestion.

Suggested owner: Developer Experience Lead

Resolution path: CLI + install gate + resolved port-map artifact.

Status: CLOSED

Closed in: `port_profile` preflight + `astloom ports check` + `scripts/install` `run_port_preflight` (2026-07-24).

## GAP-T08 - Test Data and Fixture Strategy

Category: Technical Implementation

Severity: Medium

Impact: Shared fixture catalog and synthetic workflow generator across domains.

Why it matters: Ad-hoc fixtures hide isolation and coverage gaps.

Current assumption: Cataloged fixtures under tests/backend/fixtures with no secrets.

Decision needed: Catalog + generator + validation tests.

Suggested owner: Platform Governance Lead

Resolution path: Catalog doc + shared fixtures + generator.

Status: CLOSED

Closed in: `docs/08-software-engineering-architecture/51-test-fixture-catalog.md` + `tests/backend/fixtures/` + `synthetic_workflow.py` (2026-07-24).

## GAP-A01 - Bounded Context Map

Category: Architecture

Severity: High

Impact: Formal ownership of entities, readers, events, and migrations across services.

Suggested owner: Platform Architect

Status: CLOSED

Closed in: `backend/configs/governance/bounded-context-map.json` + `architecture_governance` (2026-07-25).

## GAP-A02 - Synchronous vs Asynchronous Boundaries

Category: Architecture

Severity: High

Impact: Operation catalog for sync vs async jobs with durable delivery and timeouts.

Suggested owner: Platform Architect

Status: CLOSED

Closed in: `backend/configs/governance/sync-async-boundaries.json` (2026-07-25).

## GAP-A03 - Read Model Strategy

Category: Architecture

Severity: Medium

Impact: Catalog of materialized vs on-demand read paths with invalidation rules.

Suggested owner: Platform Architect

Status: CLOSED

Closed in: `backend/configs/governance/read-model-catalog.json` (2026-07-25).

## GAP-A04 - Multi-Tenant Deployment Modes

Category: Architecture

Severity: High

Impact: Declared tenancy deployment modes with fail-fast env validation.

Suggested owner: Platform Architect

Status: CLOSED

Closed in: `backend/configs/governance/tenancy-deployment-modes.json` (2026-07-25).

## GAP-A05 - Agent Trust Model

Category: Architecture

Severity: High

Impact: Trust lifecycle policy wired to adapter trust_level and rule-engine high-risk floor.

Suggested owner: Security Lead

Status: CLOSED

Closed in: `backend/configs/governance/agent-trust-policy.json` + rule-engine/adapter wiring (2026-07-25).

## GAP-A06 - Product Boundary Between Astloom and IDEs

Category: Architecture

Severity: Medium

Impact: Action→surface matrix; MCP fail-closed guidance resolve before writes (UI deferred).

Suggested owner: Developer Experience Lead

Status: CLOSED

Closed in: `backend/configs/governance/ide-product-boundary.json` + mcp writes gate (2026-07-25).

## GAP-A07 - Enterprise Administration Model

Category: Architecture

Severity: High

Impact: Admin permission matrix enforced via identity-access authorize (admin UI deferred).

Suggested owner: Platform Governance Lead

Status: CLOSED

Closed in: `backend/configs/governance/admin-permission-matrix.json` (2026-07-25).

## GAP-A08 - Agent Collaboration Surface Completeness

Category: Architecture

Severity: High

Impact: Native ChangeSet / review / discussion / label backend MVP (diff viewer UX deferred).

Suggested owner: Core Data Lead

Status: CLOSED

Closed in: `core-data-service` ChangeSet kinds + API + tests (2026-07-25).


## Related Documents

- Parent document: `docs/10-gap-analysis/01-gap-register.md`
