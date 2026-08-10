---
doc_id: as.doc.ckg.prod-retrieval-live-test-gates
title: 33 - Production Retrieval Live Test Gates
doc_type: runbook
status: active
schema_version: '1.0'
owner: code-graph-lead
summary: 'Normative live/fuzzer/challenge test gates for the production retrieval stack: suite
  inventory, Compose env contract, pythonpath rules, AuthError skip policy, AuthenticationRateLimit
  handling, and acceptance criteria (anti-cascade design).'
tags:
- testing
- live
- retrieval
- neo4j
- postgres
- runbook
- acceptance
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/33-production-retrieval-live-test-gates.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- operators
- agents
authority: normative
visibility: internal
linked_symbols:
- tests/backend/services/code-graph-service/test_production_retrieval_challenge_live.py::check_password
- tests/backend/services/code-graph-service/test_production_retrieval_fuzzer.py::test_fuzz_tokenize_never_raises
- tests/backend/services/code-graph-service/test_production_retrieval_live.py::check_password
related_docs:
- as.doc.ckg.prod-retrieval-feature-spec
- as.doc.ckg.prod-retrieval-risks
- as.doc.ckg.intentional-fallbacks-and-plugin-licensing
- docs/07-code-knowledge-graph/12-neo4j-runtime-plugins.md
doc_version: 1.0.1
audience:
- engineer
- operator
- agent
primary_entities:
- LiveTestGate
- ChallengeSuite
- FuzzerSuite
- AuthSkipPolicy
relations_declared:
- type: depends_on
  target: as.doc.ckg.prod-retrieval-feature-spec
- type: complements
  target: as.doc.ckg.prod-retrieval-risks
- type: complements
  target: as.doc.ckg.intentional-fallbacks-and-plugin-licensing
chunk_hints:
  strategy: heading_h2
  max_tokens: 700
  overlap_tokens: 48
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 33 - Production Retrieval Live Test Gates

## Purpose

Define how engineers and agents run **live** verification of the production
retrieval stack against Compose Neo4j + Postgres, without mistaking fixture
setup failures for product regressions, and without depending on ad-hoc
`PYTHONPATH` exports.

This document is normative for the suites under
`tests/backend/services/code-graph-service/`.

## Design principles (non-negotiable)

| Principle | Rule |
| --- | --- |
| Soft dependency | Unreachable ports → `pytest.skip`, never hard fail CI that lacks Compose |
| Single clear skip | Auth / Unauthorized / AuthenticationRateLimit → **one** skip reason, not N setup ERRORs |
| Importable by default | `code_graph_service` must import via pytest `pythonpath` / package conftest |
| Non-default ports | Live gates use Astloom mapped ports (default `32287` / `32232`), never bare `7687` / `5432` |
| Secret from Compose | Password must match the running Compose `NEO4J_AUTH` / Postgres secret |
| Artifacts are evidence | JUnit + JSON summaries under `tests/artifacts/code-graph-live/` |

## Problem this prevents

A **module-scoped** Neo4j fixture that raises `AuthError` (wrong
`ASTLOOM_NEO4J_PASSWORD`, or Neo4j `AuthenticationRateLimit` after repeated
bad logins) is re-reported by pytest for every dependent test. In a 50-case
challenge suite that looks like “~50 failed” in Test Explorer, even though the
product code under test was never exercised.

Missing `PYTHONPATH` produces `ModuleNotFoundError: code_graph_service` at
collection time — the same “everything red” appearance.

## Suite inventory

| Suite | Path | Count | Role |
| --- | --- | ---: | --- |
| Live (simple + challenge samples) | `test_production_retrieval_live.py` | 9 | Smoke + representative hard cases |
| Fuzzer (unit + live) | `test_production_retrieval_fuzzer.py` | 50 | Adversarial unit + live noise |
| Challenge live | `test_production_retrieval_challenge_live.py` | 50 | Live-only adversarial gate |

READMEs beside each module document re-run commands. Shared helpers:

| File | Responsibility |
| --- | --- |
| `conftest.py` | Inserts service `src/` (+ test dir) on `sys.path` for Test Explorer |
| `live_helpers.py` | `require_tcp`, `skip_on_live_connect_error` |
| `pyproject.toml` `[tool.pytest.ini_options].pythonpath` | Repo-wide import path for `code_graph_service` |

## Environment contract

| Variable | Default (local) | Notes |
| --- | --- | --- |
| `ASTLOOM_NEO4J_BOLT_PORT` | `32287` | Must not be `7687` |
| `ASTLOOM_POSTGRES_PORT` | `32232` | Must not be `5432` |
| `ASTLOOM_NEO4J_USER` | `neo4j` | |
| `ASTLOOM_NEO4J_PASSWORD` | `astloom-local-dev-secret` | **Must match Compose** |
| `ASTLOOM_POSTGRES_PASSWORD` | `astloom-local-dev-secret` | **Must match Compose** |
| `ASTLOOM_NEO4J_GDS_ENABLED` | `true` | See doc `32` |
| `ASTLOOM_NEO4J_GDS_CONCURRENCY` | `4` | Hard-clamped 1–4 |

Prerequisite:

```bash
backend/deployments/compose/wait-healthy.sh --timeout 90 astloom-neo4j-1 astloom-postgres-1
```

Do **not** chain unbounded `sleep` health loops with pytest (see
`.cursor/rules/compose-wait-timeouts.mdc`).

## Auth / connect skip policy

`live_helpers.skip_on_live_connect_error` converts these into `pytest.skip`
with an actionable message:

- `neo4j.exceptions.AuthError`
- message containing `Unauthorized`
- message containing `AuthenticationRateLimit`
- message containing `authentication failure`
- Postgres `OperationalError` / password authentication failed
- `ServiceUnavailable`

Any other exception **propagates** (real product bugs stay red).

### Rate-limit note

Repeated wrong-password attempts trigger Neo4j
`Neo.ClientError.Security.AuthenticationRateLimit`. Even the correct password
fails until the window clears. Operators should wait and retry once; suites
must skip (not ERROR-cascade) while rate-limited.

## How to run

```bash
export ASTLOOM_NEO4J_PASSWORD=astloom-local-dev-secret
export ASTLOOM_POSTGRES_PASSWORD=astloom-local-dev-secret

## Prefer .venv pytest; pythonpath is configured in pyproject.toml
.venv/bin/python -m pytest \
  tests/backend/services/code-graph-service/test_production_retrieval_challenge_live.py -v

.venv/bin/python -m pytest \
  tests/backend/services/code-graph-service/test_production_retrieval_fuzzer.py -v

.venv/bin/python -m pytest \
  tests/backend/services/code-graph-service/test_production_retrieval_live.py -v
```

Optional explicit path (still valid):

```bash
PYTHONPATH=backend/services/code-graph-service/src \
  .venv/bin/python -m pytest tests/backend/services/code-graph-service -q
```

## Expected outcomes

| Condition | Expected result |
| --- | --- |
| Compose healthy + correct secrets | All collected live cases **passed** |
| Wrong password / rate-limit / auth failure | Dependent live cases **skipped** with AuthSkip message |
| Ports closed | **skipped** (TCP probe) |
| Missing import path (pre-fix) | Collection ERROR — **must not recur** after `pythonpath` / conftest |

## Artifacts

| Path | Content |
| --- | --- |
| `tests/artifacts/code-graph-live/*-last-run.txt` | Full pytest console |
| `tests/artifacts/code-graph-live/*-junit.xml` | Machine summary |
| `tests/artifacts/code-graph-live/*-summary.json` | Operator JSON |
| `tests/artifacts/code-graph-live/ROOTCAUSE_50_errors.md` | Incident note (points here) |

## Acceptance gates

- [x] `pyproject.toml` declares `pythonpath` for `backend/services/code-graph-service/src`.
- [x] Directory `conftest.py` keeps Test Explorer imports working without shell exports.
- [x] Live fixtures wrap Neo4j/Postgres connect with `skip_on_live_connect_error`.
- [x] Wrong password yields **skips**, not dozens of setup ERRORs.
- [x] Correct Compose secrets yield green challenge (50) / fuzzer (50) / live (9) when deps healthy.
- [x] Suites refuse default Neo4j/Postgres host ports (`7687` / `5432`).
- [x] This doc linked from `00-index.md` and risks doc `31`.
- [x] Offline honesty eval (nDCG / co-change) is a separate unit gate — see `31` and `tests/.../ckg_eval/` (not skip-as-pass live).

## Non-goals

- Replacing unit tests with live-only coverage.
- Committing real production secrets into the repo.
- Requiring GDS Enterprise for any gate (see doc `32`).
