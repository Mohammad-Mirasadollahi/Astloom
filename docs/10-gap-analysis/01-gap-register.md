---
doc_id: as.doc.gap.gap-register
title: Master Gap Register
doc_type: gap
status: draft
schema_version: '1.0'
owner: platform-docs
summary: This register lists the most important gaps currently visible in the Astloom design.
  Each gap should eventually become a Decision, Task, Risk, or accepted non-goal.
tags:
- gap
phase: 10-gap-analysis
canonical_path: docs/10-gap-analysis/01-gap-register.md
lifecycle_lane: future
concern_lane: gap
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
doc_version: 1.2.2
updated_at: 2026-08-10
linked_symbols:
- tests/backend/configs/test_domain_customization_schemas.py::test_first_party_configs_match_schemas
---

# Master Gap Register

## Purpose

This register lists the most important gaps currently visible in the Astloom design. Each gap should eventually become a Decision, Task, Risk, or accepted non-goal.

## GAP-001 - Storage Boundary Finalization

Category: Architecture

Severity: High

Impact: The documentation defines multiple storage types, but final ownership between relational storage, Neo4j, object storage, broker persistence, vector indexes, and configuration storage still needs a concrete implementation decision.

Why it matters: Incorrect storage ownership can create duplicate truth, difficult migrations, and inconsistent audit behavior.

Current assumption: Core entities live outside Neo4j, code relationships live in Neo4j, artifacts live in object storage, and events live in broker persistence or event storage.

Decision needed: None — entity→store matrix published.

Suggested owner: Platform Architect

Approver: Platform Architect

Review date: 2026-07-23

Resolution path: Storage ownership matrix + product-per-role stack baseline.

Status: CLOSED

Closed in: `docs/13-technology-stack-and-platform-decisions/13-storage-ownership-matrix.md` (2026-07-23).

## GAP-002 - First Supported Language Set

Category: Technical Implementation

Severity: High

Impact: Tree-sitter supports many languages, but the first implementation must choose supported languages and parser behavior.

Why it matters: Symbol extraction, call resolution, import resolution, and AST hashing differ by language.

Current assumption: **Python is mandatory**; TypeScript, JavaScript, Go, Rust, and **Java** are supported via tree-sitter adapters. See `docs/07-code-knowledge-graph/10-language-support-policy.md`.

Decision needed: None — Java parser + Spring/Wire DI extraction shipped (2026-07-25). Exotic frameworks beyond FastAPI/Nest/Spring/Wire remain iterative.

Suggested owner: Code Graph Lead

Approver: Code Graph Lead

Review date: 2026-07-25

Resolution path: Cross-language CALLS/IMPORTS + package manifests + DI CALLS (`provenance=di_injection`) including Spring/Wire + `confidence_policy.clamp_confidence`.

Status: CLOSED

Closed in: `domain/parsers/java_lang.py`, `domain/di_injections.py` (Spring/Wire), language policy 1.1.0 (2026-07-25).
Exotic frameworks beyond FastAPI / Nest / Spring / Wire remain iterative.
## GAP-003 - LLM Provider and Local Model Strategy

Category: Technical Implementation

Severity: High

Impact: The design references local and cloud models; Astloom needed a single gateway so services do not integrate each vendor SDK separately.

Why it matters: Cost, latency, privacy, and quality depend on model routing and a consistent integration surface.

Current assumption: **LiteLLM is the approved LLM gateway** for all Astloom-initiated model calls. `ModelRoutingProfile` maps task type / risk / tenant / environment to LiteLLM model aliases (local Ollama/OpenAI-compatible and cloud providers). Durable embedding **storage** remains PostgreSQL+pgvector. See `docs/13-technology-stack-and-platform-decisions/09-litellm-llm-gateway.md`.

Decision needed: None — LiteLLM gateway accepted; default local/cloud `ModelRoutingProfile`
tables published under `backend/configs/model-routing/`.

Suggested owner: AI Platform Lead

Approver: Platform Architect

Review date: 2026-07-23

Resolution path: ADR `09-litellm-llm-gateway.md`; profile standard
`10-model-routing-profiles-with-litellm.md`; JSON profiles + schema; `llm_gateway.resolve_route`
loads file defaults with env overrides.

Status: CLOSED

Closed in: `docs/13-technology-stack-and-platform-decisions/10-model-routing-profiles-with-litellm.md`
+ `backend/configs/model-routing/` (2026-07-23).

## GAP-004 - Human Approval UX

Category: Product and Workflow

Severity: Medium

Impact: The system defines escalation tickets but does not yet define the exact UI or integration surface for approvals.

Why it matters: Poor approval UX will slow teams and cause rubber-stamping.

Current assumption: Approval can happen through platform UI, IDE, Slack, Jira, or other workflow tools. Interaction model for Accept vs Auto-Approve is specified in `docs/04-rule-engine-orchestration/09-approval-modes-and-auto-approve.md` (`manual`, `auto_approve`, `system_routed`).

Decision needed: None — first surface is Astloom CLI (`astloom approval`).

Suggested owner: Product Lead

Resolution path: CLI Accept queue + ApprovalModeProfile catalog; web/IDE deferred.

Status: CLOSED

Closed in: `docs/04-rule-engine-orchestration/10-approval-cli-first-surface.md` +
`backend/packages/approval_modes/` + `astloom approval` CLI (2026-07-23).

## GAP-005 - Tenant Isolation Implementation Details

Category: Security

Severity: Critical

Impact: Tenant isolation is required, but exact implementation across graph, memory, broker, object storage, and vector indexes needs more detail.

Why it matters: Tenant boundary failure is a critical security issue.

Current assumption: Every entity and event carries tenant ID and access checks run before retrieval or delivery.

Decision needed: Define isolation enforcement strategy per storage and service boundary.

Suggested owner: Security Architect

Resolution path: Threat model + enforceable tests for code-graph store and MCP scope (wedge). Broader broker/object-store surfaces remain follow-up.

Status: CLOSED

Closed in: `docs/09-platform-governance-operations/tenant-isolation-threat-model.md` +
`tests/.../test_tenant_isolation.py` / `test_mcp_tenant_isolation.py` (2026-07-21).
v1 commercial mode: **single-tenant lab OK**; multi-tenant SaaS claims blocked until remaining platform surfaces are covered.

## GAP-006 - Weight Profile Governance

Category: Memory and Retrieval

Severity: Medium

Impact: WeightProfiles and GraphRetrievalProfiles are defined, but ownership, approval, and rollback policy are not yet fully specified.

Why it matters: Bad weights can hide important memory or over-prioritize stale context.

Current assumption: Profiles are versioned and auditable.

Decision needed: None — Memory Platform Lead approves catalog profiles; CLI activate/rollback is the operator path.

Suggested owner: Memory Platform Lead

Resolution path: Governance standard + catalog + CLI activate/rollback tests.

Status: CLOSED

Closed in: `docs/02-memory-and-context/12-weight-profile-governance.md` +
`backend/packages/weight_profiles/` + `astloom weight-profile` CLI (2026-07-23).

## GAP-007 - Development Port Profile Ownership

Category: Developer Experience

Severity: Medium

Impact: Non-default development ports are documented, but ownership of the default profile and update process needs definition.

Why it matters: Conflicting local setups can create friction if port policy is unclear.

Current assumption: Development ports are configurable and project-scoped.

Decision needed: Choose default development base and ownership of port profile changes.

Suggested owner: Developer Experience Lead

Resolution path: Port profile file format and Phase 8 gate ownership checks.

Status: CLOSED

Closed in: Phase 8 port-profile catalog and verification gate (`docs/08-software-engineering-architecture/34-phase8-verification-and-acceptance.md`).

## GAP-008 - Schema Registry Implementation

Category: Contract Governance

Severity: Medium

Impact: Schema registry is recommended but not implemented in the design as a concrete service or repository module.

Why it matters: Without schema registry, broker events and adapter contracts may drift.

Current assumption: A versioned schema catalog exists.

Decision needed: None — v1 schema registry is a **repository-directory catalog**.

Suggested owner: Platform Architect

Approver: Platform Architect

Review date: 2026-07-23

Resolution path: Architecture ADR + `backend/tools/schema-registry/catalog.json` indexing
first-party schemas under `backend/configs/`; pytest validates catalog paths.

Status: CLOSED

Closed in: `docs/09-platform-governance-operations/12-schema-registry-architecture.md` (2026-07-23).

## GAP-009 - Domain Pack, Feature Profile, And Rule Suggestion Governance

Category: Product Architecture and Configuration Governance

Severity: High

Impact: Astloom now defines domain packs, feature profiles, user-authored rules, and conversation-derived rule suggestions, but the final schema ownership, approval workflow, conflict resolution policy, and rollout model still need implementation-level decisions.

Why it matters: These mechanisms control what users see, what agents can do, which rules apply, and how non-engineering domains are simplified. A weak governance model could cause confusing behavior, accidental feature exposure, cross-project leakage, or unsafe automatic rule activation.

Current assumption: Domain packs, feature profiles, and suggested rules are versioned, scoped, auditable, dry-run capable, and approval-gated by default.

Decision needed: None — schemas, precedence, and activation workflow published.

Suggested owner: Product Architect and Platform Architect

Approver: Platform Architect

Review date: 2026-07-23

Resolution path: Formal schemas under `backend/configs/` plus governance standard and unit schema tests.

Status: CLOSED

Closed in: `docs/04-rule-engine-orchestration/08-domain-pack-feature-profile-and-rule-suggestion-schemas.md` + JSON Schema files + `tests/backend/configs/test_domain_customization_schemas.py` (2026-07-23).

## GAP-010 - Impact KPI Instrumentation Completeness

Category: Governance and Operations

Severity: Medium

Impact: Impact KPIs need machine-checkable fields and an explicit comparison method.

Why it matters: Without instrumentation completeness, benefit reporting cannot be audited.

Current assumption: KPI catalogs are versioned and gate-checked.

Decision needed: Ensure KPI fields and comparison method are machine-checkable.

Suggested owner: Platform Governance Lead

Resolution path: Impact KPI catalog and Phase 9 gate.

Status: CLOSED

Closed in: Phase 9 impact-kpis catalog and verification gate (`docs/09-platform-governance-operations/11-phase9-verification-and-acceptance.md`).

## GAP-011 - Neo4j as Code Graph Store Timing

Category: Architecture

Severity: Medium

Impact: Phase 7 previously used a Postgres `code_graph` slice by default while Neo4j was an alternate Store backend.

Why it matters: Delayed migration can create dual-write debt; early migration can block language-matrix work.

Current assumption: **Neo4j is the default structural store** (`ASTLOOM_CODE_GRAPH_STORE=neo4j`). PostgreSQL remains available for rollback and parity (`ASTLOOM_CODE_GRAPH_STORE=postgres`). **Python support remains mandatory across both stores.**

Decision needed: None — cutover default completed.

Suggested owner: Code Graph Lead

Approver: Platform Architect

Review date: 2026-07-20

Resolution path: Default flipped to Neo4j; Postgres retained for rollback; structural parity via `domain/parity.py`; projection ADR `docs/07-code-knowledge-graph/13-codesymbol-projection-adr.md`. Follow `docs/07-code-knowledge-graph/11-neo4j-migration-plan.md`.

Status: CLOSED

Closed in: Neo4j default store + CodeSymbol projection ADR (2026-07-20).

## GAP-T01 - AST Hash Stability

Category: Technical Implementation

Severity: High

Impact: Normalized AST/source hashes must be language-correct and stable across formatting-only edits.

Why it matters: Unstable hashes break incremental ingest and false-positive change detection.

Current assumption: Language-aware normalization with parser/hash version metadata.

Decision needed: Ship contract + corpus-backed hashing.

Suggested owner: Code Graph Lead

Resolution path: Hash contract + language-safe hashing + frozen corpus.

Status: CLOSED

Closed in: `docs/07-code-knowledge-graph/14-ast-hash-stability-contract.md` + `domain/hashing.py` + `test_hash_corpus.py` (2026-07-24).

## GAP-T02 - Call Graph Accuracy

Category: Technical Implementation

Severity: High

Impact: Call resolution needs confidence, DI/dynamic/reflection rules, and runtime-observed edges.

Why it matters: Wrong CALLS poison impact analysis.

Current assumption: Static + runtime_trace provenance with confidence caps.

Decision needed: Operating standard + accuracy gate.

Suggested owner: Code Graph Lead

Resolution path: Confidence standard + runtime ingest + labeled corpus.

Status: CLOSED

Closed in: `docs/07-code-knowledge-graph/15-call-graph-confidence-and-runtime-traces.md` + `runtime_traces.py` + accuracy gate (2026-07-24).

## GAP-T03 - Embedding Storage and Refresh Policy

Category: Technical Implementation

Severity: High

Impact: Full embedding lifecycle and optional TurboVec Stage-2 for code-graph and memory.

Why it matters: Stale embeddings and missing ANN acceleration limit retrieval quality.

Current assumption: pgvector SoR; TurboVec optional replica; model-change refresh jobs.

Decision needed: Lifecycle + dual-service TurboVec wiring.

Suggested owner: AI Platform Lead

Resolution path: Refresh job/CLI + memory embeddings + vector_index package.

Status: CLOSED

Closed in: `docs/13-technology-stack-and-platform-decisions/14-embedding-lifecycle-and-refresh.md` + `vector_index` + memory embeddings (2026-07-24).

## GAP-T04 - Prompt Context Verification

Category: Technical Implementation

Severity: High

Impact: ContextBundles need audit schema and verification against retrieval state.

Why it matters: Unverified prompts hide omissions and stale sources.

Current assumption: Versioned audit schema + verifier + prompt-safety suite.

Decision needed: Ship schema and tests.

Suggested owner: Memory Platform Lead

Resolution path: JSON Schema + verifier + safety/fuzz tests.

Status: CLOSED

Closed in: `docs/02-memory-and-context/13-context-bundle-audit-and-verification.md` + `bundle_verifier.py` (2026-07-24).

## Related Documents

- Continued in `docs/10-gap-analysis/01-gap-register-continued.md`
