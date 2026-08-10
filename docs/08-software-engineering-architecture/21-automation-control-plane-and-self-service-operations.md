---
doc_id: as.doc.sea.automation-control-plane-and-self-service-operations
title: 21 - Automation Control Plane And Self-Service Operations
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom should automate not only first installation, but also ongoing operations.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/21-automation-control-plane-and-self-service-operations.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- docs/08-software-engineering-architecture/51-software-upgrade-server-and-client.md
- docs/09-platform-governance-operations/09-automated-deployment-and-connectivity-runbooks.md
- docs/08-software-engineering-architecture/19-zero-touch-installation-and-bootstrap-automation.md
- docs/08-software-engineering-architecture/39-local-install-runbook.md
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 21 - Automation Control Plane And Self-Service Operations

## Purpose

Astloom should automate not only first installation, but also ongoing operations. The platform should provide a control plane that can inspect state, validate configuration, repair common issues, onboard connectors, rotate credentials, run upgrades, and expose self-service actions with safe guardrails.

This document defines the engineering design for the automation control plane and self-service operations.

## Automation Philosophy

Automation should reduce user effort without hiding risk.

The system should automate:

- setup.
- validation.
- configuration generation.
- connector registration.
- dependency checks.
- migration execution.
- health checks.
- smoke tests.
- diagnostics.
- safe repair actions.
- upgrades.
- rollback preparation.
- documentation of results.

The system should ask for human approval when an action is destructive, security-sensitive, high-risk, or not reversible.

## Automation Control Plane Responsibilities

The automation control plane should provide:

- environment inventory.
- service registry.
- connector registry.
- configuration registry.
- port registry.
- contract version registry.
- migration state registry.
- health and readiness state.
- automation job history.
- evidence reports.
- self-service action catalog.

It should be accessible through CLI, admin-console, and internal APIs.

## Self-Service Action Catalog

Astloom should expose safe self-service actions.

Examples:

- install local development stack.
- install single-node stack.
- validate environment.
- generate config profile.
- run port preflight.
- register agent connector.
- register repository.
- register ticket system.
- test connector.
- rotate connector credential.
- run migrations.
- validate graph schema.
- validate broker topology.
- run smoke tests.
- export installation report.
- disable connector.
- restart service when allowed.
- collect diagnostics bundle.

Each action should define required permission, risk level, inputs, outputs, rollback behavior, and audit behavior.

## Automation Job Model

Automation actions should be represented as jobs.

Job fields:

- job_id.
- job_type.
- requested_by.
- workspace_id.
- environment.
- status.
- risk_level.
- inputs_ref.
- outputs_ref.
- started_at.
- finished_at.
- current_step.
- completed_steps.
- failed_step.
- error_code.
- retryable.
- evidence_report_ref.
- correlation_id.

Job status values:

- pending.
- waiting_for_approval.
- running.
- succeeded.
- failed.
- canceled.
- rolled_back.
- partially_completed.

## Automation Step Model

Each automation job should be decomposed into steps.

Step fields:

- step_id.
- name.
- type.
- status.
- idempotent.
- rollback_supported.
- started_at.
- finished_at.
- output_summary.
- error_summary.
- repair_hint.

Steps should be idempotent when possible so failed automation can resume safely.

## Safe Defaults

Automation should choose safe defaults.

Safe defaults include:

- non-default development ports.
- local-only credentials in local mode.
- disabled destructive actions until explicitly approved.
- least-privilege connector permissions.
- no production mode without explicit environment profile.
- no secret printing.
- no direct database sharing between services.
- no connector marked ready before validation.
- no service marked ready before migration compatibility check.

## Configuration Drift Detection

The automation control plane should detect drift.

Drift examples:

- running service uses config not recorded in registry.
- port map differs from generated profile.
- broker topic missing.
- migration version differs from expected state.
- connector supports an old contract version.
- graph schema version is stale.
- service registry endpoint no longer responds.
- documentation says a module exists but registry does not know it.

Drift should create an Issue or operational alert depending on severity.

## Automated Repair

Some repairs can be automated.

Examples:

- regenerate local port map.
- recreate missing broker topic.
- rerun failed idempotent migration step.
- refresh service registry entry.
- rotate expired local development token.
- rebuild generated SDK after contract change.
- restart failed local service.
- revalidate connector after configuration update.

Repairs that can lose data, change production permissions, or affect external systems should require approval.

## Upgrade Automation

Upgrade should be automated and validated.

**Shipped operator path:** [51 - Software Upgrade Server And Client](./51-software-upgrade-server-and-client.md)
(`bash install.sh --upgrade`, `astloom upgrade prepare|run|check|client`, Accept gates for control-plane / high risk, evidence under `.astloom/upgrade-evidence/`).

Upgrade flow:

1. read current installation state.
2. compare target artifact versions.
3. validate compatibility.
4. validate migrations.
5. validate config schema changes.
6. create upgrade plan.
7. run pre-upgrade backup when required.
8. execute staged upgrade.
9. run post-upgrade smoke tests.
10. update registry state.
11. write upgrade evidence report.
12. provide rollback or forward-fix guidance.

Local-dev control-plane jobs implement steps 1–3 and 6–12 for install-state + `install.sh` deploy; service-owned DB/graph migrations remain on each service migration path when present.

## Diagnostics Bundle

The automation control plane should generate a diagnostics bundle.

The bundle may include:

- service versions.
- config schema versions.
- effective port map.
- health results.
- readiness results.
- connector health summary.
- migration state.
- broker topology summary.
- graph schema summary.
- recent failed automation jobs.
- relevant logs with secrets redacted.
- correlation IDs for failed workflows.

The bundle must not include secrets.

## Human Approval Boundaries

Automation should stop and request approval for high-risk operations.

Approval required examples:

- destructive database migration.
- production credential rotation.
- disabling security rule enforcement.
- deleting connector state.
- changing external provider permissions.
- production service restart when impact is expected.
- bulk replay of dead-letter events.
- restoring from backup.

Approval records should include the planned action, risk, evidence, approver, decision, and time.

## Acceptance Criteria

The automation control plane is acceptable when:

- setup, validation, connector onboarding, upgrades, diagnostics, and safe repair actions are available through self-service workflows.
- automation jobs are tracked with steps, evidence, status, and correlation IDs.
- common failures provide repair hints.
- drift detection creates visible Issues or alerts.
- high-risk actions require approval.
- users rarely need manual installation or configuration steps for normal supported scenarios.

## Related Documents

- [51 - Software Upgrade Server And Client](./51-software-upgrade-server-and-client.md)
- [09 - Automated Deployment And Connectivity Runbooks](../09-platform-governance-operations/09-automated-deployment-and-connectivity-runbooks.md)
- [19 - Zero-Touch Installation And Bootstrap Automation](./19-zero-touch-installation-and-bootstrap-automation.md)
- [39 - Local Install Runbook](./39-local-install-runbook.md)
