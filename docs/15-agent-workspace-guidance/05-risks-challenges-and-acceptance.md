---
doc_id: as.doc.awg.risks-acceptance
title: 05 - Agent Workspace Guidance Risks Challenges And Acceptance
doc_type: gap
status: active
schema_version: '1.0'
owner: platform-product
summary: Risks, mitigations, engineering and product acceptance gates, and residual open gaps
  for Agent Workspace Guidance after the MCP-first vertical slice.
tags:
- agent-workspace-guidance
- risks
- acceptance
- security
phase: 15-agent-workspace-guidance
canonical_path: docs/15-agent-workspace-guidance/05-risks-challenges-and-acceptance.md
lifecycle_lane: current
concern_lane: problem
audience_lane:
- platform-engineering
- security
- product
authority: normative
visibility: internal
linked_symbols:
- backend/services/common-context-service/src/common_context_service/guidance_export.py::materialize_mcp_first_seed
- backend/services/common-context-service/src/common_context_service/layout_profiles.py::get_layout_profile
- backend/services/common-context-service/src/common_context_service/guidance_migrate.py::migrate_untyped_guidance_items
- backend/configs/guidance-export/layouts.json
related_docs:
- as.doc.awg.feature-specification
- as.doc.awg.data-contracts
- as.doc.awg.low-level-design
- as.doc.gap.architecture-gaps
doc_version: 1.1.1
audience:
- engineer
- architect
- product
- security
primary_entities:
- AgentWorkspaceGuidanceBundle
relations_declared:
- type: depends_on
  target: as.doc.awg.feature-specification
- type: complements
  target: as.doc.gap.architecture-gaps
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 05 - Agent Workspace Guidance Risks Challenges And Acceptance

## Purpose

This document records risks, mitigations, acceptance gates, and remaining open gaps for Agent Workspace Guidance. Feature behavior is owned by the feature specification; this file owns verification and residual risk.

## Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Prompt injection via approved guidance bodies | Agent follows malicious instructions | Approval gates; audit diffs; restrict who can approve; optional malware/secret scanners on body |
| Skill sprawl | Token waste, conflicting procedures | Catalog budgets; applicability filters; retire unused skills; admin health views |
| Dual-source drift (MCP SoT vs disk export) | Agents follow stale or conflicting files | MCP authoritative; export conflict detection; managed-hash tracking; no silent overwrite |
| Confusion with IDE repo docs | Engineers edit `.cursor/` in Astloom repo expecting product behavior | Explicit boundary in indexes; product UI copy names “project guidance” |
| Confusion with rule engine | Always-on text treated as enforceable policy | Docs + UI labels; no auto-execution path from AWG rules |
| Two approved `agents_entry` items | Non-deterministic agent laws | Reject-on-create invariant; resolve fails closed if violated |
| Over-injection of skill bodies | Context bloat | Default catalog-only resolve; get-skill on demand |
| Stale cache on Common Context outage | Wrong guidance applied | Prefer fail closed; if cache allowed, mark `stale=true` and surface to agent |
| Cross-tenant tool misuse | Data leak | MCP env scope; ignore client-supplied foreign project ids |
| Mandatory rule vs task override | Unsafe work or blocked legitimate tasks | Conflict records; profile policy block-vs-warn; human escalation |

## Challenges

- Portable layout mapping across Cursor and Claude-compatible trees without claiming proprietary compatibility.
- Teaching agents to call resolve **before** first write without brittle prompt-only instructions (Usage Profile descriptions + onboarding docs).
- Migrating free-text CommonItems into typed kinds without breaking existing resolvers.
- Keeping export useful for filesystem-only clients while preventing governance bypass through local edits.

## Engineering Acceptance Criteria

1. Typed kinds `agents_entry`, `always_rule`, and `skill` validate on write.
2. Resolve returns a schema-valid `AgentWorkspaceGuidanceBundle` with audit id.
3. At most one active approved `agents_entry` per project; violations are rejected or fail closed.
4. Skill catalog entries omit bodies; `get_skill` returns body only for in-scope approved skills.
5. Precedence tests cover task > user > project > org, org entry fallback, same-slug replacement, and mandatory conflict recording when a higher layer would override a mandatory lower item.
6. MCP tools appear only when Usage Profile allow-lists them; unknown tools fail closed.
7. Export dry-run reports unmanaged local edits as conflicts and does not write them.
8. Observability includes counts by kind, token estimates, and conflict reason codes.
9. Automated unit and contract tests exist for the above before feature gate pass.

## Product Acceptance Criteria

1. Project admin can author entry, rules, and skills in Astloom and approve them.
2. Connected coding agent can resolve guidance over MCP and use it before coding.
3. Operator can explain from audit UI which guidance applied to a session (`bundle_id`).
4. Optional export produces IDE-native files for a chosen layout without silent clobber.
5. Empty project shows a clear empty state and seeding path.
6. Product metrics for resolve-before-write and guidance coverage are defined in reporting design (may ship after vertical slice).

## Documentation Acceptance (This Pass)

- Phase `15-agent-workspace-guidance` exists with index and specs 01–06.
- Cross-links from docs map, Common Context index, Usage Profile doc, IDE agents index, and GAP-A06 note are present.
- MCP-first seed rule/skills are specified in [`06-mcp-first-agent-skills-and-rules.md`](06-mcp-first-agent-skills-and-rules.md).
- Bodies are English and follow documentation standards 06/08/09.

## Implementation Progress (2026-07-26)

| Capability | Status | Evidence |
| --- | --- | --- |
| Typed kinds + resolve + audit | Shipped | `astloom_guidance_resolve`, Common Context service |
| MCP-first seed pack + materialize | Shipped | `seed_mcp_first.py`, `materialize_mcp_first_seed` |
| Layout profiles (Cursor / Claude / generic) | Shipped | `backend/configs/guidance-export/layouts.json`, `layout_profiles.py` |
| Untyped → typed migration helper | Shipped | `guidance_migrate.py` (propose/apply heuristics) |
| Soft resolve-before-write | Shipped | MCP-first always rule + skills |
| Hard resolve-before-write gate | Optional / env | `ASTLOOM_GUIDANCE_RESOLVE_REQUIRED` + MCP gateway writes |
| GAP-A06 IDE chrome | Deferred | Backend closed; plugin banners remain future |

## Open Gaps

| Gap | Status | Notes |
| --- | --- | --- |
| GAP-A06 IDE boundary / context injection UX | Deferred | Plugin chrome / in-IDE banners remain future work |
| Exact Claude directory aliases | Closed | Profile JSON under `backend/configs/guidance-export/layouts.json` (not hard-coded) |
| Vertical slice implementation | Closed | Common Context kinds + MCP tools + exporter + seed |
| Agent-enforced “resolve before write” | Partial | Soft via MCP-first; hard gate via env flag |
| Migration tooling for untyped CommonItems | Closed (helper) | Deterministic propose/apply; operator applies via service/CLI follow-on if needed |
| Seed pack materialization in Common Context | Closed | Connect-time / ensure-seed + export materialize |

## Residual Decision Log

| Decision | Choice | Rationale |
| --- | --- | --- |
| Delivery | MCP-primary hybrid | Matches Usage Profile path; keeps filesystem clients viable |
| Storage | Common Context typed kinds | Avoid parallel SoT and reuse governance |
| Skill bodies in resolve | Default off | Token and injection surface control |
