---
doc_id: as.doc.ops.glossary-and-ubiquitous-language
title: Glossary and Ubiquitous Language
doc_type: glossary
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom spans agents, memory, documentation, code graphs, rules, brokers, and operations.
  A shared vocabulary prevents ambiguity between engineering, product, security, and business
  teams.
tags:
- glossary
- ops
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/08-glossary-and-ubiquitous-language.md
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

# Glossary and Ubiquitous Language

## Purpose

Astloom spans agents, memory, documentation, code graphs, rules, brokers, and operations. A shared vocabulary prevents ambiguity between engineering, product, security, and business teams.

## Terms

### Activity

An atomic record of an action performed by an agent or human.

### WorkLog

A session-level summary of attempted work, completed changes, blockers, and follow-ups.

### Decision

A record explaining why a technical or product choice was made.

### Issue

A discovered problem, risk, inconsistency, or need.

### Task

Executable work assigned to an agent or human.

### SemanticFact

A durable fact representing current project truth, architecture, rule, or domain knowledge.

### ContextBundle

The exact set of context prepared for an agent task, including references, static prompt version, and token budget.

### WeightProfile

A versioned configuration object that controls memory retrieval, decay, retention, and forgotten-memory handling.

### Code-Knowledge Graph

A graph representation of code files, classes, functions, methods, imports, calls, documentation, embeddings, and related decisions.

### GraphRetrievalProfile

A versioned configuration object that controls graph retrieval scoring, expansion, confidence thresholds, and penalties.

### DriftFinding

A record indicating documentation is missing, stale, invalid, or disconnected from code.

### RuleEvaluation

A record of a policy evaluation result, including verdict, confidence, rationale, and evidence.

### EscalationTicket

A human approval request created when automation reaches a risk boundary.

### ApprovalMode

User-selectable policy for how Accept gates are resolved: `manual` (always human Accept), `auto_approve` (system Accept for eligible gates), or `system_routed` (platform chooses auto vs human per item). Hard-block policies may still force human Accept. See `../04-rule-engine-orchestration/09-approval-modes-and-auto-approve.md`.

### AgentTicket

A durable control-plane assignment of work to a registered agent, with claim, progress, block, review, completion, failure, cancellation, and reassignment.

### ChangeSet

Astloom’s pull-request analog: a governed proposal to change project artifacts, reviewed inside Astloom, with patch evidence referenced as artifacts. External GitHub/GitLab PRs/MRs are optional projections.

### ReviewThread

A review conversation on a ChangeSet revision, either general or anchored to a path/symbol.

### ReviewComment

An evidence-bearing comment inside a ReviewThread; may carry verdicts such as approve, request changes, or block.

### DiscussionComment

A general discussion comment on an Issue, Task, ChangeSet, or AgentTicket (not the same as a ReviewComment).

### WorkLabel

A project-scoped taxonomy label bindable to collaboration entities. Labels do not grant authorization.

### WorkMilestone

An optional time-boxed collection of Issues, Tasks, or ChangeSets for planning views.

### Universal Agent JSON

The vendor-neutral structured message format used by agents, IDEs, adapters, and tools.

### DeadLetter

A broker message that failed delivery or validation and requires inspection or replay.

### Port Profile

A versioned or local configuration that assigns service ports for development or runtime environments.

## Naming Rules

- Use Activity for atomic actions.
- Use WorkLog for session summaries.
- Use Issue for discovered conditions.
- Use Task for executable work.
- Use AgentTicket for durable agent assignment.
- Use ChangeSet for proposed changes under review (not “GitHub PR” as the native type name).
- Use ReviewComment for change review; use DiscussionComment for general talk.
- Use Decision for rationale.
- Use DriftFinding for documentation synchronization problems.
- Use EscalationTicket for human approval workflows.
