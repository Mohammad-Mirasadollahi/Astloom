---
doc_id: as.doc.ops.risk-register-and-open-decisions
title: Risk Register and Open Decisions
doc_type: gap
status: active
schema_version: '1.0'
owner: platform-docs
summary: Tracked product risks and closed-vs-open decisions for Astloom platform
  governance, aligned to the official gap register.
tags:
- gap
- ops
- risk-register
- decisions
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/07-risk-register-and-open-decisions.md
lifecycle_lane: current
concern_lane: gap
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
related_docs:
- docs/13-technology-stack-and-platform-decisions/13-storage-ownership-matrix.md
- docs/02-memory-and-context/12-weight-profile-governance.md
- docs/05-interoperability-ecosystem/11-sdk-release-and-adapter-harness.md
- docs/08-software-engineering-architecture/04-development-port-management.md
doc_version: 1.1.1
updated_at: 2026-08-10
---

# Risk Register and Open Decisions

## Purpose

This document captures important risks and decisions that should be tracked before and after implementation. It prevents hidden assumptions from becoming architectural debt. Decision closures below mirror `backend/configs/governance/gap-register.json`.

## Risk Register

### Risk 1 - Context Pollution

Agents may receive stale, irrelevant, or conflicting memory.

Mitigation: current-state resolution, WeightProfiles, deprecation, conflict detection, and source references.

### Risk 2 - Over-Automation

Agents may perform risky changes without enough human oversight.

Mitigation: rule engine, escalation, capability profiles, and fail-closed policies.

### Risk 3 - Documentation Fatigue

Too many low-value drift findings may cause teams to ignore documentation signals.

Mitigation: severity thresholds, doc flags, waiver policy, and owner-based routing.

### Risk 4 - Model Cost Growth

LLM calls may become expensive if every event triggers model reasoning.

Mitigation: deterministic checks, hash diffing, prompt caching, local models, and tiered model routing.

### Risk 5 - Vendor Lock-In

The platform may become dependent on one IDE, model, or agent provider.

Mitigation: Universal Agent JSON, adapter contracts, capability profiles, and model routing abstraction.

### Risk 6 - Graph Inaccuracy

Dynamic languages or incomplete parsing may create wrong call relationships.

Mitigation: confidence scores, verification, exact/probable/ambiguous resolution states, and review Tasks. Structural isolation and hash-stable edge repair are documented in `docs/07-code-knowledge-graph/55-structural-isolation-and-architecture-overview-residuals.md`.

### Risk 7 - Port Conflicts in Development

Local development may fail when services use common default ports.

Mitigation: project-scoped non-default port profiles, startup preflight checks, and overrideable configuration.

### Risk 8 - Sensitive Data Leakage into Prompts

Logs, diffs, or artifacts may include secrets or customer data.

Mitigation: redaction pipeline, sensitivity labels, prompt safety checks, and restricted artifact references.

## Decisions

### Decision 1 - Primary Storage Split

**Closed (2026-07-23):** Storage ownership matrix published under
`docs/13-technology-stack-and-platform-decisions/13-storage-ownership-matrix.md`.
Closes GAP-001.

### Decision 2 - Model Routing Defaults

**Closed (2026-07-23):** LiteLLM gateway + published local/cloud profiles under
`backend/configs/model-routing/` (see `10-model-routing-profiles-with-litellm.md`). Closes GAP-003 / DEC-001.

### Decision 3 - WeightProfile Governance

**Closed (2026-07-23):** Owner/approval/rollback policy with CLI under
`docs/02-memory-and-context/12-weight-profile-governance.md`. Closes GAP-006.

### Decision 4 - Schema Registry Implementation

**Closed (2026-07-23):** Repository-directory catalog
(`12-schema-registry-architecture.md` + `backend/tools/schema-registry/catalog.json`).
Closes GAP-008.

### Decision 5 - SDK Scope And First Integration Targets

**Closed (2026-07-24):** Python + TypeScript SDK, generator, and adapter harness under
`docs/05-interoperability-ecosystem/11-sdk-release-and-adapter-harness.md`. Closes GAP-T06.

### Decision 6 - Development Port Base Policy

**Closed (2026-07-23 / 2026-07-24):** Port profile catalog + Phase 8 ownership checks +
`astloom ports check` / install preflight (GAP-007, GAP-T07). See
`docs/08-software-engineering-architecture/04-development-port-management.md` and
`backend/configs/port-profiles/astloom-dev.json`.

## Tracking Rule

Every new open decision should become a Decision record before implementation starts. Every risk should have an owner, mitigation, severity, and review date. Prefer updating this file when gap-register status changes rather than leaving stale "Open" headings.
