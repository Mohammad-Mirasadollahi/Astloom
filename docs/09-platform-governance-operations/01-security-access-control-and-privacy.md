---
doc_id: as.doc.ops.security-access-control-and-privacy
title: Security, Access Control, and Privacy
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom handles code, documentation, logs, model prompts, tool outputs, decisions,
  approvals, and potentially sensitive business data. Security and privacy must be designed
  into the platform from the beginning.
tags:
- standard
- ops
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/01-security-access-control-and-privacy.md
lifecycle_lane: current
concern_lane: security
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Security, Access Control, and Privacy

## Purpose

Astloom handles code, documentation, logs, model prompts, tool outputs, decisions, approvals, and potentially sensitive business data. Security and privacy must be designed into the platform from the beginning.

## Identity Model

The platform should support identities for:

- human users,
- autonomous agents,
- IDE plugins,
- external tools,
- CI jobs,
- background workers,
- service accounts.

Every identity must have a stable ID, owner, tenant scope, project scope, capability profile, trust level, and audit trail.

## Authorization Model

Authorization should be policy-based and context-aware. Access decisions should consider:

- tenant,
- project,
- role,
- task assignment,
- data sensitivity,
- agent trust level,
- requested action,
- environment,
- approval state.

## Tenant and Project Boundaries

Tenant boundaries must be enforced before retrieval, prompt building, broker delivery, graph query, artifact access, or context injection. A message, memory item, or graph node from one tenant must not become visible to another tenant unless explicitly exported through a governed process.

## Data Sensitivity Levels

Recommended sensitivity labels:

- `PUBLIC`: safe for broad visibility.
- `INTERNAL`: visible inside the tenant.
- `PROJECT_RESTRICTED`: limited to project members and assigned agents.
- `CONFIDENTIAL`: requires explicit role or approval.
- `SECRET`: never included in prompts or general dashboards.
- `CUSTOMER_DATA`: governed by privacy and retention rules.

## Prompt Safety

Before any memory, log, code, or artifact is inserted into a prompt, the platform must run redaction and access checks.

Prompt safety rules:

- secrets are never prompt-visible,
- restricted data requires explicit authorization,
- customer data is minimized or anonymized,
- evidence references can replace raw content,
- model outputs must not be treated as verified truth without evidence.

## Agent Capability Controls

Each agent should have a capability profile. Examples:

- can read code,
- can write code,
- can run tests,
- can create tasks,
- can open pull requests,
- can modify infrastructure,
- can access restricted logs,
- can request human approval,
- can publish broker events.

Risky capabilities should require higher trust level and human ownership.

## Secrets Management

Secrets must not be stored in Markdown docs, repository files, prompts, WorkLogs, or broker payloads. Secrets should come from an environment-specific secret manager or injected runtime configuration.

## Audit Requirements

Security-relevant actions must include actor, timestamp, action, affected entity, evidence reference, policy result, approval state, and correlation ID.

## Acceptance Criteria

- Every action has an authenticated identity.
- Every prompt context item passes authorization and redaction.
- Tenant boundaries are enforced before retrieval and delivery.
- Agent capabilities are explicit and auditable.
- Secrets are never stored in prompt-visible records.
