---
doc_id: as.doc.sea.security-and-threat-modeling-engineering
title: 16 - Security And Threat Modeling Engineering
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how security should be engineered into Astloom. The platform
  handles code context, work evidence, agent actions, memory, external integrations, approvals,
  and audit data. Security must be part of design and implementation, not a final checklist.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/16-security-and-threat-modeling-engineering.md
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

# 16 - Security And Threat Modeling Engineering

## Purpose

This document defines how security should be engineered into Astloom. The platform handles code context, work evidence, agent actions, memory, external integrations, approvals, and audit data. Security must be part of design and implementation, not a final checklist.

## Security Principles

Astloom should follow these principles:

- least privilege.
- explicit trust boundaries.
- tenant and workspace isolation.
- defense in depth.
- secure defaults.
- no hard-coded secrets.
- auditable privileged actions.
- redaction before persistence or prompt injection.
- approval gates for high-risk actions.
- secure failure behavior.

## Trust Boundaries

Important trust boundaries include:

- user to api-gateway.
- agent to api-gateway.
- IDE extension to platform.
- adapter-service to external providers.
- services to databases.
- services to broker.
- workers to external tools.
- memory-service to prompt context consumers.
- admin-console to sensitive audit data.

Each boundary should define authentication, authorization, input validation, logging, and failure behavior.

## Threat Modeling Workflow

Threat modeling should happen for high-risk features.

Steps:

1. identify assets.
2. identify actors.
3. identify trust boundaries.
4. list entrypoints.
5. list abuse cases.
6. define mitigations.
7. add tests.
8. document residual risk.
9. create gap entries for unresolved risk.

## Sensitive Assets

Sensitive assets include:

- source code.
- repository metadata.
- secrets and credentials.
- prompt context.
- memory records.
- audit evidence.
- approval decisions.
- external provider payloads.
- tenant identifiers.
- user identities.
- security policies.
- model outputs used for decisions.

## Authentication And Authorization

Authentication verifies identity. Authorization verifies permission.

Engineering requirements:

- every public API must require authentication unless explicitly documented otherwise.
- service-to-service calls should use trusted service identity.
- authorization must be checked before data retrieval.
- prompt context retrieval must apply authorization before ranking output.
- admin-console views must be permission-scoped.
- adapter callbacks should verify source authenticity where provider supports it.

## Tenant And Workspace Isolation

Tenant and workspace isolation should be enforced at every access path.

Rules:

- queries must include workspace or tenant scope.
- events must include workspace scope.
- memory retrieval must not mix workspace data.
- graph queries must respect repository and workspace permissions.
- audit exports must be scoped.
- tests must include cross-tenant negative cases.

## Secret Handling

Secrets must not be stored in source-controlled config, logs, events, prompts, audit text, or documentation examples.

Secret handling should include:

- secret references instead of literal values.
- redaction filters for logs and events.
- detection of secret-like values in CI.
- clear separation of local fake secrets and real provider credentials.
- rotation procedure for production secrets.

## Prompt And Memory Security

Astloom uses memory and context injection, which creates special risk.

Rules:

- authorization must happen before context assembly.
- sensitive fields must be redacted before prompt construction.
- memory items should carry source and trust metadata.
- low-confidence or untrusted memories should be marked clearly.
- prompt context should include only what the task needs.
- prompt snapshots should follow retention and redaction policy.

## External Integration Security

Adapters should protect external boundaries.

Adapter security requirements:

- validate callback signatures where available.
- validate payload schemas.
- use least-privilege provider tokens.
- normalize provider errors without leaking secrets.
- store external reference IDs for audit.
- define rate limit behavior.
- define disabled mode.

## Approval Security

High-risk actions should require approval.

Examples:

- production configuration change.
- authentication or authorization logic change.
- data deletion or retention change.
- security rule disablement.
- external provider permission expansion.
- high-impact code change detected by graph analysis.

Approval records should include presented evidence, approver identity, time, decision, and reason.

## Security Testing

Security tests should include:

- unauthenticated request rejection.
- unauthorized workspace access rejection.
- cross-tenant memory retrieval rejection.
- secret redaction checks.
- adapter callback signature failure.
- approval bypass attempts.
- prompt injection handling for external content.
- audit tampering detection where applicable.

## Acceptance Criteria

Security engineering is acceptable when:

- trust boundaries are documented.
- authorization happens before data retrieval and context assembly.
- secrets are not hard-coded or logged.
- tenant isolation is tested with negative cases.
- high-risk actions have approval and audit behavior.
- unresolved security risks are recorded in gap analysis.

## Project Isolation Security Requirements

Project isolation is a security boundary, not only a product filter.

Threats:

- cross-project memory leakage through semantic retrieval.
- graph traversal leaking unrelated project symbols.
- report aggregation exposing another project metrics or tasks.
- connector token scoped too broadly.
- agent prompt context accidentally including another project evidence.
- ProjectGroup policy granting more data types than intended.
- stale composition policy continuing to allow access.

Security requirements:

- project scope must be authorized before data retrieval.
- scope filtering must happen before ranking, summarization, prompt assembly, or report aggregation.
- ProjectGroup composition must require explicit policy and approval.
- cross-project access must create audit evidence.
- connector credentials must be project-scoped unless group-scoped by policy.
- agent tokens must include allowed project or ProjectGroup claims.
- high semantic similarity must never bypass scope boundaries.
- expired or missing composition policy must deny access by default.

Additional security tests:

- project A memory cannot be retrieved in project B context.
- project A graph nodes cannot be traversed from project B without ProjectGroup policy.
- project A report data cannot appear in project B report.
- project A connector cannot create project B tickets.
- project A agent token cannot create project B Tasks.
- ProjectGroup policy allows only configured data types and directions.
- cross-project access produces audit record with policy reference.
