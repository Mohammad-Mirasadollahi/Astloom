---
doc_id: as.doc.common-context.governance-and-operational-rules
title: 05 - Common Context Governance And Operational Rules
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Common Context changes how agents behave, so it must be governed like product and
  architecture policy.
tags:
- standard
- common-context
phase: 12-common-context-reuse
canonical_path: docs/12-common-context-reuse/05-governance-and-operational-rules.md
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

# 05 - Common Context Governance And Operational Rules


## Purpose

Common Context changes how agents behave, so it must be governed like product and architecture policy. The system must never silently turn every repeated phrase into an enforced rule.

## Governance Principles

Common Context changes how agents behave, so it must be governed like product and architecture policy. The system must never silently turn every repeated phrase into an enforced rule.

## Approval Rules

- Project-scoped low-risk items may be auto-proposed but should still be visible for review.
- Cross-project or project-group items require explicit approval.
- Security, privacy, deployment, and access-control items require owner approval.
- Mandatory governance items require change records and audit evidence.

## Isolation Rules

Common items are private to their project unless explicitly bound to a project group. Shared project groups must define member projects, allowed item types, owners, and revocation rules.

## Override Rules

A task-specific instruction can override common context when it is explicit and authorized. The override must be recorded with the reason. Mandatory safety or isolation policies cannot be overridden by ordinary task text.

## Retention Rules

Common items should have lifecycle status: proposed, approved, active, suppressed, deprecated, archived. Items with low usage, low confidence, or repeated conflicts should be reviewed automatically.

## Reporting Rules

Common Context must report number of repeated instructions converted to common items, avoided repetitions, estimated token savings, conflicts resolved, agent failures prevented, and stale or low-confidence items.

## Operational Risk

The main risk is over-injection. The resolver must prefer small, relevant, high-confidence items and expose suppression controls in the admin interface.
