---
doc_id: as.doc.interop.sdk-and-developer-platform
title: 07 - SDK And Developer Platform
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom must provide a first-class SDK layer. The SDK is not a convenience wrapper
  around HTTP endpoints. It is the supported developer interface for agents, adapters, IDE
  integrations, automation scripts, admin tools, test harnesses, and external systems that
  need to interact .
tags:
- standard
- interop
phase: 05-interoperability-ecosystem
canonical_path: docs/05-interoperability-ecosystem/07-sdk-and-developer-platform.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
placeholder: 1
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 07 - SDK And Developer Platform

## 07 - SDK And Developer Platform
## Purpose

Astloom must provide a first-class SDK layer. The SDK is not a convenience wrapper around HTTP endpoints. It is the supported developer interface for agents, adapters, IDE integrations, automation scripts, admin tools, test harnesses, and external systems that need to interact with Astloom safely.

The SDK should make correct integration easier than direct API usage. It should enforce contracts, propagate tenant and project scope, preserve audit evidence, support idempotency, expose typed errors, and prevent accidental bypass of rules, feature profiles, memory boundaries, and approval gates.

## SDK Goals

- provide a stable integration surface for internal services, external agents, IDE plugins, CLI tools, admin applications, and customer automations.
- keep Astloom modular by preventing consumers from importing service internals.
- expose typed commands, queries, events, and workflow helpers generated from public contracts where possible.
- make project isolation and domain profile boundaries default behavior.
- support software engineering workflows as the richest first-party use case.
- support custom domain packs such as HR, product, security, support, and operations through configuration-aware clients.
- provide test fakes, local simulators, and contract fixtures so integrations can be built without a full production deployment.
- support SDK-level observability, retries, idempotency, correlation IDs, and structured error handling.
- avoid hard-coded provider assumptions, hard-coded ports, hard-coded project IDs, tenant IDs, feature flags, model providers, or connector credentials.

## SDK Families

| SDK Family | Primary Users | Purpose |
| --- | --- | --- |
| Core SDK | platform services, internal apps, trusted automation | typed access to tasks, activities, decisions, memory, rules, projects, reports, and approvals. |
| Agent SDK | AI agents, coding agents, automation agents | report actions, request scoped context, create work logs, publish progress, receive tasks, submit evidence. |
| Adapter SDK | external tool adapters, IDE plugins, CI connectors, ticket connectors | implement connector lifecycle, capability declaration, mapping, validation, health, and callbacks. |
| Admin SDK | admin console, operator tools, governance workflows | manage feature profiles, domain packs, rules, projects, agents, connectors, audits, and reports. |
| Test SDK | integration tests, live tests, fixture runners | create test tenants, seed projects, simulate events, assert audit records, run contract tests. |
| Browser SDK | web interface, embedded admin panels | call safe UI-facing APIs with session-aware auth and feature visibility filtering. |
| CLI SDK | command-line tools and scripts | share auth, config loading, output formatting, idempotency, and diagnostics. |

The first implementation should prioritize TypeScript and Python because Astloom needs web/admin tooling, Node-based IDE integrations, Python automation, and AI workflow integration. Additional languages should be generated from contracts after the contract surface stabilizes.

## SDK Layering

SDKs should be layered so low-level generated clients do not leak directly into application code.

1. Generated contract clients.
2. Transport and authentication layer.
3. Typed domain clients.
4. Workflow helpers.
5. Test fakes and simulators.
6. Examples and templates.

Generated clients know schemas and transport. Domain clients expose use-case oriented methods. Workflow helpers combine multiple calls into safe flows such as creating an agent work session, recording a batched code review, requesting approval, or submitting a connector health report.

## Public Concepts

SDKs should expose public platform concepts only:

- Organization.
- Workspace.
- Project.
- ProjectGroup.
- Actor.
- Agent.
- Connector.
- Activity.
- WorkLog.
- Decision.
- Issue.
- Task.
- MemoryItem.
- Rule.
- RuleEvaluation.
- FeatureProfile.
- DomainPack.
- ApprovalTicket.
- Report.
- AuditEvent.
- CapabilityDeclaration.
- EventEnvelope.

SDKs must not expose database tables, ORM models, private service classes, internal queue names, raw prompts, unfiltered provider payloads, internal vector IDs, or internal graph storage implementation details.

## Scope And Isolation Defaults

Every SDK call should require or derive scope.

Required scope fields:

- organization_id.
- workspace_id.
- project_id or project_group_id when the action is project-related.
- actor_ref.
- correlation_id.

The SDK should make scope explicit through scoped clients.

```typescript
const client = Astloom.createClient({ auth, endpoint });
const project = client.forProject({ workspaceId: "workspace-main", projectId: "backend-api" });
await project.tasks.create({ title: "Review auth flow", reason: "Security-sensitive change" });
```

```python
client = AstloomClient(auth=auth, endpoint=endpoint)
project = client.for_project(workspace_id="workspace-main", project_id="backend-api")
project.tasks.create(title="Review auth flow", reason="Security-sensitive change")
```

A client should not silently reuse a different project scope. Cross-project composition must use an explicit project group or composition context.

## Authentication And Authorization

SDK authentication should support:

- user session tokens.
- service account tokens.
- agent identity tokens.
- connector credentials.
- short-lived delegated tokens.
- local development tokens.
- test tokens for isolated test environments.

Authorization is enforced server-side, but SDKs should expose capability discovery so clients can adapt UI and workflows before making invalid calls.

Capability discovery should answer:

- which features are enabled for this scope.
- which rules apply.
- which actions require approval.
- which connectors are available.
- which SDK methods are not available in this profile.
- which domain pack is active.

## Configuration Loading

SDK configuration should be explicit and environment-aware.

Configuration sources, in precedence order:

1. explicit constructor options.
2. workspace-local config file.
3. environment variables.
4. user profile config.
5. generated bootstrap config.

Suggested environment variables:

- ASTLOOM_ENDPOINT.
- ASTLOOM_TOKEN.
- ASTLOOM_WORKSPACE_ID.
- ASTLOOM_PROJECT_ID.
- ASTLOOM_PROFILE.
- ASTLOOM_TIMEOUT_MS.
- ASTLOOM_LOG_LEVEL.

The SDK must not hard-code local ports, cloud endpoints, tokens, project IDs, tenant IDs, feature flags, model providers, or connector credentials.

## Transport Requirements

SDKs should support HTTP APIs and event subscriptions.

Transport requirements:

- request timeout.
- retry policy for safe retryable failures.
- idempotency keys for retryable commands.
- correlation ID propagation.
- structured errors.
- pagination helpers.
- streaming or long-polling where needed.
- event subscription reconnect.
- backoff and rate-limit handling.
- audit-safe logging.
- local mock transport for tests.

The SDK should not retry non-idempotent commands unless an idempotency key is present.

## Command, Query, And Event Model

Commands mutate state:

- record_activity.
- create_task.
- create_decision.
- request_approval.
- submit_rule_suggestion.
- register_connector.
- publish_agent_status.

Queries read state:

- get_task.
- list_project_memory.
- explain_effective_profile.
- get_rule_evaluation.
- list_reports.
- search_code_graph.

Events subscribe to facts:

- ActivityRecorded.
- TaskCreated.
- RuleViolationDetected.
- MemoryConsolidated.
- ConnectorHealthChanged.
- ApprovalTicketResolved.

SDK naming should follow each language's conventions while preserving contract identity in metadata.

## Agent SDK Requirements

The Agent SDK should make agents safe participants in Astloom.

Required capabilities:

- start an agent run.
- declare current task and intent.
- request scoped context.
- report tool usage.
- record work log entries.
- create decisions and issues.
- publish progress events.
- request human approval.
- attach evidence.
- submit output artifacts.
- report token usage.
- end run with status.

Agent SDK calls should automatically attach agent identity, run ID, task ID, project scope, correlation ID, model metadata when available, token usage when available, and source evidence references.

```python
run = project.agents.start_run(agent_id="coding-agent", task_id="TASK-123")
context = run.context.request(goal="implement auth docs", max_tokens=6000)
run.worklog.record(
    summary="Updated SDK documentation",
    evidence=["docs/05-interoperability-ecosystem/07-sdk-and-developer-platform.md"],
)
run.finish(status="completed")
```

## Adapter SDK Requirements

The Adapter SDK should help external systems connect without leaking provider-specific behavior into core services.

Adapter SDK responsibilities:

- declare capabilities.
- validate adapter configuration.
- register connector instance.
- map external payloads to Astloom contracts.
- map Astloom commands to external provider actions.
- handle provider retries, rate limits, and pagination.
- report health and diagnostics.
- normalize provider errors.
- preserve external reference IDs.
- avoid storing secrets in source-controlled files.

```yaml
adapter_id: jira-cloud
adapter_version: 1.0.0
capabilities:
  - can_create_external_ticket
  - can_update_external_ticket_status
  - can_receive_webhook
required_permissions:
  - ticket.write
  - ticket.read
contract_versions:
  task: 1.x
  webhook: 1.x
health:
  endpoint: /health/jira-cloud
```

## Admin SDK Requirements

The Admin SDK should power governance and operations.

Required capabilities:

- create and update domain packs.
- create and update feature profiles.
- explain effective profiles.
- manage rule drafts and rule versions.
- review suggested rules.
- manage connector registrations.
- manage project isolation and composition.
- retrieve audit events.
- generate impact reports.
- run diagnostics.

Admin SDK methods must enforce privileged authorization and return explanations for denied actions.

## Test SDK Requirements

The Test SDK should make contract tests and live tests practical.

Required capabilities:

- create isolated test organizations, workspaces, and projects.
- seed contracts, rules, memory, and tasks.
- create fake agents and connectors.
- run SDK methods against mock transport.
- run SDK methods against live test environments.
- assert events, audit logs, rule evaluations, and reports.
- clean up test data.

Live test helpers must require explicit environment markers so tests do not accidentally run against production.

## Error Handling

SDK errors should be typed and structured.

Error classes:

- AstloomValidationError.
- AstloomAuthenticationError.
- AstloomAuthorizationError.
- AstloomConflictError.
- AstloomNotFoundError.
- AstloomPolicyError.
- AstloomApprovalRequiredError.
- AstloomRateLimitError.
- AstloomDependencyError.
- AstloomInternalError.

Every SDK error should expose error_code, message, category, retryable, correlation_id, details, and documentation_ref.

## Observability

SDKs should provide observability hooks:

- before_request.
- after_response.
- on_retry.
- on_error.
- on_event_received.
- on_rate_limit.
- on_approval_required.
- on_policy_denied.

SDK logs must be audit-safe and redact sensitive data before logging.

## Versioning And Compatibility

SDK versions must map to supported API, event, and config contract versions.

Rules:

- SDK major version changes only when public behavior breaks.
- SDK minor version may add new optional methods or fields.
- SDK patch version fixes bugs without changing public behavior.
- SDK release notes must include supported contract versions.
- deprecated methods should emit warnings before removal.
- generated clients must include schema version metadata.
- compatibility tests must run against supported API versions.

## Packaging

Recommended initial packages:

```text
packages/
  sdk/
    typescript/
      core/
      agent/
      adapter/
      admin/
      test/
    python/
      astloom_core/
      astloom_agent/
      astloom_adapter/
      astloom_admin/
      astloom_test/
```

Package names should be stable and language-appropriate. Internal generated clients may live under a generated namespace, while public domain clients should remain stable facade classes.

## Related Documents

- Continued in `docs/05-interoperability-ecosystem/07-sdk-and-developer-platform-continued.md`
