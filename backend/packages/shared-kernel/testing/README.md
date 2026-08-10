# Testing Primitives

Path: `backend/packages/shared-kernel/testing`

## Purpose

Defines future test builders, fake clocks, in-memory adapters, deterministic ids, contract test helpers, and module boundary verification primitives.

## Rules

Testing helpers must support public contracts and ports. They must not require access to private service internals.
