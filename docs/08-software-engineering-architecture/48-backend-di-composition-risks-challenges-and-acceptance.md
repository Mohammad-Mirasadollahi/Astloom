---
doc_id: as.doc.sea.backend-di-composition-risks
title: 48 - Backend DI Composition Risks Challenges And Acceptance
doc_type: standard
status: draft
schema_version: '1.0'
owner: platform-architecture
summary: Risks, challenges, and acceptance gates for Astloom composition-root DI (Phases
  A–D acceptance checked).
tags:
- dependency-injection
- composition-root
- risks
- acceptance
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/48-backend-di-composition-risks-challenges-and-acceptance.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.sea.backend-di-composition-feature-spec
- as.doc.sea.backend-di-composition-hld
- as.doc.sea.backend-di-composition-lld
- docs/08-software-engineering-architecture/30-dependency-injection-and-composition-root.md
doc_version: 1.0.1
audience:
- engineer
- architect
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 48 - Backend DI Composition Risks Challenges And Acceptance

## Implementation status

**Phases A–D acceptance checked** via gate
`tests/backend/gates/di-composition-verification/` (including thin ports / store
allowlist and CLI process containers).

## Purpose

Make failure modes and done-criteria explicit for the DI composition migration
so implementation PRs stay scoped and verifiable.

## Risks

| ID | Risk | Severity | Mitigation |
| --- | --- | --- | --- |
| R-01 | Big-bang rewrite breaks MCP/ingest | High | Phase A pathfinders only; keep `build_service` wrapper |
| R-02 | Hidden second composition root | Medium | Single `build_app` / server entry; gate for module-level singletons |
| R-03 | Import cycles after splitting ports | Medium | Ports in domain; adapters outward; no re-export loops |
| R-04 | Over-building a DI framework | High | No third-party IoC; frozen dataclass container only |
| R-05 | FastAPI `Depends` becomes service locator | Medium | Depends may only read `app.state.container` |
| R-06 | Tests still hit real Neo4j/Postgres | Medium | Unit path uses fakes; live remains marked |
| R-07 | Thin services copy-paste diverge | Low | Checklist in LLD Phase B; optional shared test helper later |

## Challenges

1. **code-graph bootstrap is already rich** — refactor carefully around LLM/embeddings locking.
2. **MCP builds multiple stores** — container is a bundle, not one service.
3. **CLI embeds services** — pool lifetime across subcommands needs Phase D discipline.
4. **Honest docs** — keep `lifecycle_lane: future` until gates pass; then flip packs to `current`.

## Acceptance — Phase A (pathfinders)

- [x] `code-graph-service` exposes `build_container` returning a frozen container with the graph service.
- [x] `create_app` / API factory attaches container to `app.state` and does not call `build_service()` inside route handlers.
- [x] `build_service()` remains a thin compatibility wrapper or is deleted after call-site update.
- [x] MCP gateway backends receive stores/services from the composition root only.
- [x] Gate package `tests/backend/gates/di-composition-verification/` exists and passes.
- [x] Existing unit tests for code-graph and MCP stay green.
- [x] Docs `45`–`48` Implementation status updated for Phase A; Phases B–D remain open.

## Acceptance — Phase B (thin services)

- [x] Each listed thin service has `build_container` + `build_app(container)` (or documented CLI-only exception).
- [x] No thin-service route module calls `build_service()` per request.
- [x] Import gate covers those services’ equivalent layout (`core.py` / `api.py` / `ports.py`).

## Acceptance — Phase C–D

- [x] No application module imports concrete Store/Neo4j/LiteLLM client modules (gate enforced).
- [x] CLI long-lived paths reuse one container per process where pools exist.
- [x] Doc `30` linked examples match the shipped pattern.

## Definition of done (program)

Astloom backend structure is “on DI” when Phases A–C acceptance are checked, doc `30` principles hold in code, and agents/engineers wire new dependencies only at the composition root.

## Related Documents

- `45-backend-di-composition-feature-specification.md`
- `46-backend-di-composition-high-level-design.md`
- `47-backend-di-composition-low-level-design.md`
- `30-dependency-injection-and-composition-root.md`
