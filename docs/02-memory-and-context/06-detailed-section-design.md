---
doc_id: as.doc.memory.detailed-section-design
title: Memory and Context - Detailed Section Design
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Agents fail when they remember too little or too much. Too little memory causes repeated
  mistakes. Too much memory causes contradiction, hallucination, slow prompts, and high cost.
  The Memory and Context layer gives agents the right knowledge at the right moment.
tags:
- standard
- memory
phase: 02-memory-and-context
canonical_path: docs/02-memory-and-context/06-detailed-section-design.md
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

# Memory and Context - Detailed Section Design


## Purpose

Agents fail when they remember too little or too much. Too little memory causes repeated mistakes. Too much memory causes contradiction, hallucination, slow prompts, and high cost. The Memory and Context layer gives agents the right knowledge at the right moment.

## Why This Phase Exists

Agents fail when they remember too little or too much. Too little memory causes repeated mistakes. Too much memory causes contradiction, hallucination, slow prompts, and high cost. The Memory and Context layer gives agents the right knowledge at the right moment.

This phase turns structured records from Phase 1 into usable context.

## Three-Tier Memory in Detail

### Working Memory

Working memory is short-lived. It includes open files, current task instructions, recent command output, active errors, and temporary reasoning. It should expire when the task or session ends.

### Episodic Memory

Episodic memory stores what happened over time. Activities, WorkLogs, completed Tasks, and incident timelines live here. It is searchable but not injected by default.

### Semantic Memory

Semantic memory stores durable truth: architecture facts, active decisions, current integrations, stable business rules, API contracts, and project conventions. This is the memory agents should receive most often.

## Memory Consolidation in Detail

Consolidation is the process of transforming many events into fewer useful facts. For example, fifty failed attempts to update a payment module should not be injected into every future prompt. The final durable fact may be: the payment gateway is now PayPal API v2 and all payment requests require idempotency keys.

### Consolidation Inputs

- Activities
- WorkLogs
- Decisions
- Closed Issues
- Completed Tasks
- Test and deployment evidence
- Human approvals

### Consolidation Outputs

- SemanticFacts
- Updated current state
- Deprecated facts
- Follow-up Issues
- Prompt cache invalidation signals

## State over Event Context in Detail

Agents should start with current state. Historical events should be retrieved only when needed.

Bad prompt pattern:

- The project used Stripe, then tried Zarinpal, then moved to PayPal.

Better prompt pattern:

- Current payment gateway is PayPal API v2. Historical gateway migrations are available on request.

This keeps the agent focused and avoids accidentally reviving old designs.

## Decay and Garbage Collection in Detail

Memory can become stale. When code is deleted, APIs are replaced, or Decisions are superseded, linked memory must stop appearing in default prompts.

Decay should not always delete data. In many cases, memory should be archived or marked deprecated. This preserves auditability while protecting active context.

### Decay Signals

- Linked file no longer exists.
- Linked symbol hash no longer exists.
- A newer Decision supersedes the fact.
- The fact has not been retrieved for a long time.
- A domain owner marks the fact obsolete.
- A CI or graph check confirms the relationship is gone.

## Prompt Caching in Detail

Prompt caching works best when stable content stays stable. Astloom should separate static context from dynamic task context.

Static context examples:

- Organization security rules.
- System architecture summary.
- Coding standards.
- Active high-level Decisions.
- Stable glossary and domain model.

Dynamic context examples:

- Current Task.
- Relevant code snippets.
- Recent error output.
- Retrieved Decisions for touched files.
- Drift findings or approval status.

## Dynamic Context Injection and RAG in Detail

RAG should not be only vector search. Astloom should combine:

- Graph traversal from Task to Issue to Decision to code/docs.
- Semantic search over memory and documentation.
- Policy filters for permissions and tenant boundaries.
- Recency and confidence ranking.
- Current-state preference over historical-event preference.

## Architecture Flow Notes

The Memory layer should be built around ContextBundles. A ContextBundle is the exact context package prepared for an agent. It should record which static prompt version was used, which dynamic references were included, why they were included, and the token budget.

## Module Responsibility Notes

### Memory Classifier

Determines if new information is temporary, historical, durable, restricted, or deprecated.

### Consolidation Scheduler

Runs after tasks, sessions, incidents, or scheduled intervals. It should be reviewable for high-risk domains.

### State Reconciler

Maintains the current truth. It should support supersession rather than deletion.

### Retriever

Builds ContextBundles using graph links, vector search, policy constraints, and ranking.

### Prompt Builder

Constructs cache-friendly prompts with stable sections first and dynamic sections later.

## Edge Cases

- Two Decisions conflict: apply precedence, owner review, and confidence labels.
- RAG misses a critical rule: fall back to graph links for owned code and policies.
- A stale fact is still legally important: archive it but exclude it from default prompts.
- Prompt cache invalidates too often: separate volatile content from static sections.
- A task exceeds token budget: retrieve summaries first, then allow explicit expansion.

## Output of This Phase

At the end of this phase, agents no longer depend on chat history. They receive precise, current, traceable context while preserving cost control and auditability.

## Dynamic Weighting for Forgotten or Low-Visibility Memory

Astloom must not treat memory decay as a simple age-based deletion rule. Some facts may be old but still critical. Other facts may be recent but low value. The memory layer therefore needs dynamic weighting instead of hard-coded constants.

The system should assign retrieval, decay, and retention weights through versioned configuration profiles. A profile can be different for security, billing, documentation, product, DevOps, support, and ordinary development tasks.

### Required Weight Signals

The memory scoring model should consider multiple signals at the same time:

- Recency: when the memory was created or last updated.
- Usage frequency: how often agents or humans retrieved it.
- Successful reuse: whether using the memory helped complete tasks or avoid mistakes.
- Domain criticality: security, billing, compliance, customer data, and production memories decay more slowly.
- Evidence strength: memories backed by Decisions, tests, approvals, or merged code have higher authority.
- Graph centrality: memories connected to many active code symbols, docs, rules, or tasks are more important.
- Ownership status: memories owned or verified by humans have higher trust.
- Conflict status: memories that conflict with active facts should be suppressed or escalated.
- Deprecation evidence: deleted files, missing symbols, superseded Decisions, and expired policies lower default retrieval priority.
- Recovery value: memories that helped recover from incidents or explain risky behavior should be retained longer.

### Forgotten Memory Handling

A memory item can appear forgotten when it has low usage, low retrieval rank, or no recent links. That does not mean it should be deleted. The system should first classify why it is low-visibility.

Possible classifications:

- Obsolete: linked code or domain no longer exists.
- Dormant but important: rarely used, but critical when needed.
- Under-linked: still useful, but graph relationships are missing.
- Conflicting: replaced by newer facts or Decisions.
- Low confidence: generated without strong evidence.

Each classification should produce a different action. Obsolete memories can be deprecated. Dormant but important memories should be retained with low default retrieval but high emergency retrieval. Under-linked memories should create graph repair tasks. Conflicting memories should create review or supersession workflows.

### No Hard-Coded Weights

Weights must not be embedded as fixed numbers in application logic. They should come from configuration, policy, or learned feedback.

Recommended sources:

- tenant-level memory policy,
- domain-level weighting profile,
- task-type retrieval profile,
- human owner override,
- feedback from successful or failed agent runs,
- incident postmortem labels,
- compliance retention rules.

A default profile can exist, but it must be externalized, versioned, auditable, and adjustable without code changes.
