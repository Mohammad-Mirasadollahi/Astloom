---
doc_id: as.doc.sea.test-authoring-standard-continued
title: 37 - Test Authoring Standard (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/08-software-engineering-architecture/37-test-authoring-standard.md`
  — remaining sections after the soft size budget.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/37-test-authoring-standard-continued.md
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

# 37 - Test Authoring Standard (Continued)

## Purpose

Continuation of `docs/08-software-engineering-architecture/37-test-authoring-standard.md` — remaining sections after the soft size budget.

## Markers And Selection

Recommended pytest markers (declare in `pyproject.toml` / pytest config as suites mature):

| Marker | Meaning |
| --- | --- |
| `unit` | Deterministic, no external I/O |
| `contract` | Schema/API/event contract |
| `integration` | Controlled real adapters |
| `e2e` | Full journey |
| `live` | Real or production-like; never in default PR fast path unless explicitly selected |
| `fuzz` | Property-based / fuzz |
| `security` | AuthZ / isolation / redaction |
| `performance` | Budget checks |
| `regression` | Pins a past failure |
| `slow` | Optional hint for long tests |

Default developer and PR fast path:

```bash
.venv/bin/python -m pytest -m "unit or contract" -q
```

Integration and fuzz run on affected owners. Live runs on release / post-deploy / explicit request.

## CI And Release Gates

Minimum gate order (aligns with `11-…` and `12-…`):

1. Format / static analysis / dependency boundaries
2. Docs validation (when docs change)
3. Unit + Contract
4. Integration for affected owners
5. Security checks for sensitive areas
6. Fuzz for parser/schema/numeric owners when touched
7. E2E for critical journey changes
8. Live for release readiness, connectors, migrations, production-like validation

Coding agents verifying a local change must run the **smallest** command covering the families they added, not only a vague “tests passed” claim.

## Definition Of Done (Implementation Changes)

A behavior change is done only when all apply:

- [ ] Required test families from the decision matrix exist in the same change
- [ ] Tests live under `tests/` with correct owner path
- [ ] Unit tests are deterministic and free of real I/O
- [ ] Contract tests updated if public schemas changed
- [ ] Integration/E2E/Live/Fuzz added when the matrix requires them
- [ ] Named pytest (or frontend runner) command was executed and passed
- [ ] No secrets in fixtures or evidence
- [ ] Docs/indexes updated when contracts or operator workflows changed
- [ ] Any gap is an explicit approved `tsoc-defer` or a Gap record — not silence

Reviewers **must reject** changes that add production behavior without the concurrent tests required above.

## Anti-Patterns

| Anti-pattern | Replace with |
| --- | --- |
| Code merged, “tests later” | Concurrent tests or approved deferral |
| Unit test that hits real Postgres/Neo4j/LLM | Fake port or move to Integration/Live |
| Mocking private internals | Public port fake + Integration for persistence |
| One mega Live test as only coverage | Unit + Contract + targeted Live |
| Asserting only “mock called” | Assert domain/API outcome |
| Sleeping in a loop until green | Harness wait with timeout + diagnostics |
| Copying customer logs into fixtures | Synthetic sanitized fixtures |
| Fuzz without invariants | Explicit properties + shrinking |
| Snapshot update without review | Treat as contract change |
| Service-local runnable `tests/` folders | Root `tests/backend/...` placement |

## Related Documents

- `11-testing-and-verification-engineering.md` — verification layers and CI philosophy
- `25-live-and-unit-test-strategy.md` — Unit vs Live, safety, evidence
- `33-testing-seams-and-contract-boundary-standards.md` — seams and doubles design
- `38-fuzzing-and-property-based-testing.md` — fuzz and property-based depth
- `06-engineering-operating-model.md` — Definition of Ready / Done
- `12-ci-cd-and-release-engineering.md` — pipeline stages
- `29-engineering-best-practices-and-implementation-standards.md` — implementation guardrails
- `../06-technical-logic/07-technical-test-strategy.md` — domain scenario suites
- `../../tests/README.md` — executable layout and commands
- Cursor rule: `ai-toolstack/rules/test-with-implementation.mdc` (wired to `.cursor/rules/`)
- engineers and coding agents can select the correct test family from the decision matrix without ambiguity
- concurrent code-and-tests is enforced as Definition of Done
- Unit, Contract, Integration, E2E, Live, Fuzz, Security, Performance, and Regression authoring rules are explicit
- doubles preference (fake over brittle mock) is clear
- placement under `tests/` is unambiguous
- Live and Fuzz are covered without duplicating the strategy docs they complement
- reviewers have a rejectable checklist for missing tests
- Parent document: `docs/08-software-engineering-architecture/37-test-authoring-standard.md`
