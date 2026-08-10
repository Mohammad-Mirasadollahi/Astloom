# Common Context Package

Path: `backend/packages/common-context`

## Purpose

Provides stable shared contracts and primitives for resolving reusable common context across apps, services, SDKs, tests, and integrations.

This package prevents each service from duplicating its own version of common item schemas, score breakdowns, conflict objects, and bundle resolution interfaces.

## Contents

- `contracts/` public schemas and DTOs.
- `resolvers/` deterministic resolver interfaces and future reusable selection primitives.
- `templates/` reusable item templates for rules, definitions, conventions, and workflow reminders.
- `examples/` sample payloads and bundle-resolution scenarios.

## Dependency Rules

This package may depend on `packages/contracts` and `packages/shared-kernel`. It must not depend on deployable services, platform adapters, database clients, message brokers, or UI code.

## Status

Active. Shared scoring (`score_item`) and budget selection (`select_within_budget`) are used by
`common-context-service` for propose scoring and bundle resolve.

Normative wiring + unused-candidate classification:
`docs/07-code-knowledge-graph/79-shared-package-wiring-and-unwired-findings.md`.
