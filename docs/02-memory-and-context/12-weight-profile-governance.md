---
doc_id: as.doc.memory.weight-profile-governance
title: 12 - Weight Profile Governance
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-architecture
summary: Closes GAP-006 with ownership, approval, activation, and rollback rules for versioned
  WeightProfiles, plus Astloom CLI governance commands.
tags:
- memory
- weight-profile
- governance
- gap-006
- standard
phase: 02-memory-and-context
canonical_path: docs/02-memory-and-context/12-weight-profile-governance.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/packages/weight_profiles/governance.py
- backend/packages/astloom_cli/commands/weight_profile.py
- backend/configs/weight-profiles/default-memory-profile.json
related_docs:
- docs/02-memory-and-context/04-data-contracts-and-events.md
- docs/10-gap-analysis/01-gap-register.md
doc_version: 1.0.1
audience:
- engineer
- architect
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 12 - Weight Profile Governance

## Purpose

Close **GAP-006**: who may change WeightProfiles, how changes are validated, and how activation rolls back.

## Ownership

| Role | Authority |
| --- | --- |
| Memory Platform Lead | Approve catalog profiles (`approved_by`) and authorize production activation |
| Project operator (CLI) | Activate / rollback an already-approved catalog profile for a project |
| Runtime (`memory-service`) | Consume active profile weights; never invent final weights in code |

## Change control

1. Author a versioned JSON profile under `backend/configs/weight-profiles/`.
2. Validate against `weight-profile.schema.json` (`astloom weight-profile validate`).
3. Set `approved_by` / `approved_at` before activation (or use `--force` only in lab).
4. Activate via CLI; history lands in `.astloom/weight-profile-governance.json`.
5. Rollback pops activation history and restores the prior profile id.

## Precedence

`ASTLOOM_WEIGHT_PROFILE` env → project state `weight_profile` → governance active pointer → `default-memory-profile`.

## CLI

```text
astloom weight-profile list
astloom weight-profile show default-memory-profile
astloom weight-profile validate conservative-memory-profile
astloom weight-profile activate conservative-memory-profile --reason "tighten evidence"
astloom weight-profile rollback --steps 1
astloom weight-profile active
```

## Acceptance

- [x] Ownership + approval fields on catalog profiles.
- [x] Validation of required weights / thresholds.
- [x] Activate + rollback with audited history.
- [x] CLI commands shipped.
- [x] Unit tests for validate / activate / rollback.
