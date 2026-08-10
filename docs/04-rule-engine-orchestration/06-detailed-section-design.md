---
doc_id: as.doc.rules.detailed-section-design
title: Rule Engine and Orchestration - Detailed Section Design
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Agents can write code, but organizations need judgment. Some changes are syntactically
  correct but business-dangerous. A pricing change, permissions change, authentication change,
  database migration, or production deployment may require policy evaluation and human approval.
tags:
- standard
- rules
phase: 04-rule-engine-orchestration
canonical_path: docs/04-rule-engine-orchestration/06-detailed-section-design.md
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

# Rule Engine and Orchestration - Detailed Section Design


## Purpose

Agents can write code, but organizations need judgment. Some changes are syntactically correct but business-dangerous. A pricing change, permissions change, authentication change, database migration, or production deployment may require policy evaluation and human approval.

## Why This Phase Exists

Agents can write code, but organizations need judgment. Some changes are syntactically correct but business-dangerous. A pricing change, permissions change, authentication change, database migration, or production deployment may require policy evaluation and human approval.

This phase turns Astloom from a memory system into an operational coordinator.

## Semantic Rules in Detail

Traditional rules are simple: if a file path matches `payment.py`, block the change. Real business rules are more subtle. A change to `base_price`, subscription interval, discount calculation, refund behavior, or invoice schema can affect revenue even if the file name does not mention payment.

Semantic rules allow policy owners to express intent in natural language. The platform then evaluates actions against those policies using deterministic checks first and LLM judgment only for ambiguous cases.

### Policy Requirements

A policy should include:

- Title.
- Natural-language rule.
- Owner.
- Severity.
- Scope.
- Examples.
- Counterexamples.
- Evaluation mode.
- Required approval path.

## LLM-as-a-Judge in Detail

The LLM Judge should not be a free-form chat. It should receive constrained evidence and return structured output.

Required output:

- Verdict: allow, warn, block, or escalate.
- Confidence.
- Rationale.
- Evidence references.
- Policy references.
- Recommended next action.

The judge must not be used for every event. It should be reserved for ambiguous semantic cases where deterministic checks are insufficient.

## Escalation in Detail

Escalation is not failure. It is the correct behavior when automation reaches a risk boundary.

A good escalation ticket includes:

- What changed.
- Why the system thinks it is risky.
- Which policy was triggered.
- What the agent intended.
- Evidence references.
- Possible outcomes.
- Rollback or mitigation plan.
- Deadline and owner.

## Hybrid Anomaly Detection in Detail

The platform should use layered detection:

1. Static checks: secrets, dangerous dependencies, schema changes, missing tests, high-risk files.
2. Statistical checks: unusual file volume, unusual agent behavior, repeated failures, high blast radius.
3. Graph checks: affected APIs, docs, owners, teams, and rules.
4. LLM review: semantic interpretation of ambiguous risk.

This keeps cost low while still catching subtle problems.

## Dependency and Impact Analysis in Detail

Impact analysis answers: if this changes, what else may break or need work?

The graph should connect changed entities to:

- API consumers.
- Frontend views.
- Mobile clients.
- Data dashboards.
- Documentation.
- Tests.
- Runbooks.
- Department workflows.
- Business policies.

When impact is confirmed, the Task Router creates downstream Tasks with ownership and acceptance criteria.

## Architecture Flow Notes

The Orchestration layer sits between work and merge/deployment. It receives events from agents, code analysis, docs drift, memory, and broker messages. It evaluates rules, estimates risk, creates tickets, routes Tasks, and records outcomes.

## Module Responsibility Notes

### Policy Parser

Turns policy text into structured evaluation metadata and examples.

### Deterministic Pre-Checker

Runs cheap checks before any model call.

### Risk Classifier

Combines severity, confidence, owner, affected domain, and historical incidents.

### Escalation Manager

Creates tickets, tracks approval status, handles timeout behavior, and records decision reason.

### Impact Analyzer

Traverses graph edges and ranks affected entities by severity and confidence.

### Task Router

Creates agent or human Tasks and subscribes owners to relevant events.

## Edge Cases

- A policy is vague: require examples and owner clarification.
- Two policies conflict: apply precedence and escalate.
- The LLM Judge has low confidence: escalate instead of allowing.
- A human approval expires: fail closed for high-risk work.
- Impact analysis generates too many tasks: apply severity thresholds and owner filters.

## Output of This Phase

At the end of this phase, Astloom can coordinate safe automation. It knows when to continue, when to warn, when to route more work, and when to stop for human judgment.
