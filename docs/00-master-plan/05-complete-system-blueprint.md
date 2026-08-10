---
doc_id: as.doc.master.complete-system-blueprint
title: Complete System Blueprint
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: >-
  Astloom connects to a codebase and improves the outputs of connected AI coding
  tools. It indexes repository structure, documentation, decisions, and current project truth,
  then injects task-scoped context into IDE assistants and agent runtimes. The first proof
  of value is measurable — fewer hallucinations, less rework, lower token cost, stronger
  architecture adherence, and measured dead-code / stale-documentation cleanup.
tags:
- standard
- master
phase: 00-master-plan
canonical_path: docs/00-master-plan/05-complete-system-blueprint.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.4
updated_at: 2026-08-10
---

# Complete System Blueprint


## Purpose

Astloom connects to a codebase and improves the outputs of connected AI coding tools. It indexes repository structure, documentation, decisions, and current project truth, then injects task-scoped context into IDE assistants and agent runtimes. The first proof of value is measurable — fewer hallucinations, less rework, lower token cost, stronger architecture adherence, and measured dead-code / stale-documentation cleanup.

## Executive Summary

Astloom connects to a codebase and improves the outputs of connected AI coding tools. It indexes repository structure, documentation, decisions, and current project truth, then injects task-scoped context into IDE assistants and agent runtimes. The first proof of value is measurable: fewer hallucinations, less rework, lower token cost, and stronger architecture adherence — plus measured dead-code and stale-documentation cleanup.

The platform does not replace coding assistants, IDEs, CI pipelines, ticket systems, or human reviewers. Connected runtimes still execute work. Astloom owns the code-linked knowledge layer and, over time, the control plane that coordinates those runtimes.

The deeper organizational problem remains: AI work often disappears into chat history. After a change ships, teams still need durable answers to what changed, why it changed, which decision justified it, which documents are stale, which teams are affected, and whether a human should approve risk. Astloom solves that by turning meaningful work into structured entities and events. That broader operating layer is the expansion path. The wedge that earns adoption is code connection and output improvement.

## Product Positioning

### Wedge

Astloom's primary product promise is:

**Connect a repository → build structured code knowledge → improve AI outputs → measure the gain.**

Readers and implementers should treat repository connection, the Code-Knowledge Graph, context injection, correction loops, and benefit measurement as the first credible product surface. See `01-product-scope-and-feature-catalog.md`.

### Control-plane destination

Astloom is also the vendor-neutral control plane for agentic work. It is not a single agent, an LLM, or an agent framework. Independently executed agents and humans coordinate through adapters, capability routing, durable tickets, governance, health supervision, shared context, and audit evidence.

The boundary is strict: Astloom may use a model for bounded control-plane intelligence, but it must not hide an internal agent runtime behind the coordinator. Codex, IDE-based workers, LangChain applications, Qwen-powered workers, and custom services remain external managed agents. Deterministic code owns permissions, lifecycle transitions, idempotency, concurrency, and approval gates.

### Value stack

The wedge is valuable because it gives developers and leads:

- Connected truth: agents see what exists in the repository now.
- Relevant context: task-scoped symbols, docs, decisions, and constraints instead of repository dumps.
- Better outputs: fewer invented APIs, fewer architecture violations, less abandoned work — **dead-code cleanup** so replacements do not leave orphaned symbols behind, and **stale-documentation cleanup** so orphan/ghost/wiki/duplicate docs do not mislead retrieval.
- Cost control: precise context reduces token waste and retry loops.
- Evidence of gain: benefit metrics against a pre-connection baseline, including cleanup KPIs.

Astloom surfaces **scored** unused candidates from the Code-Knowledge Graph (`score`, `evidence`, finding kinds including `zombie_package` and optional `runtime_dead` / `flag_controlled_dead`) and seeds always-on guidance so connected coding agents delete proven-dead predecessors in the same change. Astloom does not delete repository files itself. See `../07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md`.

Sister loop: scored **stale-documentation** candidates (`orphan_doc`, `ghost_link`, `stale_anchor`, `superseded_retrieval_risk`, `wiki_orphan`, `duplicate_authority`, optional `coverage_gap`) via MCP `astloom_docs_stale_candidates` and skill `astloom-remove-stale-docs`. Astloom does not mutate Markdown. See `../07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md`.

The platform expansion adds:

- Accountability: every important action has an actor, timestamp, evidence, and result.
- Memory: future agents inherit current project truth instead of repeating old mistakes.
- Governance: risky changes can be blocked, reviewed, approved, or rejected.
- Synchronization: code, docs, decisions, and tasks stay linked.
- Interoperability: different tools coordinate without sharing one vendor runtime.

## Core Concepts

### Structured Work

Astloom treats work as a set of structured records. Activity records answer what happened. WorkLog records summarize session outcomes. Decision records explain why. Issue records define discovered risks. Task records define executable follow-up work.

This distinction is critical. Without it, the platform becomes another chat archive. With it, the platform becomes a project memory and orchestration system.

### Current Truth

Astloom should not inject every historical event into every prompt. Agents need the current truth first. Historical context is retrieved only when the task requires it. This prevents contradiction, reduces token cost, and makes future agents less likely to revive obsolete designs.

### Docs as Live System State

Documentation is not treated as passive text. Documents are linked to code symbols, decisions, tasks, issues, APIs, and owners. If code changes and the relevant documentation does not change, the platform detects drift and creates actionable work.

### Semantic Governance

Some rules are not simple file-path checks. A change to pricing, authentication, permissions, customer data, or production infrastructure may be risky even when the file name looks harmless. Astloom supports natural-language policies and model-based judgment for these ambiguous cases, while still relying on deterministic checks first.

### Vendor Neutrality

Enterprises rarely use only one AI tool. One team may use an IDE assistant, another may use an autonomous agent, and another may use internal scripts. Astloom provides a shared protocol and broker so tools can coordinate while remaining vendor independent.

## End-to-End Example

A backend agent changes the password hashing algorithm from SHA256 to Argon2.

1. The agent records Activities for changed files, tests, and commands.
2. The agent writes a WorkLog explaining the outcome and remaining migration risk.
3. A Decision is created to explain why Argon2 was chosen despite slower login performance.
4. The platform discovers an Issue: old users still have SHA256 hashes.
5. The Issue is decomposed into Tasks for backend fallback logic, data backup, migration, QA, and docs.
6. Semantic memory is updated: current password hashing is Argon2.
7. Documentation anchors linked to authentication code are checked for drift.
8. Security policies are evaluated before merge.
9. If risk is high, an approval ticket is sent to the security owner.
10. Once approved and completed, the broker publishes events to subscribed agents and dashboards.

This example shows the whole platform working as one system: data model, memory, docs, rules, orchestration, and interoperability.

## Architectural Boundaries

### What Astloom Owns

- The code-connected knowledge layer that improves external agent and IDE outputs.
- The canonical record of AI-assisted work.
- The shared memory and context model.
- The knowledge graph linking work, docs, code, rules, and ownership.
- The policy evaluation and escalation workflow.
- The protocol and event broker between agents and tools.
- Benefit measurement evidence for whether connected context improved outcomes.

### What Astloom Integrates With

- Source control and repositories.
- CI and test systems.
- IDEs and coding assistants.
- Ticketing systems and approval tools.
- Model providers and autonomous agents.
- Department workflow tools.

### What Astloom Must Not Do Initially

- Replace source control.
- Replace human accountability.
- Allow unbounded autonomous production changes.
- Depend on one model vendor.
- Treat generated text as trustworthy without structured evidence.

## System Qualities

### Reliability

Every workflow must be idempotent where possible. Repeated event delivery should not create duplicate Decisions or Tasks. Failed broker deliveries must go to a visible dead-letter queue.

### Auditability

Every generated record must preserve source references. Summaries are useful, but evidence must remain reachable. Approval decisions must include actor, timestamp, presented evidence, and decision reason.

### Security

Secrets must be redacted before storage in prompts, dashboards, or broker events. Tenant and project boundaries must be enforced before context injection or event delivery.

### Cost Efficiency

The platform should prefer deterministic checks, graph lookup, Bloom filters, and cached prompt sections before using expensive model calls.

### Human Usability

Documents and tickets must be readable by humans. A reviewer should understand the risk without reading raw model logs.

## Phase Dependency Model

Phase 1 is the foundation because every later phase needs stable entities.

Phase 2 depends on Phase 1 because memory is built from Activities, WorkLogs, Decisions, Issues, and Tasks.

Phase 3 depends on Phases 1 and 2 because documentation links need code symbols, Decisions, Tasks, and current semantic state.

Phase 4 depends on the graph and memory because policies require evidence and impact analysis.

Phase 5 depends on a mature internal model because external tools need stable contracts before they can interoperate reliably.

## Definition of Complete Documentation

The documentation is complete when a team can understand:

- What the platform is.
- Why each feature exists.
- Which phase owns each feature.
- Which entities and events are required.
- Which components and modules must exist.
- Which risks and edge cases must be handled.
- Which acceptance criteria prove the phase is ready.
- How each phase connects to the others.
