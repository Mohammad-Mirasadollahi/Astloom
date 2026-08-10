---
doc_id: as.doc.examples.rule-engine-and-human-approval-example
title: Logical Example - Rule Engine and Human Approval
doc_type: example
status: draft
schema_version: '1.0'
owner: platform-docs
summary: An agent changes pricing logic while refactoring tax code. The file name does not
  include payment, but the change affects `base_price`. The Rule Engine must detect revenue
  risk and require product approval.
tags:
- example
- examples
phase: 11-logical-implementation-examples
canonical_path: docs/11-logical-implementation-examples/04-rule-engine-and-human-approval-example.md
lifecycle_lane: current
concern_lane: example
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Logical Example - Rule Engine and Human Approval


## Purpose

An agent changes pricing logic while refactoring tax code. The file name does not include payment, but the change affects `base_price`. The Rule Engine must detect revenue risk and require product approval.

## Scenario

An agent changes pricing logic while refactoring tax code. The file name does not include payment, but the change affects `base_price`. The Rule Engine must detect revenue risk and require product approval.

## Input Change

```text
file: src/cart/tax_calculation.py
changed symbol: calculate_taxed_price
changed variable: base_price
agent intent: refactor tax calculation
```

## Policy

```text
Policy:
    title: Revenue-impacting changes require approval
    rule: Any change that can affect direct customer billing, pricing, subscription plans, discounts, refunds, or invoices must be approved by Product and Finance.
    severity: HIGH
    evaluation_mode: HYBRID
```

## Evaluation Flow

### Step 1 - Policy Selection

The Rule Engine selects revenue policies because the changed symbol references price and checkout domain.

### Step 2 - Deterministic Pre-Check

Pre-check signals:

```text
changed variable contains price: true
checkout domain affected: true
billing tests changed: false
approval present: false
```

The deterministic check raises risk but still needs semantic judgment because the agent claims it is a refactor.

### Step 3 - LLM Judge

The LLM Judge receives constrained evidence:

```text
policy text
change summary
changed variable names
affected graph nodes
agent intent
test evidence
```

Expected structured verdict:

```text
verdict: ESCALATE
confidence: 0.87
rationale: base_price affects direct customer pricing even if the file name is tax_calculation.py
recommended_action: request Product and Finance approval before merge
```

### Step 4 - Risk Aggregation

Risk is HIGH because revenue policy matched and approval is missing.

### Step 5 - Escalation Ticket

```text
EscalationTicket:
    approvers: Product Owner, Finance Owner
    status: PENDING
    options: approve, reject, request changes
    evidence_refs: diff, graph impact, RuleEvaluation
```

## Approval Outcomes

### Approved

Workflow continues. Approval is linked to merge Activity.

### Rejected

Task is blocked and remediation Task is created.

### Request Changes

Agent receives a new Task with required changes and original merge remains blocked.

### Expired

Because the change affects revenue, automation fails closed.

## Edge Cases

### Low-Confidence High-Risk

If the LLM Judge returns high risk with low confidence, the system still escalates instead of auto-approving.

### Expired Approval

When the escalation deadline passes without a decision, high-risk automation fails closed and the Task stays blocked.

### Missing Evidence

If required evidence refs are absent, structured judge output is rejected and evaluation does not proceed to approval.

## Developer Implementation Notes

- Deterministic checks should run before LLM Judge.
- LLM Judge output must be structured and evidence-bound.
- Low confidence in high-risk domains should escalate.
- EscalationTicket must preserve presented evidence and decision reason.
