# Time Primitives

Path: `backend/packages/shared-kernel/time`

## Purpose

Defines future clock, scheduler time, duration, timeout, and deterministic test-time primitives.

## Rules

Production code must not call wall-clock APIs directly inside domain or application logic. Inject a clock abstraction when behavior depends on time.
