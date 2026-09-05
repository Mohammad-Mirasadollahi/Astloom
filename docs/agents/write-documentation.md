---
doc_id: as.doc.agents.write-documentation
title: Write Documentation Skill (All Agents)
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-docs
summary: How any coding agent loads the write-documentation skill and the documentation authoring
  law — not Cursor-specific.
tags:
- documentation
- agents
- skills
phase: agents
canonical_path: docs/agents/write-documentation.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- agents
- platform-engineering
authority: normative
visibility: internal
linked_symbols: []
language: en
security_classification: internal
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Write Documentation Skill (All Agents)

## Purpose

Entry point for **any** IDE or coding agent that authors or reviews Astloom documentation. Cursor is one consumer; Claude Code, Codex, and others use the same paths.

## Load these first

1. **Law:** [documentation-authoring.md](./documentation-authoring.md)
2. **Skill body:** `.agents/skills/write-documentation/SKILL.md`  
   Canonical source: `ai-toolstack/skills/astloom/write-documentation/SKILL.md`  
   (`.agents/skills/` is mirrored by `./ai-toolstack/install.sh`)
3. **Standards pack:** `backend/docs/standards/documentation/` (`01`–`04`)

## When to use

User asks to document a feature, service, API, deployment step, gap, HLD/LLD/runbook, or to edit existing Markdown under `backend/docs/`, `frontend/docs/`, `docs/`, `ai-toolstack/docs/`, or `deploy-toolkit/`.

Also load when reviewing a doc that may fail the pack — then restructure per the law.

## Invocation hints (by tool)

| Tool | How |
|------|-----|
| Cursor | Skill `write-documentation`; rule `documentation-authoring.mdc` (always on) |
| Claude Code / Agents skills | `.agents/skills/write-documentation/` |
| Any agent reading repo entry | `AGENTS.md` → this file + law |

## Related Documents

- [documentation-authoring.md](./documentation-authoring.md) — portable law
- [domain.md](./domain.md) — where domain docs live
- `backend/docs/standards/documentation/README.md` — normative pack index
