---
doc_id: as.doc.sea.project-isolation-and-composition-architecture-continued
title: 23 - Project Isolation And Composition Architecture (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/08-software-engineering-architecture/23-project-isolation-and-composition-architecture.md`
  — remaining sections after the soft size budget.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/23-project-isolation-and-composition-architecture-continued.md
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

# 23 - Project Isolation And Composition Architecture (Continued)

## Purpose

Continuation of `docs/08-software-engineering-architecture/23-project-isolation-and-composition-architecture.md` — remaining sections after the soft size budget.

## Required Tests

Testing must include negative cases.

Required tests:

- project A memory is not retrieved for project B query.
- project A code graph nodes are not traversed from project B without policy.
- project A report data is not aggregated into project B report.
- agent token scoped to project A cannot create project B Task.
- ProjectGroup allows only configured data types.
- expired composition policy denies access.
- cross-project access creates audit record.
- high semantic similarity does not bypass scope.
- prompt context assembly excludes unauthorized projects before ranking.

## Failure Handling

Failure cases:

- scope missing: block query and request scope selection.
- ambiguous project: ask user or infer only when evidence is safe.
- composition policy missing: deny cross-project access.
- policy expired: deny and create operator warning.
- partial group visibility: show partial result caveat.
- unauthorized connector: disable cross-project capability.
- report aggregation denied: show permission and policy reason.

## Acceptance Criteria

Project isolation and composition are acceptable when:

- every stored record has tenant, workspace, and project or group scope.
- project data is isolated by default across memory, question memory, FAQ, graph, docs, tickets, agents, reports, connectors, automation jobs, configuration, and audit.
- scope filtering happens before retrieval, ranking, graph traversal, prompt assembly, and report aggregation.
- unrelated projects never share data through semantic similarity, global memory, report aggregation, or connector tokens.
- ProjectGroup composition requires explicit policy, authorization, allowed data types, allowed directions, and audit behavior.
- frontend/backend or related-project composition can share approved contracts, graph edges, reports, and Tasks without exposing private project memory.
- every cross-project access creates audit evidence.
- UI always shows active project or ProjectGroup scope.
- negative isolation tests exist for memory, graph, docs, reports, tasks, agents, connectors, and prompt context.


## Related Documents

- Parent document: `docs/08-software-engineering-architecture/23-project-isolation-and-composition-architecture.md`
