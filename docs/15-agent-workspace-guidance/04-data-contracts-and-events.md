---
doc_id: as.doc.awg.data-contracts
title: 04 - Agent Workspace Guidance Data Contracts And Events
doc_type: contract
status: active
schema_version: '1.0'
owner: platform-architecture
summary: Bundle DTOs, MCP tool contracts for resolve/list/get-skill, export records, events,
  and compatibility rules for Agent Workspace Guidance.
tags:
- agent-workspace-guidance
- contracts
- mcp
- events
phase: 15-agent-workspace-guidance
canonical_path: docs/15-agent-workspace-guidance/04-data-contracts-and-events.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.awg.low-level-design
- as.doc.common_context.data-contracts
- as.doc.sea.usage-profile-cursor-mcp
doc_version: 1.0.1
audience:
- engineer
- architect
- agent
primary_entities:
- AgentWorkspaceGuidanceBundle
- GuidanceSkillDescriptor
- GuidanceExportResult
relations_declared:
- type: depends_on
  target: as.doc.awg.low-level-design
- type: complements
  target: as.doc.common_context.data-contracts
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 04 - Agent Workspace Guidance Data Contracts And Events

## Purpose

This document defines public contracts for Agent Workspace Guidance bundles, MCP tools, export results, and events. Field-level entity rules live in the low-level design; Common Context generic item contracts remain authoritative for storage.

## Contract Families

Publish under a versioned contracts package (design target: `backend/packages/common-context/contracts` with an `awg` namespace, or a thin `agent-workspace-guidance` contracts module that depends on Common Context types).

| Contract | Role |
| --- | --- |
| `GuidanceResolveRequest` | Scope + task fingerprint + budgets + agent type |
| `AgentWorkspaceGuidanceBundle` | Resolve response |
| `GuidanceSkillDescriptor` | Catalog entry |
| `GuidanceSkillBody` | Get-skill response |
| `GuidanceExportRequest` | Layout profile + dry_run + force flags |
| `GuidanceExportResult` | Written / skipped / conflicts |
| `GuidanceConflict` | Precedence or disk conflict |
| `GuidanceAuditRecord` | Resolve/export evidence pointer |

## Bundle DTO Sketch

```json
{
  "bundle_id": "bnd_01HZX...",
  "project_id": "prj_123",
  "user_id": "user_42",
  "layers_considered": ["org", "project", "user"],
  "resolved_at": "2026-07-20T05:30:00Z",
  "agents_entry": {
    "item_id": "cci_entry_1",
    "version": 3,
    "title": "Agent entry",
    "body": "# Agent entry\n\n**Law:** ...\n",
    "layer": "project",
    "token_estimate": 420
  },
  "always_rules": [
    {
      "item_id": "cci_rule_1",
      "version": 2,
      "title": "Reply language law",
      "body": "...",
      "slug": "reply-language",
      "priority": 100,
      "mandatory": true,
      "layer": "org",
      "reason_code": "applicability_match",
      "token_estimate": 180
    }
  ],
  "skills": [
    {
      "item_id": "cci_skill_1",
      "name": "api-contract-check",
      "description": "Validate public API changes against naming and DTO standards.",
      "version": 1,
      "when_to_use": ["openapi", "dto", "rest"],
      "layer": "user",
      "reason_code": "catalog_match"
    }
  ],
  "suppressed_items": [
    {
      "item_id": "cci_rule_9",
      "reason_code": "budget_exceeded"
    }
  ],
  "conflicts": [],
  "token_estimate": 600,
  "audit_record_id": "aud_77",
  "empty_reason": null
}
```

When no approved guidance exists, `agents_entry` is null, arrays are empty, and `empty_reason` is set (for example `no_approved_guidance`).

## MCP Tool Contracts

Tools are advertised only when present on the active Usage Profile MCP tool list.

### astloom_guidance_resolve

| Field | Value |
| --- | --- |
| `name` | `astloom_guidance_resolve` |
| `maps_to` | `guidance.resolve` |
| Purpose | Return the authoritative workspace guidance bundle for the scoped project |

Input (JSON Schema intent):

| Property | Type | Required | Notes |
| --- | --- | --- | --- |
| `task_summary` | string | no | Helps applicability / scoring |
| `workflow_type` | string | no | e.g. `coding` |
| `include_skill_bodies` | boolean | no | Default `false`; prefer catalog + get-skill |
| `budget_overrides` | object | no | Optional slice overrides |
| `user_id` | string | no | User-layer overlay; MCP gateway supplies actor when available |
| `task_overrides` | object | no | Optional `suppress_rule_slugs` / `suppress_skill_names` lists (highest precedence; mandatory rules blocked with conflict) |

Output: `AgentWorkspaceGuidanceBundle`.

Propose/write payloads may include `scope_kind` (`org` \| `project` \| `user`) and, for user layer, `user_id` (defaults to `X-Actor-Id`).

### astloom_guidance_list_skills

| Field | Value |
| --- | --- |
| `name` | `astloom_guidance_list_skills` |
| `maps_to` | `guidance.list_skills` |
| Purpose | Refresh skill catalog without re-sending always-on rule bodies |

Input: optional `query` string. Output: `{ "skills": GuidanceSkillDescriptor[] }`.

### astloom_guidance_get_skill

| Field | Value |
| --- | --- |
| `name` | `astloom_guidance_get_skill` |
| `maps_to` | `guidance.get_skill` |
| Purpose | Fetch one skill body by id or name |

Input:

| Property | Type | Required |
| --- | --- | --- |
| `skill_id` | string | one of id/name |
| `name` | string | one of id/name |
| `bundle_id` | string | no; correlation |

Output: `GuidanceSkillBody` (`item_id`, `name`, `version`, `body`, `content_hash`).

Unknown or out-of-scope skills fail closed with a typed error (no invented body).

## HTTP / Service API (Design)

Complementary admin/agent APIs (names indicative):

- `POST /projects/{project_id}/guidance/resolve`
- `GET /projects/{project_id}/guidance/skills`
- `GET /projects/{project_id}/guidance/skills/{skill_id}`
- `POST /projects/{project_id}/guidance/export`

Authorization follows project RBAC. MCP handlers must use env scope and must not accept cross-tenant `project_id` overrides unless the caller is an internal trusted service.

## Export Result Sketch

```json
{
  "export_id": "exp_01HZY...",
  "layout": "cursor",
  "dry_run": true,
  "written": [],
  "skipped": [],
  "conflicts": [
    {
      "path": ".cursor/rules/reply-language.mdc",
      "reason_code": "unmanaged_local_edit",
      "item_id": "cci_rule_1"
    }
  ],
  "audit_record_id": "aud_88"
}
```

## Event Names

- `AgentWorkspaceGuidanceBundleResolved`
- `AgentWorkspaceGuidanceSkillFetched`
- `AgentWorkspaceGuidanceExported`
- `AgentWorkspaceGuidanceExportConflictDetected`

Typed item lifecycle continues to emit Common Context events (`CommonItemApproved`, …) with `item_type` set to the guidance kind.

## Event Metadata

Every AWG event must include: `event_id`, `event_type`, `event_version`, `occurred_at`, `actor_id`, `tenant_id`, `workspace_id`, `project_id`, `correlation_id`, `causation_id`, `source_service`, `audit_record_id`. Resolve events also include `bundle_id` and counts by kind.

## Compatibility Rules

- Additive fields are preferred; removing or renaming fields requires a new contract version.
- MCP tool names are stable once shipped; behavior changes that break agents need a new tool name or explicit version field.
- Bundle `schema_version` must be present when the DTO evolves.
- SDK and Usage Profile catalog updates ship with contract changes.
- Contract tests must cover schema validation and fail-closed unknown skill behavior.

## Relationship To Common Context Contracts

`ContextBundleRequest` / `ContextBundleResponse` remain the general Common Context API. `GuidanceResolveRequest` may wrap or specialize that pipeline with kind filters and catalog mode. Implementations should avoid duplicating storage contracts; AWG DTOs are projections.

Platform seed skills and the `mcp-first-astloom` always-on rule (see [`06-mcp-first-agent-skills-and-rules.md`](06-mcp-first-agent-skills-and-rules.md)) reference the MCP tool names in this document and in the Usage Profile catalog. Adding a programming-profile MCP tool requires updating that seed catalog in the same change set.
