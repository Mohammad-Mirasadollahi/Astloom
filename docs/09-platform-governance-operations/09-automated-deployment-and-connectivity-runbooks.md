---
doc_id: as.doc.ops.automated-deployment-and-connectivity-runbooks
title: 09 - Automated Deployment And Connectivity Runbooks
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines operational runbooks for automated installation, deployment,
  connector onboarding, validation, repair, and upgrade workflows.
tags:
- runbook
- ops
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/09-automated-deployment-and-connectivity-runbooks.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- docs/08-software-engineering-architecture/51-software-upgrade-server-and-client.md
- docs/08-software-engineering-architecture/39-local-install-runbook.md
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 09 - Automated Deployment And Connectivity Runbooks

## Purpose

This document defines operational runbooks for automated installation, deployment, connector onboarding, validation, repair, and upgrade workflows. The goal is to ensure Astloom can be installed and connected to agents and resources with minimal manual work.

## Runbook: First Installation

Goal: install a supported Astloom environment and reach a ready state.

Automated steps:

1. run preflight checks.
2. generate environment profile.
3. allocate or validate ports.
4. provision managed dependencies or validate external dependencies.
5. generate service configuration.
6. create or validate databases.
7. create graph schema and indexes.
8. create broker topics and dead-letter destinations.
9. run migrations.
10. register services.
11. start services.
12. wait for readiness.
13. run smoke tests.
14. create bootstrap audit event.
15. write installation evidence report.

Operator checks:

- confirm installation mode is correct.
- confirm no secrets are printed.
- confirm readiness report is successful.
- confirm generated connection endpoints are visible.

Failure response:

- read failed step.
- follow repair hint.
- rerun installer in resume mode.
- escalate only if the same step fails after repair.

## Runbook: Agent Connector Registration

Goal: connect a new agent to Astloom with minimal manual configuration.

Automated steps:

1. create connector record.
2. select workspace and environment.
3. generate connection profile.
4. issue onboarding token or identity binding.
5. validate API contract compatibility.
6. validate authentication.
7. run sample health request.
8. register capabilities.
9. mark connector ready.
10. write connector evidence report.

Operator checks:

- confirm connector owner.
- confirm requested capabilities.
- confirm least-privilege permission scope.
- confirm validation passed.

Failure response:

- inspect connector diagnostics.
- rotate onboarding token if expired.
- rerun validation.
- keep connector disabled until validation succeeds.

## Runbook: Repository Registration

Goal: connect a repository so code graph and docs sync workflows can operate.

Automated steps:

1. register repository URL or local path.
2. validate access permission.
3. detect repository type and languages.
4. detect documentation paths.
5. select parser extensions.
6. create graph ingestion profile.
7. run initial lightweight scan.
8. create graph schema records.
9. link repository to workspace.
10. run graph health check.

Operator checks:

- confirm repository owner.
- confirm included and excluded paths.
- confirm parser support.
- confirm graph scan result.

Failure response:

- check access credentials.
- check unsupported language list.
- check parser errors.
- create gap entry if required parser support is missing.

## Runbook: External Resource Connector

Goal: connect a ticket, approval, CI, model provider, or observability resource.

Automated steps:

1. choose connector type.
2. validate required fields.
3. create credential reference.
4. discover provider capabilities when supported.
5. map provider concepts to Astloom contracts.
6. run connection test.
7. run safe sample operation when supported.
8. register capabilities.
9. enable connector or keep disabled for approval.

Operator checks:

- confirm provider permissions.
- confirm callback URLs.
- confirm rate limit behavior.
- confirm unsupported capabilities are documented.

Failure response:

- inspect normalized provider error.
- verify callback or network reachability.
- verify credential scope.
- keep connector disabled until validation passes.

## Runbook: Automated Upgrade

Goal: upgrade an existing Astloom installation safely.

**Implementation (local-dev + CLI control plane):** see
[51 - Software Upgrade Server And Client](../08-software-engineering-architecture/51-software-upgrade-server-and-client.md)
(`bash install.sh --upgrade`, `astloom upgrade …`, client handshake via `platform.ping`).

Automated steps:

1. read current installation state.
2. compare target versions.
3. validate contract compatibility.
4. validate config schema changes.
5. validate migration plan.
6. create upgrade plan.
7. request approval when risk requires it.
8. run backup when required.
9. deploy artifacts.
10. run migrations.
11. run post-upgrade smoke tests.
12. update registries.
13. write upgrade evidence report.

Operator checks:

- review upgrade plan.
- review migration risk.
- review rollback or forward-fix plan.
- monitor post-upgrade metrics.

Failure response:

- stop rollout.
- use rollback when safe.
- use forward-fix when migrations are irreversible.
- preserve evidence report for incident review.

## Runbook: Drift Detection And Repair

Goal: detect and repair configuration, registry, dependency, or connector drift.

Automated checks:

- service registry vs running services.
- port map vs effective ports.
- config profile vs runtime diagnostics.
- broker topology vs expected topics.
- graph schema vs expected version.
- connector contract versions vs registry.
- migration state vs service requirements.

Repair actions:

- regenerate local config.
- refresh service registry.
- recreate missing broker topic.
- rerun idempotent migration step.
- revalidate connector.
- rotate local development token.
- restart local service when allowed.

Operator checks:

- approve risky repair actions.
- verify repair evidence.
- create gap when drift cannot be automatically repaired.

## Acceptance Criteria

Automated deployment and connectivity runbooks are acceptable when:

- first installation is automated and resumable.
- agent and resource connector onboarding is self-service and validated.
- upgrades include compatibility checks, evidence reports, and rollback or forward-fix guidance.
- drift detection creates visible repair actions.
- risky automation requires approval.
- manual user setup is minimized for supported scenarios.
