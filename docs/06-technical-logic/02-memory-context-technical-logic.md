---
doc_id: as.doc.tech.memory-context-technical-logic
title: Memory and Context Technical Logic
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: The Memory and Context layer transforms structured records into agent-usable context.
  Its technical responsibility is to decide what should be remembered, what should be forgotten
  by default, what should be retrieved, and how context should be packed into prompts without
  wasting .
tags:
- standard
- tech
phase: 06-technical-logic
canonical_path: docs/06-technical-logic/02-memory-context-technical-logic.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
placeholder: 1
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Memory and Context Technical Logic

## Memory and Context Technical Logic
## Purpose

The Memory and Context layer transforms structured records into agent-usable context. Its technical responsibility is to decide what should be remembered, what should be forgotten by default, what should be retrieved, and how context should be packed into prompts without wasting .

## Technical Goal

The Memory and Context layer transforms structured records into agent-usable context. Its technical responsibility is to decide what should be remembered, what should be forgotten by default, what should be retrieved, and how context should be packed into prompts without wasting tokens or injecting stale truth.

## Memory Type Classifier

Every candidate memory item is classified into one of these types:

- `WORKING`: temporary session context.
- `EPISODIC`: historical event or completed work.
- `SEMANTIC`: durable current truth or rule.
- `RESTRICTED`: sensitive memory requiring access control.
- `DEPRECATED`: no longer active but retained for audit.

Classifier input signals:

- source entity type,
- owner domain,
- evidence confidence,
- linked code existence,
- linked Decision status,
- sensitivity score,
- expected half-life,
- retrieval frequency.

Classification logic:

```text
if contains_secret or sensitive_customer_data:
    type = RESTRICTED
elif active_decision or current_architecture_fact:
    type = SEMANTIC
elif task_is_active:
    type = WORKING
elif event_is_completed:
    type = EPISODIC
elif linked_entity_is_deleted_or_superseded:
    type = DEPRECATED
```

## Consolidation Logic

Consolidation turns many low-level events into fewer high-value facts.

Inputs:

- Activities,
- WorkLogs,
- Decisions,
- Issues,
- Tasks,
- test results,
- docs drift findings,
- approvals.

Outputs:

- SemanticFacts,
- deprecated facts,
- unresolved knowledge gaps,
- prompt cache invalidation events.

Consolidation algorithm:

```text
collect events for time_window or completed_task
cluster events by affected_entity and intent
remove duplicate retries and failed intermediate attempts
extract final state and durable constraints
compare with existing SemanticFacts
create new facts or supersede old facts
mark source event references
emit memory.consolidation_completed
```

## Current State Resolution

The platform should resolve current state through active SemanticFacts and active Decisions.

Resolution priority:

1. Human-approved active Decision.
2. Verified deployment or merge state.
3. Latest completed Task with passing acceptance checks.
4. Consolidated WorkLog with evidence.
5. Low-confidence inferred fact.

If two facts conflict, the system should not choose randomly. It should create a conflict record or escalation.

## Retrieval Scoring

Context retrieval should rank candidate memory items by relevance, authority, freshness, and risk.

```text
score =
    semantic_similarity * 0.30 +
    graph_distance_score * 0.25 +
    authority_score * 0.20 +
    freshness_score * 0.10 +
    risk_relevance_score * 0.10 +
    usage_success_score * 0.05
```

Penalty factors:

- deprecated status,
- low confidence,
- access restriction,
- conflicting active fact,
- excessive token size,
- irrelevant domain.

## Graph-Aware Retrieval

Vector search alone is insufficient. The retriever should combine graph traversal and semantic search.

Retrieval flow:

1. Start from Task, Issue, code symbol, or policy subject.
2. Traverse graph edges to linked Decisions, Docs, Rules, owners, and previous Tasks.
3. Run semantic search for additional related MemoryItems.
4. Merge results and remove duplicates.
5. Apply access control.
6. Rank using retrieval score.
7. Summarize large documents when token budget is limited.

## Prompt Packing Logic

Prompt sections should be packed in this order:

1. Stable cached architecture and policy section.
2. Active current-state facts for the task domain.
3. Task instructions and acceptance criteria.
4. Relevant Decisions and Rules.
5. Relevant docs and code anchors.
6. Recent errors or command outputs.
7. Optional history only when requested or needed.

Token budget policy:

```text
reserve 25 percent for model output
reserve 15 percent for task instructions
reserve 25 percent for current state and rules
reserve 20 percent for code and docs
reserve 10 percent for recent evidence
reserve 5 percent for safety margin
```

## Prompt Cache Invalidation

Static prompt cache should invalidate only when stable content changes.

Invalidation triggers:

- organization policy update,
- global architecture update,
- active high-level Decision change,
- tenant security rule change,
- context schema version change.

Non-invalidation triggers:

- task-specific error output,
- local file snippet,
- single drift finding,
- temporary command output.

## Decay and Garbage Collection Logic

Decay should reduce default prompt noise without destroying audit history.

Decay score:

```text
decay_score =
    age_weight +
    missing_link_weight +
    superseded_weight +
    low_usage_weight +
    owner_deprecation_weight -
    compliance_retention_weight -
    security_importance_weight
```

Actions by score:

- low score: keep active.
- medium score: keep active but reduce retrieval priority.
- high score: mark deprecated and exclude from default prompts.
- restricted high score: archive with retention policy.

## ContextBundle Contract

A ContextBundle must include:

- task ID,
- retrieval query,
- included MemoryItem IDs,
- included Decision IDs,
- included Doc IDs,
- static prompt version,
- token budget,
- redaction status,
- omitted high-scoring items with reason.

## Failure Handling

- If retrieval confidence is low, ask for clarification or escalate rather than injecting weak context.
- If token budget is exceeded, summarize and preserve source references.
- If current-state facts conflict, block automatic context generation for high-risk tasks.
- If prompt cache version is unknown, rebuild static section and record invalidation.

## Configurable Memory Weighting Logic

Memory retrieval and decay must use configurable weighting profiles. The application logic may define feature names and scoring flow, but it must not hard-code final weights. Weights should be loaded from a versioned policy profile and selected by tenant, project, domain, task type, risk level, and agent role.

## Weight Profile Contract

A WeightProfile should include:

```text
WeightProfile:
    profile_id
    tenant_id
    domain
    task_type
    risk_level
    version
    feature_weights
    thresholds
    retention_overrides
    owner
    status
    created_at
    updated_at
```

Example feature names:

```text
recency
usage_frequency
successful_reuse
semantic_similarity
graph_distance
graph_centrality
evidence_strength
domain_criticality
human_verified
conflict_penalty
deprecation_penalty
restricted_access_penalty
incident_recovery_value
```

The values assigned to these features must come from the active WeightProfile, not from code constants.

## Profile Selection Logic

```text
select_weight_profile(request):
    candidates = profiles where tenant_id matches request.tenant_id
    candidates = filter by project_id if project profile exists
    candidates = filter by domain if domain profile exists
    candidates = filter by task_type if task profile exists
    candidates = filter by risk_level if risk-specific profile exists
    return highest_specificity_active_profile(candidates)
```

Specificity order:

1. tenant + project + domain + task_type + risk_level,
2. tenant + project + domain + task_type,
3. tenant + domain,
4. tenant default,
5. platform default.

## Weighted Retrieval Formula

The formula should be data-driven:

```text
score(memory_item, request, profile):
    features = extract_features(memory_item, request)
    total = 0
    for feature_name, feature_value in features:
        weight = profile.feature_weights.get(feature_name, 0)
        total += normalize(feature_value) * weight
    total -= apply_penalties(memory_item, request, profile)
    total += apply_boosts(memory_item, request, profile)
    return clamp(total, 0, 1)
```

The code can define `extract_features`, `normalize`, `apply_penalties`, and `apply_boosts`, but the numeric weight values and thresholds should be profile-driven.

## Forgotten Memory Classification Logic

A low-scoring memory item should not automatically be deleted. It should be classified.

```text
classify_low_visibility_memory(item):
    if linked_code_missing or superseded_by_active_decision:
        return OBSOLETE
    if domain_criticality_high or incident_recovery_value_high:
        return DORMANT_BUT_IMPORTANT
    if evidence_strength_high and graph_degree_low:
        return UNDER_LINKED
    if conflicts_with_active_fact:
        return CONFLICTING
    if evidence_strength_low and usage_frequency_low:
        return LOW_CONFIDENCE
    return LOW_PRIORITY
```

Actions:

- `OBSOLETE`: mark deprecated and exclude from default prompts.
- `DORMANT_BUT_IMPORTANT`: retain, lower default rank, boost for incident/security/recovery contexts.
- `UNDER_LINKED`: create graph repair or documentation linking Task.
- `CONFLICTING`: create review or supersession workflow.
- `LOW_CONFIDENCE`: keep out of default prompts unless explicitly requested.
- `LOW_PRIORITY`: keep searchable but low ranked.

## Dynamic Decay Formula

Decay should be profile-driven and multi-signal:

```text
decay_score(item, profile):
    features = {
        age,
        missing_link_strength,
        supersession_strength,
        low_usage_duration,
        owner_deprecation_signal,
        compliance_retention_need,
        security_importance,
        incident_recovery_value,
        human_verified
    }
    return weighted_sum(features, profile.decay_weights)
```

A high age value alone must never be enough to delete or hide critical memory.

## Feedback Loop

After an agent run, the system should record whether retrieved memory was useful.

Feedback sources:

- task completed successfully,
- agent cited the memory in final output,
- human reviewer accepted or rejected the result,
- generated code passed tests,
- policy violation was avoided,
- incident response used the memory.

This feedback updates `successful_reuse`, `usage_quality`, and future retrieval ranking. The feedback update should change memory metrics, not hard-coded weights.

## Guardrails

- Compliance and security retention rules override decay.
- Restricted memory cannot be boosted into unauthorized contexts.
- Conflicting memory cannot be injected as current truth.
- Low-confidence generated memory must not outrank human-approved Decisions.
- WeightProfile changes must be audited and versioned.
- Agents should be able to explain why a memory item was retrieved or excluded.

## Related Documents

- Continued in `docs/06-technical-logic/02-memory-context-technical-logic-continued.md`
