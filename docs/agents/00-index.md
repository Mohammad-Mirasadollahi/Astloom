---
doc_id: as.doc.agents.index
title: IDE agent documentation index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: English-only. **This tree is Cursor IDE setup and agent behavior in this repo—not
  Astloom product architecture.** Product specs live under [`../README.md`](../README.md)
  (phases 00–15).
tags:
- index
- agents
phase: agents
canonical_path: docs/agents/00-index.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# IDE agent documentation index


## Purpose

English-only. **This tree is Cursor IDE setup and agent behavior in this repo—not Astloom product architecture.** Product specs live under [`../README.md`](../README.md) (phases 00–15).

English-only. **This tree is Cursor IDE setup and agent behavior in this repo—not Astloom product architecture.** Product specs live under [`../README.md`](../README.md) (phases 00–15).

**Canonical file:** this folder at repo root (`docs/agents/`).

## Reading order

| Step | Document | Why |
| --- | --- | --- |
| 1 | [`AGENTS.md`](../../AGENTS.md) | Entry: laws, high-signal skills |
| 2 | [`team-documentation-playbook-for-astloom.md`](team-documentation-playbook-for-astloom.md) | Team method: which docs to follow for Astloom-quality Markdown + code links |
| 2a | [`TEAM-HANDOUT-astloom-documentation-complete.md`](TEAM-HANDOUT-astloom-documentation-complete.md) | **Give this one file to teams** — complete LIST A/B/C + rules |
| 3 | [`documentation-authoring.md`](documentation-authoring.md) | Portable Full-tier authoring law |
| 4 | [`.cursor/rules/`](../../.cursor/rules/) | Always-apply / scoped Cursor rules (`.mdc`) |
| 5 | [`.cursor/skills/`](../../.cursor/skills/) · [`.agents/skills/`](../../.agents/skills/) | Agent skills (`SKILL.md`) |
| 6 | [`ide-mcp-first-workflow.md`](ide-mcp-first-workflow.md) | Docs-first discovery, live-test flow (if present) |
| 7 | [`ide-workspace-rule-discovery.md`](ide-workspace-rule-discovery.md) | Optional: org interview → workspace packs → `.mdc` (if present) |
| 8 | [`domain.md`](domain.md) | Monorepo context |
| 9 | [`issue-tracker.md`](issue-tracker.md) · [`triage-labels.md`](triage-labels.md) | Issue workflow vocabulary |

## Active Persian / language rules

| Path | Role |
| --- | --- |
| `.cursor/rules/persian-chat-typography.mdc` | RTL wrapper + right alignment (`alwaysApply`) |
| `.cursor/rules/reply-fa-code-docs-en.mdc` | Persian chat; English code/docs (`alwaysApply`) |
| `.cursor/rules/compose-wait-timeouts.mdc` | Hard 90s Compose/Neo4j wait cutoff; no pytest+sleep chains |
| `.cursor/skills/persian-chat-reply/SKILL.md` | Skill detailing the RTL reply pattern |

## Not for product implementation

| Need | Go to |
| --- | --- |
| Platform rule engine | `docs/04-rule-engine-orchestration/` |
| Product domain packs | `docs/08-software-engineering-architecture/26-domain-customization-and-feature-control.md` |
| Product AGENTS / rules / skills for connected coding agents | [`../15-agent-workspace-guidance/00-index.md`](../15-agent-workspace-guidance/00-index.md) |
| MCP-first seed skills (route work to Astloom via MCP) | [`../15-agent-workspace-guidance/06-mcp-first-agent-skills-and-rules.md`](../15-agent-workspace-guidance/06-mcp-first-agent-skills-and-rules.md) |
| Backend | `backend/docs/` |

IDE `.mdc` configuration in this repository does **not** implement those product features.

## After changing rules/skills

Cursor → **Reload Window**.
