---
doc_id: as.doc.sea.sdk-engineering-and-contract-generation
title: 27 - SDK Engineering And Contract Generation
doc_type: contract
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom SDKs should be engineered, generated, tested,
  released, and governed. The SDK is a product surface and an engineering boundary. It must
  be treated with the same rigor as public APIs, event contracts, and database migrations.
tags:
- contract
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/27-sdk-engineering-and-contract-generation.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 27 - SDK Engineering And Contract Generation

## Purpose

This document defines how Astloom SDKs should be engineered, generated, tested, released, and governed. The SDK is a product surface and an engineering boundary. It must be treated with the same rigor as public APIs, event contracts, and database migrations.

## Engineering Principles

- public contracts first.
- generated low-level clients where possible.
- stable hand-curated domain facades for common workflows.
- no service internals in SDK packages.
- no hard-coded deployment assumptions.
- explicit scoping for organization, workspace, project, actor, and correlation.
- deterministic error mapping.
- contract tests for every generated operation.
- examples that compile or run in CI.
- release notes for every SDK version.

## Package Architecture

The SDK should be a modular package family, not one large unstructured package.

| Package | Responsibility |
| --- | --- |
| contracts-generated | generated types and low-level clients from API/event schemas. |
| sdk-core | auth, transport, config, retries, idempotency, errors, pagination, observability. |
| sdk-project | project-scoped tasks, activities, decisions, memory, reports, approvals. |
| sdk-agent | agent run lifecycle, context requests, work logs, evidence, token reporting. |
| sdk-adapter | connector registration, capability declaration, payload mapping, health reporting. |
| sdk-admin | domain packs, feature profiles, rule suggestions, audit, governance. |
| sdk-test | mock transport, fixtures, fake agents, fake connectors, live-test helpers. |
| sdk-browser | browser-safe API client with session-aware auth and UI feature visibility. |
| sdk-cli-support | CLI config, output, diagnostics, and command helpers. |

Each package should publish a clear public API. Internal generated modules should be hidden behind stable facade classes unless direct generated access is explicitly supported.

## Repository Layout

```text
packages/
  contracts/
    openapi/
    events/
    config/
    examples/
  sdk/
    typescript/
      generated/
      core/
      project/
      agent/
      adapter/
      admin/
      test/
      browser/
      examples/
    python/
      generated/
      astloom_core/
      astloom_project/
      astloom_agent/
      astloom_adapter/
      astloom_admin/
      astloom_test/
      examples/
  sdk-tools/
    generators/
    compatibility-checker/
    example-runner/
    release-notes/
```

Generated code should be reproducible from committed schemas and generator versions. Generated files should include schema version, generator version, and build metadata according to the reproducibility policy.

## Contract Generation Pipeline

The SDK generation pipeline should run in CI and locally.

1. validate source contracts.
2. check contract compatibility.
3. generate low-level clients.
4. generate typed models.
5. format generated code.
6. run compile and type checks.
7. run example validation.
8. run mock transport tests.
9. run consumer compatibility tests.
10. publish artifacts only after release approval.

Generated SDKs must not be manually edited. Custom behavior belongs in facade packages or generator templates.

## Public Facade Design

Generated clients are often too mechanical for application developers. Astloom should expose stable facade classes:

- AstloomClient.
- WorkspaceClient.
- ProjectClient.
- AgentRunClient.
- AdapterRegistrationClient.
- RuleSuggestionClient.
- FeatureProfileClient.
- TestFixtureClient.

Facade responsibilities:

- require scope.
- validate user intent.
- attach correlation IDs.
- create idempotency keys for safe workflows.
- map generated errors into SDK errors.
- provide pagination helpers.
- expose workflow methods.
- hide internal endpoint details.

## Scope Enforcement In SDK

The SDK should make unsafe unscoped calls difficult.

```typescript
const client = Astloom.createClient({ endpoint, auth });
const workspace = client.forWorkspace("workspace-main");
const project = workspace.forProject("backend-api");
await project.workLogs.record({ summary: "Implemented SDK docs" });
```

A method that mutates project data should not be available on an unscoped root client. Root clients may expose discovery, authentication, and organization-level admin operations only.

## Idempotency Design

SDK commands should support idempotency.

- SDK should accept caller-provided idempotency keys.
- SDK may generate keys for workflow helpers when safe.
- generated keys should be deterministic only when the workflow requires repeatability.
- retries should require idempotency for mutating commands.
- idempotency conflicts should map to AstloomConflictError.

## Retry And Timeout Policy

Retryable:

- transient network failures.
- rate limits with retry-after.
- service unavailable.
- gateway timeout.
- event subscription reconnect.

Not retryable by default:

- validation errors.
- authorization errors.
- policy denied errors.
- approval required errors.
- non-idempotent mutation without idempotency key.

Timeouts should be configurable per client and per request.

## Error Mapping

| Platform Category | SDK Error |
| --- | --- |
| validation_error | AstloomValidationError |
| authentication_error | AstloomAuthenticationError |
| authorization_error | AstloomAuthorizationError |
| conflict_error | AstloomConflictError |
| not_found_error | AstloomNotFoundError |
| policy_error | AstloomPolicyError |
| approval_required | AstloomApprovalRequiredError |
| rate_limit_error | AstloomRateLimitError |
| dependency_error | AstloomDependencyError |
| internal_error | AstloomInternalError |

Errors must preserve correlation_id and documentation_ref.

## Event Subscription Engineering

SDK event subscriptions should be resilient and scoped.

Requirements:

- subscribe by workspace, project, project group, agent, connector, or event type.
- enforce authorization server-side.
- reconnect with backoff.
- resume with IDE when supported.
- expose dead-letter or skipped event metadata.
- validate event schema before invoking handlers.
- allow test transports to inject events.

## Adapter SDK Engineering

Adapter SDKs should include a harness for building connectors.

Harness responsibilities:

- config schema validation.
- capability declaration validation.
- secret reference validation.
- health endpoint implementation helper.
- webhook verification helper.
- provider payload fixture runner.
- mapping test runner.
- local adapter simulator.

Adapter SDKs should keep provider-specific behavior in adapter packages, not in core services.

## Agent SDK Engineering

Agent SDKs should provide an AgentRun abstraction.

AgentRun responsibilities:

- start and finish run.
- report status.
- request scoped context.
- record work log.
- create decision.
- create issue.
- request approval.
- attach evidence.
- report token usage.
- submit final artifact.

The AgentRun object should cache run-level identifiers and automatically attach them to calls.

## Admin SDK Engineering

Admin SDK methods must be privileged and auditable.

Admin capabilities:

- domain pack management.
- feature profile management.
- rule suggestion review.
- rule version activation and rollback.
- project isolation management.
- connector governance.
- report configuration.
- audit retrieval.

Admin SDK calls should return explanation metadata for denied or approval-gated actions.

## Test SDK Engineering

The Test SDK should make SDK testing cheap and repeatable.

Test SDK features:

- mock transport.
- fake auth provider.
- contract fixture loader.
- project fixture builder.
- event fixture emitter.
- fake agent run.
- fake adapter registration.
- live environment guardrails.
- cleanup helpers.

Live test helpers must require explicit environment markers so tests do not accidentally run against production.

## CI Requirements

CI should run:

- schema validation.
- SDK generation reproducibility check.
- TypeScript type check.
- Python type check where applicable.
- linting.
- unit tests.
- contract tests.
- mock transport tests.
- example compile or run tests.
- package build tests.
- compatibility matrix tests.

CI should fail when docs examples drift from SDK behavior.

## Release Governance

SDK releases should include:

- version number.
- supported API versions.
- supported event versions.
- supported config schema versions.
- migration notes.
- deprecation notes.
- generated client checksum or build metadata.
- changelog.
- compatibility test result.

Breaking changes require a deprecation window unless the current version is explicitly pre-stable.

## Security Requirements

- never log tokens.
- never log raw secrets.
- redact provider payloads by default.
- expose secure secret references, not secret values.
- avoid writing credentials to generated examples.
- support token refresh without exposing refresh tokens to application logs.
- enforce TLS for remote endpoints except explicit local development profiles.
- expose audit-safe diagnostics.

## Developer Experience Requirements

Required developer experience assets:

- quickstart.
- authentication guide.
- project-scoped client guide.
- agent integration guide.
- adapter integration guide.
- admin automation guide.
- test fixture guide.
- error handling guide.
- version compatibility table.
- runnable examples.

## Acceptance Criteria

SDK engineering is acceptable when:

- SDK packages are generated or validated from public contracts.
- SDK public facades are stable and use-case oriented.
- SDKs are scoped by default and preserve project isolation.
- SDKs support idempotency, retries, typed errors, correlation IDs, and audit-safe logging.
- TypeScript and Python SDKs have examples, tests, and release metadata.
- adapter, agent, admin, and test SDK surfaces are separated by package or namespace.
- CI proves generation reproducibility and example validity.
- SDK releases clearly state compatibility with API, event, and config contract versions.
