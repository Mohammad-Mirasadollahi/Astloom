---
doc_id: as.doc.sea.modular-project-structure-continued-continued
title: 05 - Modular Project Structure (Continued) (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/08-software-engineering-architecture/05-modular-project-structure-continued.md`
  — remaining sections after the soft size budget.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/05-modular-project-structure-continued-continued.md
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

# 05 - Modular Project Structure (Continued) (Continued)

## Purpose

Continuation of `docs/08-software-engineering-architecture/05-modular-project-structure-continued.md` — remaining sections after the soft size budget.

## Common Context Reuse Structure

Astloom must include a first-class Common Context area so stable project rules and definitions do not need to be repeated in every user request, agent run, ticket, or workflow.

Required folders:

    backend/domains/common-context/
      model/
      policies/
      events/
      use-cases/
      examples/
    backend/services/common-context-service/
      src/
      tests/
      docs/
      migrations/
      config/
    backend/packages/common-context/
      contracts/
      resolvers/
      templates/
      examples/
    backend/configs/common-context-profiles/

The common-context domain defines vocabulary and policy. The common-context-service owns lifecycle and resolution. The common-context package exposes reusable contracts and deterministic resolver primitives. The common-context-profiles directory keeps score weights, token budgets, approval thresholds, and feature toggles out of code.

Common context must be project-scoped by default. Cross-project reuse is allowed only through explicit project-group composition and audit records.


## Engineering Standards Structure

Backend implementation must follow `/root/Astloom/backend/docs/ENGINEERING_STANDARDS.md` and the Software Engineering Architecture standards in files 29 through 33.

Shared cross-cutting primitives should live under:

    backend/packages/shared-kernel/dependency-injection/
    backend/packages/shared-kernel/validation/
    backend/packages/shared-kernel/results/
    backend/packages/shared-kernel/time/
    backend/packages/shared-kernel/resilience/
    backend/packages/shared-kernel/testing/

These folders are for stable primitives only. They must not become a dumping ground for business logic.

## Related Documents

- Parent document: `docs/08-software-engineering-architecture/05-modular-project-structure.md`
- Parent document: `docs/08-software-engineering-architecture/05-modular-project-structure-continued.md`
