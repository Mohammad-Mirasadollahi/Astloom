---
doc_id: as.doc.tech.rules-orchestration-technical-logic
title: Rule Engine and Orchestration Technical Logic
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: The Rule Engine and Orchestration layer decides whether automation should continue,
  warn, route downstream work, or stop for human approval. It combines deterministic checks,
  graph impact, anomaly signals, and constrained LLM judgment.
tags:
- standard
- tech
phase: 06-technical-logic
canonical_path: docs/06-technical-logic/04-rules-orchestration-technical-logic.md
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

# Rule Engine and Orchestration Technical Logic


## Purpose

The Rule Engine and Orchestration layer decides whether automation should continue, warn, route downstream work, or stop for human approval. It combines deterministic checks, graph impact, anomaly signals, and constrained LLM judgment.

## Technical Goal

The Rule Engine and Orchestration layer decides whether automation should continue, warn, route downstream work, or stop for human approval. It combines deterministic checks, graph impact, anomaly signals, and constrained LLM judgment.

## Policy Representation

A Policy should be stored as structured metadata plus natural-language rule text.

```text
Policy:
    id
    title
    natural_language_rule
    scope
    severity
    owner
    examples
    counterexamples
    evaluation_mode
    required_approval_role
    precedence
    status
```

Evaluation modes:

- `DETERMINISTIC`: pure rule or query.
- `SEMANTIC`: needs LLM judgment.
- `HYBRID`: deterministic pre-check followed by LLM only when needed.
- `MANUAL`: always requires human review.

## Evaluation Pipeline

```text
evaluate(change):
    subject = normalize_subject(change)
    policies = select_applicable_policies(subject)
    deterministic_results = run_prechecks(subject, policies)

    if deterministic_results.block:
        return BLOCK with evidence

    semantic_candidates = filter_ambiguous_policies(policies, deterministic_results)
    llm_results = judge_semantic_policies(subject, semantic_candidates)

    risk = aggregate_risk(deterministic_results, llm_results, graph_impact)

    if risk.requires_approval:
        return ESCALATE
    if risk.requires_tasks:
        return ALLOW_WITH_TASKS
    return ALLOW
```

## Deterministic Pre-Checks

Deterministic checks are cheap and should run before any LLM call.

Examples:

- changed file path matches high-risk area,
- secret pattern detected,
- database migration changed,
- public API schema changed,
- authentication or authorization module changed,
- tests missing for touched domain,
- linked docs are stale,
- owner approval missing.

## LLM Judge Constraints

The LLM Judge must receive a constrained prompt and return structured JSON. It should not be allowed to invent evidence.

Judge input:

- policy text,
- examples and counterexamples,
- normalized change summary,
- affected entities,
- evidence references,
- graph impact summary.

Judge output:

```text
verdict: ALLOW | WARN | BLOCK | ESCALATE
confidence: 0.0 - 1.0
rationale: short explanation
matched_policy_examples: list
missing_evidence: list
recommended_action: string
```

If confidence is below threshold for high-risk domains, escalate.

## Risk Aggregation Logic

```text
risk_score = max(
    policy_severity_score,
    graph_impact_score,
    anomaly_score,
    data_sensitivity_score,
    deployment_risk_score
)

if llm_confidence_low and risk_score >= HIGH:
    action = ESCALATE
elif risk_score >= CRITICAL:
    action = ESCALATE
elif risk_score >= HIGH and approval_missing:
    action = ESCALATE
elif risk_score >= MEDIUM:
    action = WARN_OR_ROUTE_TASKS
else:
    action = ALLOW
```

## Escalation Logic

Escalation tickets should be concise but evidence-backed.

Ticket creation algorithm:

```text
create_ticket(risk_result):
    summarize_change()
    attach_policy_refs()
    attach_evidence_refs()
    attach_impact_map()
    attach_recommended_options()
    assign_approver(policy.owner or domain.owner)
    set_deadline_by_severity()
    block_automation_if_required()
```

Approval outcomes:

- approved: continue workflow and record approval.
- rejected: stop workflow and create remediation Task.
- needs changes: create Task and keep original blocked.
- expired: fail closed for high-risk domains.

## Impact Traversal Logic

Impact analysis starts from changed entities and traverses graph edges.

```text
frontier = changed_entities
for depth in 1..max_depth:
    neighbors = graph.get_neighbors(frontier)
    score each neighbor by relation type and domain severity
    add high-confidence neighbors to impact map
    frontier = neighbors above traversal threshold
```

Relation weights:

- `implements`: high.
- `depends_on`: high.
- `explains`: medium.
- `owned_by`: routing only.
- `related_to`: low.
- `supersedes`: lifecycle only.

## Task Routing Logic

For every high-confidence affected domain, create a Task only if work is required.

Routing examples:

- API contract changed: frontend and mobile update Tasks.
- Data schema changed: data dashboard and migration verification Tasks.
- Security policy triggered: security review Task.
- Docs drift found: docs update Task.
- Deployment risk found: DevOps runbook Task.

Task routing must check for existing open Tasks to avoid duplication.

## Anomaly Detection Logic

Hybrid anomaly detection combines cheap signals and semantic judgment.

Signals:

- unusually many files touched,
- repeated failing commands,
- agent acting outside capability profile,
- high-risk files changed without linked Task,
- tests removed or weakened,
- docs not updated for public interface change,
- unusual dependency added.

## Failure Handling

- If policy selection fails, apply conservative default for high-risk domains.
- If LLM Judge fails, fall back to escalation when risk is medium or higher.
- If approver is unknown, route to domain owner or platform administrator.
- If impact traversal times out, return partial impact map and mark confidence incomplete.
- If task routing fails, publish routing failure and keep the parent Issue open.
