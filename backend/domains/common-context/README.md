# Common Context Domain

Path: `backend/domains/common-context`

## Purpose

The Common Context domain defines reusable project knowledge that should not be repeated in every prompt, task, ticket, agent instruction, or workflow. It centralizes shared rules, definitions, constraints, glossary terms, workflow reminders, and stable project conventions.

Common Context is not hidden global memory. Every item must be scoped, versioned, auditable, explainable, and configurable. The default scope is one project. Sharing across projects is allowed only through explicit project-group composition.

## Responsibilities

This domain owns the language and policies for:

- reusable engineering rules and product definitions.
- repeated instruction promotion into governed common items.
- applicability metadata that decides when an item is relevant.
- score inputs such as frequency, recency, confidence, user pinning, task similarity, and effectiveness.
- conflict behavior between task instructions, project overrides, memory, rules, and common items.
- lifecycle states such as proposed, approved, active, suppressed, deprecated, and archived.

## Boundary

Common Context stores reusable guidance. It does not execute tasks, own long-term memory internals, run policies, or own project isolation. Other services consume it through public contracts and resolved bundles.

## Folder Map

- `model/` domain entities and value objects.
- `policies/` promotion, injection, override, isolation, and retirement policies.
- `events/` common context lifecycle events.
- `use-cases/` authoring, approving, resolving, suppressing, and retiring workflows.
- `examples/` realistic reusable context examples.

## Dependency Rules

This domain may reference `packages/contracts` and stable primitives from `packages/shared-kernel`. It must not depend on service internals, infrastructure adapters, UI code, or provider-specific integrations.

## Status

Scaffolded for documentation and future implementation. No runtime code is implemented yet.
