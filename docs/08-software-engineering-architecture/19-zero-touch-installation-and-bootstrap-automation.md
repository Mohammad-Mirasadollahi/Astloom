---
doc_id: as.doc.sea.zero-touch-installation-and-bootstrap-automation
title: 19 - Zero Touch Installation And Bootstrap Automation
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom must be installable and deployable with minimal manual work.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/19-zero-touch-installation-and-bootstrap-automation.md
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

# 19 - Zero Touch Installation And Bootstrap Automation

## Purpose

Astloom must be installable and deployable with minimal manual work. The first installation should prepare the platform, configure required services, validate dependencies, create initial settings, start the runtime, run health checks, and report a clear ready state without asking the user to perform scattered manual setup steps.

This document defines the engineering requirements for zero-touch installation, automated bootstrap, dependency provisioning, configuration generation, validation, and first-run readiness.

## Product Requirement

The installation experience should feel like a guided automated setup, not a manual infrastructure project.

The user should not need to manually:

- create every config file.
- choose service ports without guidance.
- install every dependency by hand.
- create database schemas by hand.
- wire broker topics by hand.
- configure every agent connector by hand.
- discover missing prerequisites through trial and error.
- manually check whether services are healthy.
- manually produce a connection guide for agents.

When manual input is unavoidable, the installer should ask for the smallest possible set of values and generate everything else from templates, profiles, discovery, and validated defaults.

## Installation Modes

Astloom should support multiple installation modes.

| Mode | Purpose | Expected User Effort |
| --- | --- | --- |
| local-dev | developer workstation or remote development host | one command plus optional overrides |
| single-node | small team, proof of concept, internal server | one command plus environment profile |
| production-cluster | production deployment on orchestrated infrastructure | declarative config plus automated deployment |
| air-gapped | enterprise environment without internet access | offline bundle plus automated validation |
| upgrade | update existing installation | one command with preflight and rollback plan |
| connector-only | add an agent, IDE, provider, or resource connector | one command or self-service registration |

Each mode should use the same configuration model and validation principles.

## Installer Responsibilities

The installer or deployment automation should perform these responsibilities:

- detect operating system and architecture.
- verify required runtime dependencies.
- install or validate package managers when allowed.
- prepare service users or runtime identities when needed.
- generate configuration profiles.
- allocate or validate non-default development ports.
- generate secret references or local development secrets safely.
- provision databases, graph stores, broker topics, indexes, and schemas.
- run migrations.
- register default services.
- create initial admin or bootstrap identity through a secure flow.
- start services in the selected runtime mode.
- wait for readiness.
- run smoke tests.
- print connection endpoints and next steps.
- write an installation evidence report.

## Non-Interactive And Interactive Behavior

The installer should support both non-interactive and interactive operation.

Non-interactive mode should be suitable for CI, remote servers, repeatable deployments, and scripted environments.

Interactive mode should be suitable for a human setting up the platform for the first time.

Rules:

- every interactive prompt must have a non-interactive equivalent.
- every generated value must be written to a documented config profile.
- secrets must not be printed in terminal output.
- failed validation should show the exact failing check and suggested fix.
- installation should be resumable after failure.

## Bootstrap Inputs

The minimal bootstrap input should include:

- installation mode.
- environment name.
- workspace or tenant name.
- public base URL or local base URL.
- admin identity source or bootstrap admin email.
- secret provider mode.
- data storage mode.
- broker mode.
- graph mode.
- connector mode.

Everything else should be generated, discovered, or validated through profiles.

## Generated Bootstrap Outputs

A successful bootstrap should generate:

- effective environment profile.
- service configuration files.
- generated local port map.
- service registry entries.
- contract version registry snapshot.
- database migration state.
- broker topic declarations.
- graph schema state.
- initial feature flag state.
- bootstrap admin record or identity binding.
- connector registration endpoint.
- agent onboarding token or registration flow reference.
- health report.
- installation evidence report.

## Preflight Checks

Preflight checks must run before installation changes the system.

Checks should include:

- operating system support.
- CPU architecture support.
- disk space.
- memory.
- required command availability.
- network reachability when needed.
- package repository reachability when needed.
- port availability.
- container runtime availability when used.
- file permissions.
- database connectivity when using existing databases.
- broker connectivity when using existing broker.
- graph database connectivity when using existing graph store.
- secret provider availability.

Preflight should produce machine-readable and human-readable output.

## Dependency Provisioning

Dependency provisioning should be automated but policy-aware.

The system should support:

- managed local dependencies for local-dev and single-node modes.
- external managed dependencies for production-cluster mode.
- offline dependency bundles for air-gapped mode.
- dependency version lock files for reproducibility.
- checksum validation for downloaded or bundled assets.

The installer should never silently install unexpected global dependencies in production mode. It should follow the selected profile and explain what it will manage.

## Configuration Generation

Configuration generation should use templates and schemas.

Generated config must include:

- service names.
- service ports.
- service URLs.
- database references.
- broker references.
- graph references.
- secret references.
- feature flags.
- retry policies.
- timeout policies.
- logging profile.
- metrics profile.
- connector registry settings.
- agent onboarding settings.

Generated config must pass schema validation before services start.

## Port Automation

Installation must avoid default framework ports during development.

Port automation should:

- reserve a project-specific range.
- detect conflicts before startup.
- generate a port map.
- support user overrides.
- validate overrides.
- update service discovery with effective ports.
- print a summary of effective endpoints.

Port values must not be hard-coded in services.

## Database And Store Bootstrap

Store bootstrap should be automatic.

Responsibilities:

- create databases or schemas when managed mode is selected.
- validate existing store compatibility when external mode is selected.
- run migrations in the correct order.
- create required indexes.
- create graph constraints and indexes.
- create vector index collections when used.
- validate migration state.
- create initial retention policy records.
- create backup policy records where applicable.

If a migration cannot run safely, bootstrap should stop before starting dependent services.

## Broker Bootstrap

Broker bootstrap should be automatic.

Responsibilities:

- create topics or queues.
- configure retry policies.
- configure dead-letter destinations.
- register consumer groups.
- validate publish and consume path.
- run a broker smoke test.
- record broker topology in the installation evidence report.

## Service Registry Bootstrap

Astloom should maintain a service registry for internal service discovery.

The bootstrap process should register:

- service name.
- service version.
- internal URL.
- public URL when applicable.
- health endpoint.
- readiness endpoint.
- contract version set.
- required dependencies.
- effective port.
- environment profile.

This registry makes agent and connector onboarding easier because clients can discover the correct endpoints instead of relying on static documentation.

## First-Run Readiness

After installation, the system should run first-run validation.

Validation should verify:

- every required service is healthy.
- every required service is ready.
- databases are migrated.
- broker topics exist.
- graph schema exists.
- config schema versions match service expectations.
- service registry is populated.
- connector registry is reachable.
- admin-console can call api-gateway.
- api-gateway can call core services.
- audit-service records a bootstrap event.
- agent onboarding endpoint is available.

## Installation Evidence Report

Every installation should produce a report.

The report should include:

- installation mode.
- environment name.
- timestamp.
- installer version.
- source revision or artifact versions.
- generated config paths.
- effective service endpoints.
- port map.
- dependency versions.
- migration versions.
- broker topology.
- graph schema version.
- smoke test results.
- warnings.
- next steps.

The report must not include secrets.

## Failure And Resume Behavior

Installation should be resumable.

Rules:

- each step should be idempotent when possible.
- completed steps should be recorded.
- failed steps should include repair guidance.
- rerunning the installer should continue from a safe checkpoint.
- partially created resources should be detected.
- rollback should be supported for steps where safe.
- destructive cleanup should require explicit confirmation.

## Acceptance Criteria

Zero-touch installation is acceptable when:

- a supported environment can be installed with one primary command and a small configuration profile.
- preflight catches missing dependencies and port conflicts before startup.
- databases, graph stores, broker topics, migrations, indexes, and service registry entries are created or validated automatically.
- services start with generated and validated configuration.
- first-run readiness proves that the platform is usable.
- installation produces an evidence report without secrets.
- failures are resumable and explain the smallest safe fix.


## Venv And Docker Bootstrap Requirements

Bootstrap automation must create or validate `/root/Astloom/.venv` before installing Python dependencies. It must not install packages into the global Python interpreter.

Bootstrap automation must start local infrastructure through Docker Compose profiles and validate non-default host ports before starting services. It must not modify existing service ports unless a migration is explicitly requested.

The bootstrap evidence report must include enabled Compose profiles, resolved port map, virtual environment path, dependency installation status, Docker availability, and service health checks.
