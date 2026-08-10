# Validation Primitives

Path: `backend/packages/shared-kernel/validation`

## Purpose

Defines future shared validation primitives for input validation, config validation, command validation, contract validation, and invariant reporting.

## Rules

Validation must produce structured errors, must not hide business policy inside transport adapters, and must be deterministic in tests.
