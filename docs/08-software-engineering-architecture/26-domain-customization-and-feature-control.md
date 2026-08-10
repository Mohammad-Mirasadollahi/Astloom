---
doc_id: as.doc.sea.domain-customization-and-feature-control
title: 26 - Domain Customization And Feature Control
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom must be modular enough to serve different operational domains while keeping
  software engineering as the primary product focus. The platform should work as a deeply
  technical coding and documentation copilot for engineering teams, but it should also support
  domain-specif.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/26-domain-customization-and-feature-control.md
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

# 26 - Domain Customization And Feature Control

## Purpose

Astloom must be modular enough to serve different operational domains while keeping software engineering as the primary product focus. The platform should work as a deeply technical coding and documentation copilot for engineering teams, but it should also support domain-specific usage by teams such as HR, operations, security, support, product management, compliance, or internal enablement.

This does not mean every domain receives a separate product. Astloom should expose one core platform with domain packs, rule packs, feature profiles, capability gates, and administrative controls. A user or organization can shape the platform behavior without hard-coding workflows into the core services.

## Design Goals

The customization architecture must satisfy the following goals:

- keep coding, documentation, architecture, code review, code graph, memory, and agent orchestration as the primary first-class workflow.
- allow non-engineering teams to use the platform through domain-specific profiles without seeing irrelevant technical features.
- allow each project, team, or workspace to define its own rules, terminology, approval policies, memory behavior, enabled features, UI surfaces, and automation limits.
- avoid hard-coded behavior in services, prompts, scoring, rule selection, UI navigation, and agent workflows.
- make feature enablement explicit, auditable, reversible, and testable.
- allow the system to suggest rules and profiles based on repeated user conversations, observed corrections, workflow patterns, risk events, and missing guidance.
- keep all customizations scoped so one project or domain cannot accidentally inherit another domain's data, rules, memory, or UI behavior.

## Core Concept

Astloom should separate platform capability from domain activation.

Platform capability is what the system can technically do. Domain activation is what a specific workspace, project, team, or user is allowed to see and use.

Example:

- The platform can perform code review, memory retrieval, document synchronization, task routing, approval escalation, and reporting.
- A software engineering workspace may enable code graph, code review, architecture documentation, CI insights, developer rules, token reporting, and live test workflows.
- An HR workspace may disable code graph and code review while enabling policy Q&A, onboarding workflows, document memory, approval tasks, conversation summaries, and rule suggestions.
- A mixed project group may enable engineering features for backend and frontend projects while exposing simplified workflow dashboards to product or HR stakeholders.

## Domain Pack Model

A domain pack is a versioned configuration package that defines how Astloom behaves for a domain or team type.

A domain pack should include:

- domain identifier.
- display name.
- target audience.
- enabled feature profile.
- default rule packs.
- default memory profile.
- default UI navigation profile.
- default task types.
- default approval policies.
- domain vocabulary.
- suggested prompt templates.
- connector requirements.
- reporting templates.
- security and privacy constraints.
- examples and acceptance tests.

Example domain packs:

| Domain Pack | Primary Users | Enabled Focus |
| --- | --- | --- |
| software-engineering | developers, architects, tech leads | code graph, code generation, code review, docs-as-code, architecture rules, tests, CI/CD, token reporting |
| hr-operations | HR specialists, people operations | onboarding tasks, policy memory, approval workflows, employee-document Q&A, feedback capture, task tracking |
| product-design | product managers, product designers | requirement analysis, decision records, user workflow mapping, feature specs, acceptance criteria |
| security-compliance | security reviewers, compliance owners | policy checks, risk scoring, escalation, evidence packages, audit reporting |
| support-operations | support teams, customer operations | knowledge base memory, incident summaries, ticket routing, repeated question scoring |

## Feature Profile Model

A feature profile controls which capabilities are visible, enabled, hidden, disabled, or approval-gated for a scope.

Feature profile states:

| State | Meaning |
| --- | --- |
| enabled | feature is visible and usable. |
| disabled | feature is unavailable and must not run. |
| hidden | feature is not shown in UI but may be available to administrators. |
| read_only | feature data can be viewed but not modified. |
| approval_required | feature can run only after an approval policy passes. |
| shadow_mode | feature evaluates and reports results without changing state. |
| admin_only | feature is available only to privileged operators. |

Feature profile scopes:

- organization.
- workspace.
- project.
- project group.
- team.
- role.
- user.
- agent.
- connector.
- environment.

Resolution must be deterministic. The system should calculate an effective feature profile from the configured scopes and produce an explanation for why a feature is enabled, disabled, hidden, or approval-gated.

## Suggested Feature Taxonomy

Astloom should define a stable feature taxonomy so product, UI, backend, policy, and reporting systems speak the same language.

Suggested top-level feature groups:

- code_intelligence.
- code_generation.
- code_review.
- docs_as_code.
- memory_and_context.
- rule_engine.
- task_management.
- approval_workflows.
- agent_orchestration.
- connector_management.
- admin_console.
- reporting.
- live_testing.
- unit_testing.
- project_composition.
- impact_analysis.
- knowledge_base.
- conversation_analysis.
- rule_suggestion.

Each feature should have a stable feature key, owner, description, default state, risk level, dependencies, UI entry points, API permissions, events, metrics, and tests.

## Modular Architecture Requirements

The core platform should not directly encode domain behavior. Instead, domain-specific behavior should be loaded through contracts and configuration.

Required modules:

| Module | Responsibility |
| --- | --- |
| domain-profile-service | stores domain packs, feature profiles, UI profiles, and effective profile calculations. |
| rule-engine-service | evaluates deterministic and semantic rules, including user-authored and suggested rules. |
| memory-service | applies domain-specific memory weighting, retrieval profiles, and conversation-derived knowledge. |
| admin-console | exposes profile, rule, feature, task, and feedback management. |
| agent-orchestrator | selects agents and workflows based on effective domain and feature profile. |
| adapter-service | connects domain-specific resources without changing core services. |
| reporting-service | compares enabled capabilities, outcomes, and usage by domain/profile/project. |
| audit-service | records profile changes, feature state changes, rule suggestions, and user approvals. |

Dependency direction must flow from core contracts to domain packs. Domain packs may depend on platform contracts, but platform services must not depend on a specific domain pack.

## User-Defined Rules

Users should be able to define their own rules without changing source code.

Rule types:

- deterministic validation rule.
- natural-language semantic rule.
- approval rule.
- memory retrieval rule.
- documentation rule.
- code review rule.
- task routing rule.
- UI visibility rule.
- connector usage rule.
- reporting rule.

Rule authoring should support:

- natural-language description.
- structured condition builder.
- scope selection.
- severity selection.
- examples and counterexamples.
- test cases.
- dry-run mode.
- approval workflow.
- versioning.
- rollback.
- audit trail.

## Rule Suggestions From Conversation

Astloom should observe user conversations, corrections, repeated requests, rejected outputs, approval decisions, and manually applied fixes. Based on those signals, it should propose rules that would prevent repeated friction.

Examples:

- If a developer repeatedly says that all documentation must be English, suggest a documentation-language rule scoped to that project.
- If a team repeatedly disables advanced engineering features for HR users, suggest an HR feature profile.
- If reviewers repeatedly reject direct database access from UI modules, suggest an architecture rule.
- If a project frequently asks for code review after a batch of changes, suggest a deferred review rule.
- If users repeatedly correct terminology, suggest a domain vocabulary entry.

A suggested rule must not become active automatically unless the workspace policy allows automatic low-risk rule adoption. The default behavior should be proposal first, human review second, activation third.

For **explicit** business and process definition (not only passive chat mining), see `../04-rule-engine-orchestration/07-custom-rule-authoring-and-suggestion-workflows.md` — Guided Business And Process Intake Mode, Challenge Catalog, and LLM-Managed Rule Authoring.

## Feature Hiding For Non-Engineering Users

Non-engineering users should not have to navigate the full engineering platform.

The admin console should support UI profile controls such as:

- hide code graph navigation.
- hide code review workflows.
- hide CI/CD and release views.
- hide token optimization internals.
- hide parser and AST terminology.
- show simplified task queues.
- show knowledge base search.
- show approval inbox.
- show conversation feedback.
- show domain-specific reports.

Hidden features must still be enforced by backend permissions and feature gates. UI hiding is not a security boundary.

## Effective Profile Calculation

When a user or agent starts a workflow, the system should compute an effective runtime profile.

Inputs:

- organization profile.
- workspace profile.
- project profile.
- project group profile.
- user role.
- user-specific overrides.
- agent capability profile.
- environment.
- active domain pack.
- connector availability.
- current task type.
- risk level.

Output:

- enabled feature map.
- disabled feature map.
- visible UI surface map.
- active rule packs.
- active memory profile.
- approval requirements.
- allowed agent actions.
- reporting dimensions.
- explanation metadata.

The explanation metadata should answer: which profile made this decision, which override applied, which rule was selected, and what the user can change to modify behavior.

## Configuration Contract Example

The final implementation should use a validated schema. Normative schemas, conflict precedence, and activation workflow: `../04-rule-engine-orchestration/08-domain-pack-feature-profile-and-rule-suggestion-schemas.md`. A conceptual example:

```yaml
domain_pack: software-engineering
scope:
  workspace_id: workspace-main
  project_id: backend-api
features:
  code_intelligence: enabled
  code_review: approval_required
  docs_as_code: enabled
  hr_policy_workflows: hidden
memory_profile: engineering-default
rule_packs:
  - secure-coding-baseline
  - architecture-boundary-rules
  - documentation-english-only
ui_profile:
  navigation:
    code_graph: enabled
    approval_inbox: enabled
    hr_onboarding: hidden
suggestions:
  rule_suggestions: enabled
  auto_activate_low_risk_rules: disabled
```

## Product Experience Requirements

The customization experience should be professional and operator-friendly.

Required screens:

- domain pack library.
- feature profile editor.
- rule pack editor.
- suggested rules inbox.
- rule dry-run review.
- profile diff viewer.
- effective profile debugger.
- user and role assignment screen.
- project scope assignment screen.
- audit log for profile and rule changes.

Required interaction states:

- draft.
- dry-run.
- pending approval.
- active.
- shadow mode.
- deprecated.
- rolled back.
- failed validation.

## Engineering Acceptance Criteria

This design is acceptable when:

- all user-visible and agent-executable capabilities are controlled by feature profiles.
- custom rules can be authored without source code changes.
- domain packs can configure behavior for software engineering and non-engineering teams.
- the software engineering domain remains the primary and most complete first-party domain pack.
- non-engineering users can receive simplified UI profiles without weakening backend authorization.
- conversation-derived rule suggestions are proposed with evidence, scope, confidence, risk, and test examples.
- effective profile calculation is deterministic, explainable, auditable, and testable.
- project isolation rules prevent accidental sharing of profiles, rules, memories, and reports across unrelated projects.
