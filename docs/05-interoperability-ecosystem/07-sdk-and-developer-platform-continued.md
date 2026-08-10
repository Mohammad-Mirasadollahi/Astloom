---
doc_id: as.doc.interop.sdk-and-developer-platform-continued
title: 07 - SDK And Developer Platform (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/05-interoperability-ecosystem/07-sdk-and-developer-platform.md`
  — remaining sections after the soft size budget.
tags:
- standard
- interop
phase: 05-interoperability-ecosystem
canonical_path: docs/05-interoperability-ecosystem/07-sdk-and-developer-platform-continued.md
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

# 07 - SDK And Developer Platform (Continued)

## Purpose

Continuation of `docs/05-interoperability-ecosystem/07-sdk-and-developer-platform.md` — remaining sections after the soft size budget.

## Documentation Requirements

SDK documentation should include:

- installation.
- authentication.
- configuration.
- project scoping.
- command examples.
- query examples.
- event subscription examples.
- agent run examples.
- adapter implementation examples.
- admin workflows.
- test fixtures.
- error handling.
- migration guides.
- version compatibility matrix.

Examples must use public SDK methods only. They must not import service internals.

## Acceptance Criteria

The SDK platform is acceptable when:

- developers can integrate agents, adapters, admin tools, and tests without importing service internals.
- every SDK call carries explicit or derived organization, workspace, project, actor, and correlation context.
- SDKs expose typed errors, idempotency support, retry behavior, and audit-safe logging.
- SDK behavior is generated or validated from public contracts.
- TypeScript and Python SDKs have contract tests, examples, and test fakes.
- adapter developers can register capabilities and validate payload mappings through the SDK.
- agents can report work, request context, submit evidence, and finish runs through the SDK.
- admin tooling can manage domain packs, feature profiles, rule suggestions, and audits through privileged SDK methods.
- SDK documentation is sufficient for a developer to build a first integration without reading service internals.


## Related Documents

- Parent document: `docs/05-interoperability-ecosystem/07-sdk-and-developer-platform.md`
