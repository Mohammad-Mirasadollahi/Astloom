---
doc_id: as.doc.sea.project-isolation-and-composition-architecture
title: 23 - Project Isolation And Composition Architecture
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom must support multiple independent projects inside one platform installation.
  Each project may have different domain concepts, repository structure, architecture style,
  rules, documentation model, memory, agents, connectors, reports, and operational workflows.
  By default.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/23-project-isolation-and-composition-architecture.md
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

# 23 - Project Isolation And Composition Architecture

## 23 - Project Isolation And Composition Architecture
## Purpose

Astloom must support multiple independent projects inside one platform installation. Each project may have different domain concepts, repository structure, architecture style, rules, documentation model, memory, agents, connectors, reports, and operational workflows. By default, each project must behave as a completely isolated context. Data must not be shared across projects at any layer unless an explicit, authorized composition policy allows it.

The system must also support controlled composition for related projects, such as frontend and backend repositories of one product. Composition must be deliberate, scoped, auditable, reversible, and limited to approved data types.

## Corrected Requirement

The raw user requirement can be formalized as follows:

Astloom must provide a strict multi-project isolation model. A user may have several projects with different concepts and structures. Each project must have an independent view of memory, code graph, documentation, tickets, rules, agents, reports, connectors, audit, and configuration. No project data should be shared at any level by default. If related projects need to be used together, such as frontend and backend of one product, the system must support an explicit ProjectGroup that defines exactly which data types can be composed, in which direction, for which actors, and under which approval and audit rules.

## Professional Audience

This document is written for:

- software engineers implementing scope enforcement, memory retrieval, graph queries, connector registration, report filters, and audit search.
- architects reviewing tenant, workspace, project, and ProjectGroup boundaries.
- product designers defining project switcher, active scope UX, composition policy UX, and cross-project warnings.
- security reviewers validating isolation, authorization, and cross-project access auditability.
- operators managing multi-project installations and support diagnostics.

## Goals

- Guarantee project isolation by default.
- Prevent accidental cross-project memory, graph, docs, tickets, reports, connector, and audit access.
- Apply scope before retrieval, ranking, graph traversal, report aggregation, or prompt assembly.
- Support controlled composition of related projects through ProjectGroup policies.
- Make all cross-project access visible, explainable, and auditable.
- Allow frontend/backend or multi-repository products to share only approved context.
- Keep project-specific concepts from contaminating unrelated project memory or FAQ.
- Preserve professional UX clarity by always showing active scope.

## Non-Goals

- No automatic project merging.
- No global shared memory for project-sensitive data.
- No cross-project retrieval based only on semantic similarity.
- No report aggregation across unrelated projects.
- No connector token that silently spans all projects.
- No agent access to another project without explicit scope permission.
- No ProjectGroup that bypasses tenant, workspace, or RBAC boundaries.

## Concept Model

Astloom should use the following hierarchy.

    Tenant
      Workspace
        Project
          Repository
          AgentRegistration
          ConnectorRegistration
          MemoryScope
          CodeGraphScope
          DocumentationScope
          RuleScope
          ReportScope
        ProjectGroup
          MemberProjects
          CompositionPolicy
          CrossProjectAccessAudit

Definitions:

- Tenant: highest security, billing, compliance, and data residency boundary.
- Workspace: organizational boundary inside a tenant.
- Project: isolated engineering and product context inside a workspace.
- Repository: source or documentation repository attached to exactly one project unless explicitly linked through ProjectGroup.
- ProjectGroup: explicit composition of multiple projects for a shared product or workflow.
- Scope: runtime boundary used by every query, mutation, retrieval, report, and UI view.
- CompositionPolicy: versioned policy defining what may be shared between ProjectGroup members.

## Isolation Dimensions

Isolation must apply across all data and operational layers.

| Dimension | Isolation Requirement |
| --- | --- |
| memory | project memory is default; cross-project memory requires policy |
| question memory | repeated questions are project-local unless promoted through policy |
| FAQ memory | project FAQ cannot become group or workspace FAQ without review |
| code graph | graph traversal starts inside project and cannot cross unless policy allows edges |
| documentation graph | anchors and docs metadata are project-scoped |
| tasks and tickets | Tasks, Issues, and external tickets belong to project or approved group |
| decisions | Decisions are project-scoped unless explicitly marked group-visible |
| rules | rule sets are project-scoped and can be inherited only by policy |
| connectors | connectors and credentials are scoped to project or approved group |
| agents | agent tokens carry allowed project or ProjectGroup scope |
| reports | reporting scope must be explicit and authorized |
| audit | audit search is scoped and cross-project access is recorded |
| configuration | runtime config and feature flags are project-scoped where behavior differs |
| automation jobs | automation jobs run inside project or explicit ProjectGroup scope |

## Scope Enforcement Rule

Scope must be applied before data selection.

Correct order:

1. identify actor and requested scope.
2. authorize actor for scope.
3. determine allowed projects and data types.
4. restrict candidate data sources.
5. retrieve or query only allowed candidates.
6. rank, aggregate, summarize, or generate output.
7. record audit event if cross-project access occurred.

Forbidden order:

1. retrieve broad data.
2. rank by semantic relevance.
3. filter unauthorized projects afterward.

Filtering after retrieval is not acceptable because it can leak information through ranking, summaries, logs, metrics, or prompt side effects.

## Data Contract Requirements

Every scoped record should include:

- tenant_id.
- workspace_id.
- project_id.
- project_group_id when created or queried in group context.
- scope_type.
- sensitivity_level.
- owner.
- created_by.
- created_at.
- access_policy_ref.

ProjectGroup records should include:

    ProjectGroup:
        group_id
        tenant_id
        workspace_id
        name
        purpose
        member_project_ids
        composition_policy_ref
        owner
        approval_status
        created_at
        updated_at

CompositionPolicy records should include:

    CompositionPolicy:
        policy_id
        group_id
        version
        allowed_data_types
        allowed_query_directions
        allowed_actors
        memory_policy
        graph_policy
        docs_policy
        task_policy
        report_policy
        connector_policy
        audit_policy
        expiration_policy
        approval_ref
        status

CrossProjectAccessAudit records should include:

    CrossProjectAccessAudit:
        access_id
        actor_ref
        source_project_id
        target_project_id
        project_group_id
        data_type
        operation
        policy_ref
        reason
        evidence_ref
        timestamp

## Project Composition Model

Project composition is allowed only through ProjectGroup.

Valid ProjectGroup examples:

- frontend and backend of one product.
- mobile app and backend API.
- SDK and platform API.
- documentation repository and implementation repository.
- infrastructure repository and application repository.
- service group participating in one release train.

A ProjectGroup does not merge projects. It creates a controlled view across member projects.

## Composition Policy Examples

Allowed composition examples:

- backend exposes public API contract docs to frontend.
- frontend exposes API usage traces to backend.
- shared report aggregates delivery metrics across approved member projects.
- code graph impact analysis can traverse CONTRACT_DEPENDS_ON edges.
- documentation drift can create Tasks in both frontend and backend when a shared contract changes.
- project group FAQ can store approved cross-project answers about shared API behavior.

Forbidden composition examples:

- frontend agent reads backend private memory without policy.
- backend report includes frontend task details without selected group scope.
- global FAQ stores project-specific authentication implementation details.
- connector token can create tickets across all projects by default.
- semantic search crosses projects because names look similar.

## Memory Isolation

Memory retrieval must be project-scoped by default.

Rules:

- MemoryItem belongs to one project unless created as approved ProjectGroup memory.
- SemanticFacts are project-local unless explicitly group-visible.
- QuestionMemory is project-local by default.
- FAQ memory is project-local by default.
- ProjectGroup memory can include only approved shared concepts.
- Workspace memory may store generic organizational rules only when sanitized.
- Global pattern memory must not contain project-sensitive data.

Memory retrieval must include a scope explanation:

- queried project memory only.
- included project group memory by policy.
- excluded unrelated project memory.
- omitted high-scoring result because scope denied access.

## Code Graph Isolation

Each project should have its own graph scope.

Graph node requirements:

- project_id is required on project-owned nodes.
- project_group_id is allowed only on approved cross-project relationship views.
- graph snapshot includes project scope.
- graph queries must begin from scoped roots.

Allowed cross-project edge types:

- API_CONSUMES.
- CONTRACT_DEPENDS_ON.
- DOCUMENTS_EXTERNAL_API.
- DEPLOYS_WITH.
- RELEASED_WITH.
- SHARES_OWNER.

Every cross-project edge must include:

- source_project_id.
- target_project_id.
- policy_ref.
- evidence_ref.
- created_at.

## Documentation Isolation

Documentation metadata must be project-scoped.

Rules:

- docs graph anchors belong to project scope.
- missing documentation tasks are created in the owning project.
- shared API documentation can be visible to ProjectGroup members only by policy.
- generated documentation must not include private implementation details from another project unless policy allows it.

## Task, Ticket, And Agent Isolation

Tasks and agents must carry scope.

Rules:

- a Task belongs to project or ProjectGroup scope.
- an Issue belongs to project or ProjectGroup scope.
- external tickets inherit scope from Astloom Task.
- agent registration declares allowed project_ids or project_group_ids.
- agent token must include scope claims.
- connector registration is project-scoped unless group-scoped by policy.
- creating cross-project tasks requires ProjectGroup permission.

## Reporting Isolation

Reports must declare scope before calculation.

A report should include:

- tenant.
- workspace.
- project or ProjectGroup.
- included projects.
- excluded projects.
- data types included.
- time range.
- baseline range.
- comparison method.
- permissions used.

Reports cannot aggregate multiple projects unless:

- a ProjectGroup exists.
- actor has permission for the group.
- report policy allows required data types.
- output shows included projects and caveats.

## Product Experience

The web interface should make active scope impossible to miss.

Required UX elements:

- workspace switcher.
- project switcher.
- ProjectGroup switcher.
- active scope banner.
- scoped search indicator.
- cross-project warning state.
- composition policy editor.
- ProjectGroup member list.
- cross-project access audit view.
- report scope selector.
- memory scope selector.
- connector scope selector.
- agent scope selector.

The UI should show different states:

- single_project_scope.
- project_group_scope.
- cross_project_access_requested.
- cross_project_access_denied.
- composition_policy_missing.
- composition_policy_expired.
- partial_group_visibility.

## Example: Frontend And Backend Composition

Initial state:

- frontend project owns UI and API client code.
- backend project owns API implementation and auth rules.
- both projects are isolated by default.

Composition setup:

1. workspace admin creates ProjectGroup ProductA.
2. frontend and backend are added as members.
3. policy allows sharing public API contracts, API usage graph edges, shared release Tasks, and approved group reports.
4. policy denies sharing private backend memory and private frontend implementation tasks.
5. cross-project graph edges are created only for API_CONSUMES and CONTRACT_DEPENDS_ON.

Runtime behavior:

- frontend agent can ask about backend public API contract.
- frontend agent cannot retrieve backend private auth implementation memory.
- backend agent can see frontend API usage impact through approved graph edges.
- group report can aggregate delivery metrics across both projects.
- every cross-project query creates CrossProjectAccessAudit.

## Related Documents

- Continued in `docs/08-software-engineering-architecture/23-project-isolation-and-composition-architecture-continued.md`
