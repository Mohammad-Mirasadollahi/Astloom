# Result And Error Primitives

Path: `backend/packages/shared-kernel/results`

## Purpose

Defines future Result, Option, typed error, problem detail, and failure classification primitives used across services.

## Rules

Expected business failures should be represented as typed results. Unexpected failures should preserve stack traces, correlation ids, and safe diagnostic metadata.
