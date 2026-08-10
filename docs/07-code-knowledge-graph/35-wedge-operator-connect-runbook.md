---
doc_id: as.doc.ckg.wedge-operator-connect-runbook
title: 35 - Wedge Operator Connect and Ingest Runbook
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-product
summary: 'One-path operator runbook: Compose (or memory smoke) → register project → ingest
  → freshness/hybrid/explore.'
tags:
- runbook
- ingest
- mcp
- wedge
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/35-wedge-operator-connect-runbook.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
language: en
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 35 - Wedge Operator Connect and Ingest Runbook


## Purpose

One-path operator runbook: Compose (or memory smoke) → register project → ingest → freshness/hybrid/explore. Closes backlog 34 Phase C1.

## Goal

Connect a repo and prove hybrid/explore within one operator session. Freshness
story is **explicit ingest + session pending-sync** (ADR `19` Phase B freeze) —
not continuous save-watch indexing.

## Prerequisites

```bash
cd /opt/Astloom
bash scripts/ensure-venv.sh
source .venv/bin/activate
astloom doctor
```

## Path A — Local memory smoke (no Compose)

Fast dry-run for CLI wiring:

```bash
astloom graph smoke \
  --tenant demo --workspace eng --project wedge \
  --path samples/e2e-graph-probe/src \
  --query "login password"
```

Expect JSON `"ok": true` with `hybrid_hits` and `explore_sections` ≥ 1.

## Path B — Compose + Neo4j (prod-like)

1. Bring up Neo4j (and optional Postgres) via the project Compose profile used in
   live gates (`33`). Set `ASTLOOM_NEO4J_PASSWORD` and related env from the
   port profile (`astloom ports show`).
2. Register and activate the programming profile:

```bash
astloom project register \
  --tenant demo --workspace eng --project wedge \
  --name "Wedge" --usage-profile programming-cursor-mcp

astloom project activate \
  --tenant demo --workspace eng --project wedge \
  --usage-profile programming-cursor-mcp
```

3. Ingest via probe (Neo4j) or CLI with durable backend:

```bash
export ASTLOOM_CODE_GRAPH_STORE=neo4j
export ASTLOOM_GRAPH_CLI_BACKEND=neo4j
python samples/e2e-graph-probe/run_probe.py
## or:
astloom graph ingest \
  --tenant demo --workspace eng --project wedge \
  --path samples/e2e-graph-probe/src
astloom graph freshness --tenant demo --workspace eng --project wedge
astloom graph hybrid --tenant demo --workspace eng --project wedge --query "login"
astloom graph explore --tenant demo --workspace eng --project wedge --query "login password"
```

4. Optional benefit proxy report:

```bash
python samples/benefit-mvp/run_benefit_mvp.py
## → tests/artifacts/code-graph-eval/benefit-mvp-latest.{json,md}
```

## Acceptance

- [x] Path A `graph smoke` exits 0 on this host (verified 2026-07-21).
- [x] Path B: Neo4j live isolation + Compose-backed graph path verified when secrets present (`test_tenant_isolation_neo4j_live.py`; CLI `ASTLOOM_GRAPH_CLI_BACKEND=neo4j`).
- [x] No marketing claim of always-live indexing in operator copy (ADR `19` + product scope freeze).
