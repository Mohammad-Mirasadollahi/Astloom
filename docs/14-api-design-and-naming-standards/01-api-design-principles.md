---
doc_id: as.doc.api.api-design-principles
title: 01 - API Design Principles
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the principles that all Astloom APIs must follow. APIs are
  long-lived contracts between the admin console, SDKs, agents, adapters, services, and external
  tools. They must be stable, versioned, understandable, and testable.
tags:
- standard
- api
phase: 14-api-design-and-naming-standards
canonical_path: docs/14-api-design-and-naming-standards/01-api-design-principles.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 01 - API Design Principles

## Purpose

This document defines the principles that all Astloom APIs must follow. APIs are long-lived contracts between the admin console, SDKs, agents, adapters, services, and external tools. They must be stable, versioned, understandable, and testable.

## Core Principles

### Domain Language First

API names must use Astloom domain language, not database table names or framework internals. Use names such as `projects`, `agents`, `tasks`, `memory-items`, `common-context-items`, `rules`, `context-bundles`, `code-metadata`, and `reports`.

### Resource-Oriented By Default

External and admin APIs should be resource-oriented REST endpoints by default. Use nouns for resources and HTTP methods for standard operations.

### Use-Case Oriented Commands

When an operation is not a simple CRUD change, model it as a command subresource. Examples: approve a rule, resolve a context bundle, run a live test, start an agent run, or reindex a repository.

### Project Isolation First

Project-scoped APIs must include the project context explicitly in the path or validated request context. APIs must never infer cross-project access from user text or agent memory.

### Contract First

Every public API must have an OpenAPI contract, request/response schemas, examples, structured errors, and contract tests.

### Stable Public IDs

APIs must use stable public IDs. Do not expose database primary keys unless they are explicitly designed as public identifiers.

### Explicit Pagination

Every list endpoint must support pagination. Large collections must not return unbounded arrays.

### Idempotent Commands

Retryable commands must accept an idempotency key and must return the same logical result for repeated identical requests.

### Correlation Everywhere

Every request must propagate or create a correlation id. Every response should include correlation metadata or headers so UI, SDK, logs, traces, and audit records can be connected.

## API Families

Astloom APIs should be grouped into families:

- identity and access APIs.
- workspace, project, and project-group APIs.
- agent and agent-run APIs.
- task, issue, decision, and activity APIs.
- memory and context APIs.
- common context APIs.
- rule and policy APIs.
- code graph and code metadata APIs.
- docs sync APIs.
- connector and resource APIs.
- reporting and analytics APIs.
- admin and automation APIs.
- test evidence APIs.

## Compatibility Rule

Additive changes are preferred. Removing fields, changing meanings, changing idempotency behavior, renaming endpoints, or changing error codes requires a new version or migration plan.

## Acceptance Criteria

An API design is acceptable when the endpoint name is predictable, the resource owner is clear, the DTO names are stable, errors are structured, pagination is explicit, authorization scope is enforceable, and generated clients can use it without hand-written assumptions.
