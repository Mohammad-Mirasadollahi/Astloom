---
doc_id: as.doc.ops.phase9-verification-and-acceptance
title: Phase 9 - Verification and Acceptance
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Phase 9 completes operational governance. Its executable gate proves that security,
  observability, release, retention, contract versioning, runbooks, automated deployment/connectivity
  procedures, impact KPIs, risks, decisions, and glossary artifacts exist and that machine-readabl.
tags:
- standard
- ops
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/11-phase9-verification-and-acceptance.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- tests/backend/gates/governance-catalog-verification/run_gate.py::main
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Phase 9 - Verification and Acceptance

## Purpose

Phase 9 completes operational governance. Its executable gate proves that security, observability, release, retention, contract versioning, runbooks, automated deployment/connectivity procedures, impact KPIs, risks, decisions, and glossary artifacts exist and that machine-readable risk and KPI catalogs are complete enough for review.

## Gate Artifacts

| Artifact | Path |
| --- | --- |
| Governance docs | `docs/09-platform-governance-operations/` |
| Risk and decision catalog | `backend/configs/governance/risk-open-decisions.json` |
| Impact KPI catalog | `backend/configs/governance/impact-kpis.json` |
| Catalog loader | `backend/packages/governance_catalog/` |
| Verification package | `tests/support/governance_catalog_gate/` |
| Gate tests | `tests/backend/gates/governance-catalog-verification/` |

## Named Commands

```bash
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/governance-catalog-verification -q
.venv/bin/python tests/backend/gates/governance-catalog-verification/run_gate.py
```

## Exit Checks Covered by the Gate

- Required Phase 9 governance documents exist and contain key topic markers.
- Risk and open-decision catalog entries include owners, mitigations or proposed resolutions, and review dates.
- Impact KPI catalog covers code generation speed, bug reduction, architecture quality, rework reduction, token consumption, and dead-code cleanup with definition, instrumentation, baseline, scope, time range, sample size, caveats, and evidence drilldown.
- Comparison method is explicitly with-or-without Astloom.

## Acceptance

Phase 9 passes when `check_phase_gate()` returns `pass` and `run_all_checks()` returns only `passed` results. A documented waiver reference may mark the gate `waived` when an explicit owner accepts temporary failures.
