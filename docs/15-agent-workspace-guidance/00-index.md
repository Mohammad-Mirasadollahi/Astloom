---
doc_id: as.doc.awg.index
title: 15 - Agent Workspace Guidance Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: 'Phase index for Agent Workspace Guidance: governed AGENTS entry, always-on rules,
  and on-demand skills (including MCP-first routing to Astloom tools) delivered primarily
  over MCP with optional filesystem export, stored as typed Common Context items.'
tags:
- agent-workspace-guidance
- skills
- rules
- agents-md
- mcp
- common-context
phase: 15-agent-workspace-guidance
canonical_path: docs/15-agent-workspace-guidance/00-index.md
lifecycle_lane: current
concern_lane: product
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.awg.feature-specification
- as.doc.awg.mcp-first-skills-rules
- as.doc.common_context.index
- as.doc.sea.usage-profile-cursor-mcp
doc_version: 1.0.2
audience:
- engineer
- architect
- product
- agent
primary_entities:
- AgentWorkspaceGuidanceBundle
- AgentsEntry
- AlwaysRule
- Skill
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 15 - Agent Workspace Guidance Index

## Purpose

This phase defines **Agent Workspace Guidance**: the product capability that lets coding agents (Cursor, Claude Code–style runtimes, and other MCP clients) load project **AGENTS entry**, **always-on rules**, and **on-demand skills** from Astloom before they write code.

Storage and governance reuse Common Context. Session delivery is **MCP-primary** with optional filesystem materialize/export. This phase owns the agent-facing artifact model, connect-time resolve path, contracts, and acceptance criteria.

It also specifies the **MCP-first seed pack**: the always-on rule and skills that tell those agents to send Astloom-capable work through MCP tools (memory, code graph, dead-code cleanup, docs-sync, durable writes, tasks, guidance resolve) instead of local-only substitutes.

## Locked Design Defaults

| Decision | Choice |
| --- | --- |
| Delivery | Hybrid: MCP resolve is authoritative; filesystem export is optional |
| Storage | Layer on Common Context (`agents_entry`, `always_rule`, `skill`); no parallel SoT |
| Precedence | Task override > user profile > project guidance > org defaults |
| Layers | `org` (workspace defaults) · `project` · `user` (workspace-personal); same Common Context SoT |

## Files

| File | Owns |
| --- | --- |
| [`01-feature-specification.md`](01-feature-specification.md) | Problem, goals, non-goals, actors, workflows, FR/NFR, acceptance |
| [`02-high-level-design.md`](02-high-level-design.md) | Connect-time resolve, MCP surface, optional materialize, ownership |
| [`03-low-level-design.md`](03-low-level-design.md) | Artifact model, resolve pipeline, budgets, export layout mapping |
| [`04-data-contracts-and-events.md`](04-data-contracts-and-events.md) | Bundle DTO, MCP tools, events, versioning |
| [`05-risks-challenges-and-acceptance.md`](05-risks-challenges-and-acceptance.md) | Risks, acceptance gates, residual gaps + implementation progress |
| [`06-mcp-first-agent-skills-and-rules.md`](06-mcp-first-agent-skills-and-rules.md) | Seed always-on rule + skills that route Astloom work over MCP (includes dead-code cleanup) |

## Reading Order

1. This index.
2. Feature specification.
3. High-level design.
4. Low-level design.
5. Data contracts and events.
6. Risks and acceptance.
7. MCP-first agent skills and rules (seed pack for Cursor and other coding agents).

## Boundaries

| Need | Go to |
| --- | --- |
| Common Context store, approval, scoring | [`../12-common-context-reuse/`](../12-common-context-reuse/) |
| Platform policy execution | [`../04-rule-engine-orchestration/`](../04-rule-engine-orchestration/) |
| Usage Profile / Cursor MCP onboarding | [`../08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md`](../08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md) |
| Code-metadata context packs | [`../07-code-knowledge-graph/09-context-pack-retrieval-and-agent-workflow.md`](../07-code-knowledge-graph/09-context-pack-retrieval-and-agent-workflow.md) |
| This repo’s own Cursor IDE rules/skills | [`../agents/00-index.md`](../agents/00-index.md) (**not** product scope) |

## Relationship To IDE Docs

[`docs/agents/`](../agents/) documents how Cursor is configured **while developing Astloom**. Phase 15 documents how **customer projects** publish the same *shape* of guidance through the platform so any connected coding agent can consume it.
