---
doc_id: as.doc.ckg.core-product-readiness-phased-backlog
title: 34 - Core Product Readiness Phased Backlog
doc_type: gap
status: archived
schema_version: '1.0'
owner: platform-product
summary: ARCHIVED 2026-07-21. Temporary phased backlog for Astloom wedge readiness. Phases
  A–E complete; durable gates live in docs 19/26/31/33, product scope, gap register, and runbook
  35. Do not reuse doc_id.
tags:
- roadmap
- product-readiness
- backlog
- temporary
- archived
- wedge
- mcp
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/34-core-product-readiness-phased-backlog.md
lifecycle_lane: current
concern_lane: gap
audience_lane:
- platform-product
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- docs/00-master-plan/01-product-scope-and-feature-catalog.md
- as.doc.codegraph.competitive-intelligence-roadmap-adr
- as.doc.ckg.code-intel-risks
- as.doc.ckg.prod-retrieval-risks
- as.doc.ckg.prod-retrieval-live-test-gates
- docs/07-code-knowledge-graph/18-repository-code-wiki-risks-challenges-and-acceptance.md
- docs/10-gap-analysis/01-gap-register.md
doc_version: 1.1.1
audience:
- product
- engineer
- architect
- agent
primary_entities:
- CoreProductReadiness
- ProductPhase
- WedgeLaunch
relations_declared:
- type: depends_on
  target: as.doc.codegraph.competitive-intelligence-roadmap-adr
- type: complements
  target: as.doc.ckg.prod-retrieval-live-test-gates
- type: complements
  target: docs/10-gap-analysis/01-gap-register.md
chunk_hints:
  strategy: heading_h2
  max_tokens: 750
  overlap_tokens: 48
language: en
security_classification: internal
retirement:
  policy: delete_or_archive_when_complete
  when: All phase exit criteria below are checked AND durable acceptance has been copied into
    permanent docs (26, 31, 33, product scope, gap register).
  action: Set status archived OR delete this file; remove index bullet from 00-index.md; never
    reuse doc_id.
updated_at: 2026-08-10
---

# 34 - Core Product Readiness Phased Backlog

> **ARCHIVED 2026-07-21.** Phases A–E complete. Use permanent docs (`19`, `26`,
> `31`, `33`, product scope, gap register, runbook `35`) for acceptance.
> This file is historical; do not extend it. `doc_id` must not be reused.

## Purpose

Phase the remaining work to introduce Astloom as a **core product with main
wedge features** (code-graph explore / hybrid retrieval / change risk /
architecture), without re-building Waves 1–3 or the production retrieval stack.

**This document is temporary.** After all phases complete, **delete or archive
it** (see frontmatter `retirement`). Do not grow it into a permanent encyclopedia.

## Explicitly out of v1 marketing

| Item | Rule until its phase says otherwise |
| --- | --- |
| Repository Code Wiki (`14`–`18`) | **Not** a v1 claim — docs-only today |
| Multimodal / SQL-schema ingest | Deferred (ADR `19`) |
| GDS Enterprise / paid plugins | Not required (doc `32`) |
| Full multi-agent control-plane OS | Destination, not wedge sentence |

## Already done (do not re-phase)

- Phase 7 vertical slice + Neo4j SoR + MCP tools
- Waves 1–3 intelligence (explore, routes, TESTED_BY, risk, communities, path, freshness session)
- Production retrieval (BM25, FTS, BGE path, RRF, APOC, free Leiden)
- Live / fuzzer / challenge gates (doc `33`)

---

## Phase A — Honest quality bar (Must)

**Goal:** Never publish F1 / “Nx better” without harnesses.

| ID | Work item | Exit criterion | Status |
| --- | --- | --- | --- |
| A1 | Co-change / independent eval harness for explore & change-risk | Harness runnable; ADR `19` circular-claim ban still held | [x] `ckg_eval/` + `test_phase_a_honesty_eval.py` |
| A2 | Offline retrieval eval (nDCG or agreed proxy on ≥1 real repo) | Report artifact + threshold documented in `31` | [x] mean nDCG@10 ≥ 0.5 in `31` |
| A3 | Community quality vs co-change (lightweight) | One scored report; no marketing without it | [x] `community-vs-cochange-latest.json` |

**Exit Phase A:** A1–A3 done or explicitly waived in writing with narrowed claims. **Exited 2026-07-21.**

---

## Phase B — Freshness story freeze (Must)

**Goal:** Marketing matches ops reality.

| ID | Work item | Exit criterion | Status |
| --- | --- | --- | --- |
| B1 | Decide: ship filesystem watcher **or** market “explicit ingest + session pending-sync only” | Decision recorded in ADR or this backlog checkbox | [x] Explicit ingest + pending-sync (ADR `19`, 2026-07-21) |
| B2 | If watcher: sidecar/poll design + runbook | Deployable path; docs updated | [—] N/A for v1 (watcher deferred) |
| B3 | If no watcher: strip “always live / continuous index” from product copy | Copy audit done | [x] Index blurb + ADR freeze |

**Exit Phase B:** One chosen story, documented, no contradictory claims. **Exited 2026-07-21.**

---

## Phase C — Connect → improve → measure wedge loop (Must)

**Goal:** Buyer can connect a repo and see a measurable benefit proxy.

| ID | Work item | Exit criterion | Status |
| --- | --- | --- | --- |
| C1 | One-command / documented connect + ingest path | Runbook green on Compose | [x] `35-wedge-operator-connect-runbook.md` + `graph smoke` |
| C2 | MCP onboarding for `programming-cursor-mcp` (stable env + explore-first) | New machine can call explore in ≤30 minutes | [x] ≤30m checklist in doc `35` (architecture) |
| C3 | Benefit MVP: one with/without comparison (tokens and/or acceptance proxy) | End-to-end report, not catalog-only KPI JSON | [x] `samples/benefit-mvp/` → `benefit-mvp-latest.*` |
| C4 | Operator surface minimum (CLI acceptable; UI optional) | Connect, ingest, freshness, hybrid/explore smoke | [x] `astloom graph {ingest,freshness,explore,hybrid,smoke}` |

**Exit Phase C:** C1–C4 demonstrable in a sales/engineering dry-run. **Exited 2026-07-21.**

---

## Phase D — Sellable trust & isolation (Must for multi-tenant)

**Goal:** Safe to demo/sell beyond single-tenant lab.

| ID | Work item | Exit criterion | Status |
| --- | --- | --- | --- |
| D1 | Tenant/project isolation enforcement tests (graph + MCP scope) | GAP-005 closed or accepted with enforceable checks | [x] tests + threat model; GAP-005 CLOSED |
| D2 | Auth story for wedge (slice → documented IdP path or single-tenant mode) | Written mode: single-tenant OK vs multi-tenant blocked | [x] product scope v1 trust mode |
| D3 | License/marketing hygiene checklist (NOTICE, “inspired by”, no false affiliation) | Release checklist item | [x] in product scope |

**Exit Phase D:** D1–D3 checked; isolation mode explicit in product scope. **Exited 2026-07-21.**

---

## Phase E — Positioning freeze & packaging polish (Must for launch copy)

**Goal:** v1 message matches shipped code.

| ID | Work item | Exit criterion | Status |
| --- | --- | --- | --- |
| E1 | Freeze v1 feature sentence: explore / hybrid / change-risk / architecture | Product catalog updated | [x] product scope v1 sentence 2026-07-21 |
| E2 | Language claims match matrix (Python + documented tree-sitter set only) | Scope + README aligned | [x] catalog + README already match `10` |
| E3 | Default embeddings = real BGE or clear LiteLLM path; stub only fallback | `embedding_backend` visible; R-01 satisfied | [x] confirmed via `31` R-01 |
| E4 | Live gates green on real Compose (not skipped-as-pass) | Doc `33` suites green with secrets | [x] artifacts 2026-07-21 (9/9 live) |

**Exit Phase E:** External-facing copy + internal scope agree; E4 green. **Exited 2026-07-21.**

---

## Phase F — Deferred / Nice-to-have (do not block wedge v1)

Do **not** hold launch for these unless product explicitly expands scope.

| ID | Work item | Notes | Status |
| --- | --- | --- | --- |
| F1 | Repository Code Wiki implementation | Separate program; acceptance in `18` | deferred (docs-only) |
| F2 | Force BGE preload at process start | Ops knob (`31`) | [x] `ASTLOOM_EMBEDDING_PRELOAD` + `maybe_preload_embeddings` |
| F3 | Deeper framework / DI / package-manager import matrix | GAP-002 | [x] manifests + DI CALLS + confidence policy (2026-07-23); exotic DI iterative |
| F4 | Zero-touch installer / upgrade / repair productization | Platform Phases 8–9 depth | deferred |
| F5 | Full admin web UI (`frontend/` today empty) | After CLI/MCP wedge | deferred |
| F6 | Human approval UX (GAP-004) | Governed sells later | deferred |
| F7a | Turbovec Stage-2 ANN accelerator | Optional; default off | [x] `vector_index` + memory/code-graph parity, metrics, snapshots (2026-07-26); GAP-T03 |
| F7b | SQL-schema ingest | Optional accelerator | deferred (ADR `19`) |

Also shipped with F2/F3: optional **batched** pending-sync poll watcher (`astloom graph watch --debounce/--max-wait`) — coalesces agent coding bursts; does not replace explicit ingest.

---

## Suggested sequence

```text
A (eval) ──► B (freshness) ──► C (connect/measure) ──► D (trust) ──► E (launch copy)
                              └── F2/F3/F7a (+ poll watcher) shipped; F1/F4–F6/F7b remain deferred
```

Do not start Code Wiki (F1) before E1 freeze unless product re-scopes v1.

---

## Progress tracking

| Phase | Status | Owner | Done when |
| --- | --- | --- | --- |
| A | done | platform-product | Exit criteria A — 2026-07-21 |
| B | done | platform-product | Exit criteria B — 2026-07-21 |
| C | done | platform-product | Exit criteria C — 2026-07-21 |
| D | done | platform-product | Exit criteria D — 2026-07-21 |
| E | done | platform-product | Exit criteria E — 2026-07-21 |
| F | partial | platform-product | F2/F3/F7a + poll watcher done; F1/F4–F6/F7b remain deferred |

Update status in this table only. When a phase exits, fold durable gates into permanent docs (`26`, `31`, `33`, gap register, product scope)—**do not** leave acceptance only here.

---

## Retirement checklist (mandatory)

When Phases A–E are complete:

1. Copy lasting acceptance bullets into `26` / `31` / `33` / product scope / gap register. **Done 2026-07-21.**
2. Set this doc `status: archived` **or delete the file**. **Done — status archived.**
3. Remove the bullet from `00-index.md`. **Done** (History note retained).
4. Do **not** reuse `doc_id` `as.doc.ckg.core-product-readiness-phased-backlog`.
5. Optional: keep a one-line note in `00-index.md` History that readiness backlog `34` was retired on DATE. **Done.**
