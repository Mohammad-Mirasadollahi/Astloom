---
doc_id: as.doc.sea.error-handling-validation-and-result-standards
title: 31 - Error Handling, Validation, And Result Standards
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom should validate input, represent expected failures,
  handle unexpected failures, and expose safe diagnostics.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/31-error-handling-validation-and-result-standards.md
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

# 31 - Error Handling, Validation, And Result Standards

## Purpose

This document defines how Astloom should validate input, represent expected failures, handle unexpected failures, and expose safe diagnostics.

## Error Categories

Astloom should classify errors into:

- validation errors.
- authorization errors.
- conflict errors.
- not-found errors.
- rate-limit errors.
- dependency unavailable errors.
- retryable infrastructure errors.
- non-retryable infrastructure errors.
- policy rejection errors.
- unsafe-operation errors.
- unexpected system errors.

## Result Pattern

Expected business failures should return typed results or typed errors. They should not rely on generic exceptions for normal control flow.

Examples of expected failures:

- invalid project scope.
- task already completed.
- common context conflict.
- stale metadata.
- missing approval.
- contract version mismatch.

Unexpected failures may use exceptions, but they must be logged with correlation ids and safe diagnostic metadata.

## Validation Standard

Validation should happen at multiple layers:

- Transport validation checks request shape, authentication context, content type, and size limits.
- Contract validation checks schema compatibility and version.
- Application validation checks command preconditions and workflow rules.
- Domain validation enforces invariants.
- Configuration validation checks startup settings before the service becomes ready.

Validation errors must be structured, localized to the failing field or rule, and safe to return through APIs.

## Problem Details

Public API errors should use a consistent problem-details style response with:

- error_code
- message
- category
- correlation_id
- retryable
- field_errors when applicable
- safe_details

Secrets, tokens, credentials, private prompts, and raw provider payloads must never be returned in error responses.

## Logging Rule

Errors must include correlation id, tenant or project scope when safe, service name, operation name, retryability, and failure category. Sensitive values must be redacted.

## Recovery Rule

A handler must not catch an error unless it can add context, translate it to a typed failure, trigger a compensating action, or safely retry it.

## Acceptance Criteria

Error handling is acceptable when callers can understand whether a failure is retryable, operators can trace the failure, users do not see secrets, and tests can assert typed failure behavior without parsing free-form strings.
