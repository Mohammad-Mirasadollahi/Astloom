---
doc_id: as.doc.ops.index
title: 09 - Platform Governance and Operations Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: This section completes the Astloom plan from an operational and governance perspective.
  Earlier sections define product architecture, technical logic, code graph design, and software
  engineering architecture. This section defines the controls required to run the platform
  safely.
tags:
- index
- ops
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/00-index.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols:
- tests/backend/gates/governance-catalog-verification/run_gate.py::main
doc_version: 1.2.1
updated_at: 2026-08-10
---

# 09 - Platform Governance and Operations Index

## Purpose

This section completes the Astloom plan from an operational and governance perspective. Earlier sections define product architecture, technical logic, code graph design, and software engineering architecture. This section defines the controls required to run the platform safely in real teams and enterprise environments.

## Files

- 01-security-access-control-and-privacy.md defines identity, authorization, tenant boundaries, data sensitivity, prompt safety, and privacy requirements.
- 02-observability-slo-and-incident-response.md defines logs, metrics, traces, SLOs, alerting, and incident handling.
- 03-ci-cd-release-and-environment-strategy.md defines CI gates, release workflow, environment separation, migrations, and rollback strategy.
- 04-data-retention-backup-and-disaster-recovery.md defines retention, backup, restore, audit evidence preservation, and disaster recovery expectations (cross-links automated follow-up Task retention in core-data model doc 09).
- 13-project-scoped-backup-and-restore.md is the operator runbook for portable `.asbak` project migrate (CLI export/validate/dry-run/restore + MCP status/dry-run).
- 05-api-versioning-and-contract-governance.md defines API contracts, schema versioning, backward compatibility, and deprecation policy.
- 12-schema-registry-architecture.md decides v1 schema registry shape (repository-directory catalog) and closes GAP-008.
- 06-runbooks-and-operational-procedures.md defines standard operating procedures for common platform workflows.
- 07-risk-register-and-open-decisions.md captures platform risks and decisions that must be resolved before implementation.
- 08-glossary-and-ubiquitous-language.md defines common terminology used across the documentation tree.
- 09-automated-deployment-and-connectivity-runbooks.md defines operational runbooks for automated first installation, agent connector registration, repository registration, external resource connection, automated upgrade, drift detection, and repair.
- 10-impact-reporting-and-benefit-measurement.md defines the impact measurement framework, KPI definitions, instrumentation requirements, baseline strategy, with-or-without Astloom comparison, dashboard states, evidence model, and reporting contracts for code generation speed, bug reduction, architecture quality, rework reduction, token consumption, and dead-code cleanup.
- 11-phase9-verification-and-acceptance.md defines the governance-catalog feature gate and named verification commands under `tests/backend/gates/governance-catalog-verification/`.

## Implementation Slice

Phase 9 verification home:

- Risk/decision catalog: `backend/configs/governance/risk-open-decisions.json`
- Impact KPI catalog: `backend/configs/governance/impact-kpis.json`
- Catalog loader: `backend/packages/governance_catalog/`
- Gate package: `tests/support/governance_catalog_gate/`
- Tests: `tests/backend/gates/governance-catalog-verification/`

```bash
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/governance-catalog-verification -q
.venv/bin/python tests/backend/gates/governance-catalog-verification/run_gate.py
```

## Why This Section Exists

A design is incomplete if it only explains features. A production-grade platform also needs security rules, operational signals, deployment strategy, data retention, versioning, runbooks, automated installation, connector onboarding, repair workflows, impact reporting, benefit measurement, and risk ownership. These documents make the Astloom plan easier to implement, review, fund, install, connect, measure, and operate.
