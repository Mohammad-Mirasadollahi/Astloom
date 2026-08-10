---
doc_id: as.doc.common-context.index
title: 12 - Common Context Reuse Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: This section defines the Astloom Common Context capability.
tags:
- index
- common-context
phase: 12-common-context-reuse
canonical_path: docs/12-common-context-reuse/00-index.md
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

# 12 - Common Context Reuse Index

## Purpose

This section defines the Astloom Common Context capability. Common Context stores reusable rules, definitions, constraints, workflow reminders, and project conventions so users and agents do not need to repeat the same information in every task.

Common Context must be scoped, scored, explainable, auditable, configurable, and isolated per project. It is not hard-coded prompt text and it is not a global memory bucket.

## Files

- 01-feature-specification.md defines goals, functional requirements, non-functional requirements, and acceptance criteria.
- 02-high-level-design.md defines system-level architecture, service responsibilities, integrations, and runtime flows.
- 03-low-level-design.md defines entities, APIs, scoring inputs, resolution pipeline, conflict handling, and storage needs.
- 04-data-contracts-and-events.md defines contracts, event names, metadata, and compatibility rules.
- 05-governance-and-operational-rules.md defines approval, isolation, override, retention, reporting, and operational safety.

## Relationship To Existing Sections

- `../02-memory-and-context/` explains memory and repeated question behavior. Common Context consumes repeated signals but stores reusable project guidance separately.
- `../04-rule-engine-orchestration/` executes policies and automation decisions. Common Context supplies reusable rules and constraints but does not replace the rule engine.
- `../08-software-engineering-architecture/` defines modular engineering structure. Common Context adds a dedicated domain, service, package, and configuration profile.
- `../09-platform-governance-operations/` defines operational governance and reporting. Common Context contributes audit and benefit measurement data.
- `../15-agent-workspace-guidance/` projects typed Common Context kinds (`agents_entry`, `always_rule`, `skill`) into connect-time MCP bundles and optional IDE filesystem export. Common Context remains the source of truth; phase 15 owns the coding-agent artifact shape and delivery.
