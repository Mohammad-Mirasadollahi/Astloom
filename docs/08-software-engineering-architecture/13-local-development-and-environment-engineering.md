---
doc_id: as.doc.sea.local-development-and-environment-engineering
title: 13 - Local Development And Environment Engineering
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the expected local development and environment strategy for
  Astloom. It explains how engineers should run services safely, avoid port conflicts, manage
  configuration, use test data, and reproduce behavior across machines.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/13-local-development-and-environment-engineering.md
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

# 13 - Local Development And Environment Engineering

## Purpose

This document defines the expected local development and environment strategy for Astloom. It explains how engineers should run services safely, avoid port conflicts, manage configuration, use test data, and reproduce behavior across machines.

## Local Development Goals

Local development should be:

- reproducible.
- explicit about dependencies.
- safe from port conflicts.
- close enough to production behavior for meaningful tests.
- fast enough for daily engineering.
- isolated from real secrets and production data.
- easy to reset.

## Environment Types

Astloom should define these environment types:

| Environment | Purpose |
| --- | --- |
| local | individual developer machine or remote development host |
| test | automated test execution |
| integration | shared environment for multi-service validation |
| staging | production-like validation before release |
| production | real user and agent workloads |

Each environment should have a named configuration profile.

## Local Runtime Modes

Local development should support multiple modes.

| Mode | Description | Use Case |
| --- | --- | --- |
| single-service | one service with mocked dependencies | focused domain work |
| service-with-deps | one service with real local stores and broker | integration work |
| core-stack | core-data, broker, config, memory, audit | common platform work |
| graph-stack | code-graph, docs-sync, graph database | code knowledge work |
| full-stack | all core services and apps | E2E validation |

Engineers should not need full-stack mode for every change.

## Port Management

Local ports must be configured, not hard-coded.

Rules:

- avoid framework default ports in development.
- store port allocation in local-dev config.
- run port-preflight before starting services.
- fail startup when a required port is unavailable.
- allow developers to override ports through a local override file.
- never commit machine-specific port overrides.

The development port management document defines recommended non-default ranges.

## Configuration Profiles

Each service should provide example config files.

Recommended files:

    services/<service-name>/config/development.example.yaml
    services/<service-name>/config/test.example.yaml
    services/<service-name>/config/production.example.yaml

Local generated or private files should be ignored by source control.

Configuration should include:

- service port.
- database connection reference.
- broker connection reference.
- feature flags.
- timeout values.
- retry policy.
- log level.
- external adapter mode.
- memory weight profile when applicable.
- graph ingestion profile when applicable.

## Secrets

Secrets must not be committed.

Local development should use:

- local secret references.
- fake credentials.
- provider sandbox credentials.
- environment variables managed outside committed files.

Logs, events, prompts, and audit records should redact secret-like values even in local mode.

## Local Data

Local data should be easy to reset.

Recommended datasets:

- minimal dataset for service startup.
- realistic dataset for E2E tests.
- graph fixture repository.
- memory retrieval fixture set.
- adapter payload fixture set.
- rule evaluation fixture set.

Fixtures should include edge cases such as stale docs, duplicate events, conflicting decisions, low-confidence memory, and failed approvals.

## Development Commands

The repository should provide standard commands.

Expected command groups:

- bootstrap local dependencies.
- start one service.
- start a named stack.
- stop a named stack.
- reset local data.
- run port preflight.
- run docs validation.
- run contract validation.
- run affected tests.
- run full local verification.

Commands should print clear next steps when they fail.

## Remote Development

When development happens on a remote Linux host, the remote workspace should be treated as the real project workspace.

Remote development rules:

- all project files, package installs, builds, tests, and git commands should run inside the remote project path.
- local Windows tooling may control the remote session, but project state lives on Linux.
- GUI tools should not be required for automated setup.
- SSH tunnel configuration should be documented and reusable.
- local ports exposed through tunnels should still follow port management rules.

## Environment Parity

Local and production do not need to be identical, but behavior-critical differences must be explicit.

Differences to document:

- mocked external providers.
- reduced retention duration.
- smaller graph datasets.
- disabled expensive model calls.
- local-only feature flags.
- fake authentication mode.
- single-process service mode.

Hidden environment differences cause bugs and should be avoided.

## Troubleshooting Requirements

Local development should include troubleshooting docs for:

- port conflict.
- failed database migration.
- broker connection failure.
- graph database startup failure.
- stale generated contracts.
- failed docs validation.
- missing environment variables.
- adapter sandbox failure.
- test fixture reset.

## Acceptance Criteria

Local development engineering is acceptable when:

- engineers can start a focused service without running the entire platform.
- port conflicts are detected before startup.
- config is typed, documented, and environment-specific.
- secrets are not committed or printed.
- fixtures cover realistic and edge-case workflows.
- remote development on the Linux workspace is documented as a first-class workflow.
