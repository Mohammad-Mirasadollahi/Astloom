# Common Context Service

Path: `backend/services/common-context-service`

## Purpose

The Common Context Service manages reusable context items that prevent users and agents from repeating the same project rules, constraints, definitions, and workflow instructions in every task.

The service turns stable repeated guidance into governed, scoped, explainable common items. It should help Astloom behave consistently without hard-coding project rules into prompts, source code, scripts, or agent-specific wrappers.

## Responsibilities

This service owns:

- common item creation, update, approval, rejection, suppression, deprecation, and archive workflows.
- automatic proposal of common items from repeated user instructions, repeated corrections, repeated tickets, and repeated agent failures.
- scoring using configurable weights: frequency, recency, confidence, user pinning, task similarity, project relevance, and effectiveness.
- context bundle resolution for project, project group, workflow type, task type, agent type, user, and token budget.
- conflict detection between common context, memory, rules, domain packs, feature profiles, project isolation policies, and task-specific instructions.
- audit records explaining why each item was selected, suppressed, overridden, or rejected.
- reporting signals for repetition reduction and token savings.

## Non-Responsibilities

This service does not execute agent tasks, own memory storage internals, execute rule policies, or own project isolation. It integrates with those services through contracts.

## Internal Layout

- `src/` future implementation code.
- `tests/` unit, integration, and contract tests.
- `docs/` service-specific design and operational notes.
- `migrations/` future storage migrations.
- `config/` score weights, thresholds, and resolution policy settings.

## Dependency Rules

The service may depend on `packages/contracts`, `packages/common-context`, `packages/shared-kernel`, and platform adapters through ports. It must not import private internals of memory-service, rule-engine-service, orchestration-service, or project-profile-service.

## Status

Vertical slice implemented. Canonical tests live under `tests/backend/services/common-context-service/`.

```bash
PYTHONPATH=backend/services/common-context-service/src .venv/bin/python -m pytest tests/backend/services/common-context-service -q
```
