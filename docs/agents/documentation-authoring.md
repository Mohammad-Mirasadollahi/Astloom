---
doc_id: as.doc.agents.documentation-authoring
title: Documentation Authoring (All Agents)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: IDE-agnostic law for writing and reviewing ThinkingSOC Markdown. Applies to Cursor,
  Claude Code, Codex, and any agent that reads docs/agents or AGENTS.md.
tags:
- documentation
- agents
- authoring
phase: agents
canonical_path: docs/agents/documentation-authoring.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- agents
- platform-engineering
authority: normative
visibility: internal
doc_version: 1.0.1
updated_at: 2026-08-10
linked_symbols:
- backend/packages/astloom_cli/commands/docs_standards/check.py::check_markdown_doc
- backend/packages/astloom_cli/commands/docs_standards/remediate.py::remediate_markdown_doc
language: en
security_classification: internal
---

# Documentation Authoring (All Agents)


## Purpose

IDE-agnostic law for writing and reviewing ThinkingSOC Markdown. Applies to Cursor, Claude Code, Codex, and any agent that reads docs/agents or AGENTS.md.

**Scope:** Every coding agent working in this repository (Cursor, Claude Code, Codex, Copilot workspace agents, and others). This file is the **portable law**. Cursor also loads a mirror as `documentation-authoring.mdc` after `./ai-toolstack/install.sh`.

**Canonical standards pack:** `backend/docs/standards/documentation/`

| Doc | Owns |
|-----|------|
| `01-professional-documentation-standard.md` | Tone, audience, required sections |
| `02-documentation-structure-and-machine-ingest-standard.md` | Placement, modularity, frontmatter, edit/restructure |
| `03-documentation-classification-and-lanes.md` | Lifecycle / concern / audience / authority / visibility |
| `04-diagrams-and-agent-readable-flows.md` | Mermaid + agent-readable flow tables |

**Skill (portable):** `.agents/skills/write-documentation/` (symlink to `ai-toolstack/skills/thinkingsoc/write-documentation/`). Guide: [write-documentation.md](./write-documentation.md).

**Language:** English only in committed docs (`code-and-docs-english-only` project law).

## When this applies

- Creating Markdown under the doc trees below
- Any material edit of those files
- Any time you open, review, cite, or rely on a repo doc for the task — non-conformance is not ignoreable

Trees: `backend/docs/`, `frontend/docs/`, `docs/`, `ai-toolstack/docs/`, `deploy-toolkit/**/*.md`, service design/runbook trees.

Chat-only explanations are not repo docs. Do not invent Persian repo docs.

## Review gate (mandatory)

Whenever you **read or review** a documentation file on disk as part of the task:

1. Check it against the pack (`01`–`04`): structure, frontmatter, lanes, content grade, diagrams for design types.
2. If it **does not** follow the standards → you **must** bring its structure (and required metadata/diagrams) into compliance in the same work — full restructure and/or split. Do **not** leave a known non-conforming doc unchanged.
3. If the user’s ask was “only answer a question” and the file is badly out of shape: still fix the structure when you are already touching that file or the task depends on it; if the task is chat-only and you will not write to disk, say in one line that the doc is non-conforming and offer/await fix — **never** silently treat a broken shell as a finished standard doc.
4. Exception: user **explicitly** requests a minimal typo-only patch with no structural work.

## Hard requirements (new docs)

1. Correct folder (phase folder under `docs/` or service/topic under `backend/docs/standards/` unless another tree owns it).
2. Full YAML frontmatter: `doc_id` (`as.doc.<domain>.<slug>` for Astloom `docs/`; do not use `tsoc.doc.*` there), `title`, `doc_type`, `status`, `schema_version`, `owner`, `summary`, `tags`, `phase`, `canonical_path`, plus all five **lane** fields with closed-set enums from `09-…`.
3. Exactly one H1 matching `title`; Purpose H2; chunkable H2s; Related Documents for normative types.
4. Modular: soft ≤ ~400 body lines, hard ≤ ~800 or split; one concern per file. Soft-budget warnings **must** be cleared when standardizing.
5. Implementation-grade content per `01-…` / `06-professional-documentation-standard.md` (contracts, ownership, failure, verification — not marketing). Unimplemented design may be published; it **must not** read as shipped / product-ready (`lifecycle_lane` + Implementation status + honest voice).
6. **Design docs (`hld` / `lld` / `feature_spec` / `service_design`):** Mermaid + matching agent-readable flow table in the same H2 (`04-…`). Not Mermaid-only, not image-only.
7. Link from folder `README.md` / index. No secrets or customer data in examples.
8. Search for existing canonical doc first — extend or split; do not duplicate.
9. **Standardization method:** when fixing nonconformance or bulk-remediating `docs/`, follow `docs/00-master-plan/10-documentation-standardization-procedure.md` (machine gate issue codes, remediator, size splits, evidence-only `linked_symbols`). Verify with `astloom docs-standards` until zero issues. **Team brief / reading list:** `docs/agents/team-documentation-playbook-for-astloom.md`.
10. **Revision stamp on material create/edit:** bump `doc_version` (semver `MAJOR.MINOR.PATCH`) and set `updated_at` (UTC `YYYY-MM-DD`) **with** truthful body changes — never stamp-only. Prefer docs-sync drift / `linked_symbols` / catalog to choose which docs a code change must update.

## Edit / review obligation (structure wrong → fix whole doc)

If the file lacks proper structure (mega-doc, no H1/H2 discipline, missing Purpose/Related Documents, wrong placement, mixed current+future, missing frontmatter on a normative target, **or design doc missing Mermaid + flow table**):

- **Restructure the entire document** (and split siblings if budgets require) to match `02-…` + `01-…` + `03-…` + `04-…`.
- Do not only append a paragraph into a broken shell unless the user **explicitly** asks for a minimal typo-only patch.
- Leaving a reviewed non-conforming doc unfixed is a **standards violation**.

## Before write

Read `backend/docs/standards/documentation/README.md` (or the four standards). Prefer `rg` for existing `doc_id:` / topic docs. Follow TI-style 16 sections for new `*-service-design.md`.

## Where agents find this

| Surface | Path |
|---------|------|
| All agents (git-tracked) | `docs/agents/documentation-authoring.md` (this file; source of truth for sync: `ai-toolstack/docs/agents/`) |
| Skills mirror | `.agents/skills/write-documentation/` |
| Rules mirror | `.agents/rules/documentation-authoring.md` |
| Entry | `AGENTS.md` |
| Cursor-only mirror | `ai-toolstack/rules/documentation-authoring.mdc` → `.cursor/rules/` via `install.sh` |
| MCP coding agents | Tool `astloom_docs_authoring_standards` + seed skill `astloom-documentation-authoring` (payload SSOT: `common_context_service.documentation_authoring_law`) |
| Teams (human brief) | [`team-documentation-playbook-for-astloom.md`](./team-documentation-playbook-for-astloom.md) |

## Anti-patterns

Mega-bible Markdown · marketing tone · Persian in committed `.md` · colliding `doc_id` · burying future/gaps inside `current` normative files · writing unimplemented design as if the product is already ready · drive-by edits that leave structure broken · **reviewing a non-conforming doc and not fixing it** · design docs without Mermaid · Mermaid without flow table · image-only architecture diagrams · treating this law as Cursor-only
