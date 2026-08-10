---
doc_id: as.doc.master.agent-control-plane-product-boundary
title: Agent Control Plane Product Boundary
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Accepted and normative. This document resolves whether Astloom is itself an agent.
tags:
- standard
- master
phase: 00-master-plan
canonical_path: docs/00-master-plan/07-agent-control-plane-product-boundary.md
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

# Agent Control Plane Product Boundary


## Purpose

Accepted and normative. This document resolves whether Astloom is itself an agent.

## Status

Accepted and normative. This document resolves whether Astloom is itself an agent.

## Relationship to product wedge

Product scope leads with a wedge: connect to a codebase, build structured code knowledge, and improve the outputs of connected IDE assistants and agent runtimes. See `01-product-scope-and-feature-catalog.md`.

That wedge does not change this boundary. Improving agent outputs means supplying governed context, memory references, rules, and evidence to external executors. It does not mean Astloom becomes the executor, writes repository mutations itself, or embeds an agent framework as domain logic.

## Decision

Astloom is a vendor-neutral knowledge and control plane for registering, coordinating, governing, observing, and improving autonomous and semi-autonomous agents. Astloom is not an agent, an LLM, an agent executor, or an agent framework.

External runtimes perform task execution. Examples include Codex, IDE-based workers, MCP-connected tools, LangChain applications, Qwen-powered services, CI workers, and custom organization agents. They connect through versioned `AgentAdapter` contracts and remain replaceable.

## Owned Responsibilities

Astloom owns:

- `AgentRegistry`: identity, capabilities, allowed scopes, adapter type, health, and lifecycle state;
- `AgentTicket`: durable work, acceptance criteria, dependencies, assignment, claim, progress, block, review, completion, failure, cancellation, and reassignment;
- `CapabilityRouter`: deterministic eligibility filtering and explainable selection, with optional model recommendations;
- `AdapterRegistry`: dispatch, health, cancellation, and result normalization across agent vendors;
- governance: authorization, project isolation, approval gates, rate and risk policy, and fail-closed controls;
- shared context and memory references without exposing another service's private persistence;
- audit, correlation, metrics, traces, evidence, and agent performance history.

Astloom does not own:

- an agent's private reasoning loop, tools, prompt framework, or execution sandbox;
- vendor-specific behavior outside an adapter;
- direct mutation of repositories or business systems on behalf of an agent;
- model-generated authorization, state transitions, or approval bypasses.

## Runtime Boundary

```mermaid
flowchart LR
    Human["Human supervisor"] --> CP["Astloom control plane"]
    CP --> Registry["Agent registry"]
    CP --> Tickets["Durable ticket lifecycle"]
    CP --> Router["Capability router"]
    CP --> Policy["Governance and approvals"]
    CP --> Audit["Audit and observability"]
    Router --> Adapters["Versioned AgentAdapter boundary"]
    Adapters --> Codex["Codex agent"]
    Adapters --> IDE["IDE-based worker"]
    Adapters --> MCP["MCP or custom agent"]
    Adapters --> Framework["LangChain or other runtime"]
    CP -. "bounded recommendations" .-> Qwen["Qwen Cloud"]
```

## Qwen Boundary

Qwen Cloud may provide structured task decomposition, capability extraction, routing recommendations, conflict adjudication, evidence summarization, and evaluation. Every response must be schema-validated and auditable. Deterministic application policies remain authoritative for agent eligibility, tenant and project scope, ticket transitions, concurrency, idempotency, and human approval.

## Required Aggregate States

An agent has a governed lifecycle such as `registered`, `online`, `degraded`, `paused`, `offline`, or `revoked`. A ticket uses explicit transitions across `created`, `assigned`, `claimed`, `in_progress`, `blocked`, `review`, `completed`, `failed`, and `canceled`. Every mutation uses optimistic concurrency and creates audit evidence.

## Architectural Consequences

- Core application services depend on `AgentAdapter` and repository ports, never vendor SDKs.
- A model-backed demo worker is still an adapter-managed external-agent simulation; it is not embedded domain logic.
- LangChain is optional behind an adapter and must not become the orchestration core.
- Agent-to-agent collaboration is represented as tickets and versioned messages, not hidden sequential prompt calls.
- Admin UI and SDKs operate on agents, capabilities, tickets, dispatches, approvals, and evidence.
- Native collaboration aggregates beyond AgentTicket (Issue, Task, ChangeSet, reviews, discussion, labels) are specified in `../01-core-data-model/07-agent-collaboration-work-surface.md`. External VCS/trackers remain optional projections per `../05-interoperability-ecosystem/10-external-vcs-and-tracker-mapping.md`.

## Acceptance Criteria

- An agent can be registered, health-checked, paused, and selected by capability.
- A durable ticket can be assigned, dispatched, observed, reviewed, completed, or reassigned.
- At least two different adapter implementations can satisfy the same port in tests or runtime.
- Replacing an agent runtime does not change domain or application logic.
- Model failure cannot bypass deterministic policy or corrupt a ticket transition.
