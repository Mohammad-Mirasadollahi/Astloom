---
doc_id: as.doc.rules.approval-cli-first-surface
title: 10 - Approval CLI First Surface
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-architecture
summary: Closes GAP-004 by selecting the Astloom CLI as the first human Accept surface and
  wiring ApprovalModeProfile config plus local Accept queue commands.
tags:
- approval
- cli
- gap-004
- standard
phase: 04-rule-engine-orchestration
canonical_path: docs/04-rule-engine-orchestration/10-approval-cli-first-surface.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
- product
authority: normative
visibility: internal
linked_symbols:
- backend/packages/approval_modes/modes.py
- backend/packages/approval_modes/queue.py
- backend/packages/astloom_cli/commands/approval.py
- backend/configs/approval-modes/default.json
related_docs:
- docs/04-rule-engine-orchestration/09-approval-modes-and-auto-approve.md
- docs/10-gap-analysis/01-gap-register.md
doc_version: 1.0.1
audience:
- engineer
- architect
- product
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 10 - Approval CLI First Surface

## Purpose

Close **GAP-004** by choosing the **Astloom CLI** as the first shipped human Accept surface. Web UI / IDE / chat remain follow-ups; modes and hard-block policy stay owned by `09-approval-modes-and-auto-approve.md`.

## Decision

| Choice | Value |
| --- | --- |
| First surface | CLI (`astloom approval …`) |
| Mode catalog | `backend/configs/approval-modes/` |
| Default mode | `manual` |
| Auto path | `auto_approve` / eligible `system_routed` still persist a durable Accept record |
| Hard-block | Always human, regardless of mode |

## Document flow

```mermaid
flowchart LR
  gate[Open Accept gate] --> mode[Resolve ApprovalMode]
  mode --> route{Route}
  route -->|human| cli[CLI queue]
  route -->|auto| sys[System Accept + audit]
  cli --> decide[accept / reject]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Operator / rule-engine | Opens a gate (`enqueue` or escalate evaluation) | Pending or auto-resolved item |
| 2 | Config | Resolves effective mode (env → project → catalog) | `manual` / `auto_approve` / `system_routed` |
| 3 | Policy | Applies hard-block + mode rules | `route=human` or `route=auto` |
| 4 | Human (CLI) | `approval queue` / `accept` / `reject` | Durable resolution |

## CLI

```text
astloom approval mode show
astloom approval mode set auto_approve
astloom approval enqueue --subject-ref change:1 --subject-class docs.low_risk
astloom approval queue
astloom approval accept <id>
astloom approval reject <id>
```

## Acceptance

- [x] First surface decision recorded (CLI).
- [x] ApprovalModeProfile schema + default catalog entry.
- [x] Route decision library with hard-block fail-closed.
- [x] CLI mode / queue / accept / reject commands.
- [x] Unit tests for route policy + CLI smoke.
- [ ] Web / IDE / Slack surfaces (explicitly out of GAP-004 v1 close).
