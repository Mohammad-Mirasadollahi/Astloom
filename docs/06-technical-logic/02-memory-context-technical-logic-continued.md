---
doc_id: as.doc.tech.memory-context-technical-logic-continued
title: Memory and Context Technical Logic (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/06-technical-logic/02-memory-context-technical-logic.md` —
  remaining sections after the soft size budget.
tags:
- standard
- tech
phase: 06-technical-logic
canonical_path: docs/06-technical-logic/02-memory-context-technical-logic-continued.md
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

# Memory and Context Technical Logic (Continued)

## Purpose

Continuation of `docs/06-technical-logic/02-memory-context-technical-logic.md` — remaining sections after the soft size budget.

## Autonomous Question Intelligence Logic

The Memory and Context layer should include a Question Intelligence loop. This loop detects repeated questions, unanswered questions, missing documentation, and stale answers. It should decide whether to answer from existing evidence, investigate further, generate a documentation draft, create a Task, create a KnowledgeGap, or promote an answer to FAQ memory.

### Question Processing Pipeline

    on_question_asked(raw_question, actor, scope):
        scoped_question = apply_scope(raw_question, scope)
        observation = record_question_observation(scoped_question)
        normalized = normalize_question(scoped_question)
        question_memory = upsert_question_memory(normalized, observation)
        scores = compute_question_scores(question_memory)

        if scores.urgency_score >= immediate_threshold:
            request_investigation(question_memory)
        elif scores.curiosity_score >= curiosity_threshold:
            enqueue_investigation(question_memory)
        elif scores.faq_score >= faq_candidate_threshold and question_memory.has_stable_answer:
            create_faq_candidate(question_memory)
        else:
            keep_as_observed_or_candidate(question_memory)

### Evidence Search Logic

    investigate_question(question_memory):
        enforce_scope(question_memory.scope)
        evidence = []
        evidence += search_project_faq(question_memory)
        evidence += search_active_semantic_facts(question_memory)
        evidence += search_decisions(question_memory)
        evidence += search_docs_graph(question_memory)
        evidence += search_code_graph(question_memory)
        evidence += search_worklogs_issues_tasks(question_memory)
        evidence += search_rule_evaluations(question_memory)
        evidence += search_human_feedback(question_memory)

        scored_evidence = score_evidence(evidence)
        result = decide_question_outcome(question_memory, scored_evidence)
        persist_result(result)
        emit_question_events(result)

### Scope Enforcement

Question Intelligence must apply tenant, workspace, project, and project group scope before retrieval or scoring. The system must not retrieve broad memory and filter only after ranking.

## Batched Memory And Deferred Knowledge Logic

The Memory and Context layer should include a WorkBatch loop. This loop separates append-only raw evidence capture from durable knowledge actions such as memory consolidation, documentation generation, code review, FAQ promotion, and long-term memory promotion.

### Batch Processing Pipeline

    on_activity_recorded(activity):
        enforce_scope(activity.scope)
        record_raw_activity(activity)
        batch = find_or_create_work_batch(activity)
        attach_activity_to_batch(batch, activity)
        update_batch_candidates(batch, activity)
        decision = classify_batch_behavior(batch, activity)
        apply_batch_policy(batch, decision)
        persist_batch_decision(batch, decision)
        emit_batch_events(batch, decision)

### LLM Batch Classification

    classify_batch_behavior(batch, latest_activity):
        features = extract_batch_features(batch, latest_activity)
        llm_output = llm_classify(features)
        validated_output = validate_batch_decision_output(llm_output)
        return validated_output

The LLM output must include:

- batch_action.
- batch_type.
- defer_or_execute.
- deferred_actions.
- immediate_actions.
- boundary_condition.
- max_wait_time.
- confidence.
- risk_level.
- reason.
- evidence_refs.

### Policy-Constrained Decision Logic

    apply_batch_policy(batch, decision):
        if contains_secret_signal(batch):
            force_immediate_action(secret_detection)
        if destructive_action_requested(batch):
            force_immediate_action(approval_required)
        if authentication_or_authorization_changed(batch):
            force_immediate_action(security_review)
        if public_contract_changed(batch):
            create_deferred_action(documentation_generation)
            create_deferred_action(code_review)
        if decision.defer_or_execute == defer:
            create_deferred_actions(batch, decision)
        if readiness_score(batch) >= ready_threshold:
            mark_ready_for_consolidation(batch)

Policy can override the LLM recommendation. The LLM may recommend deferral, but policy determines whether deferral is allowed.

### Readiness Scoring Logic

    readiness_score(batch, profile):
        features = {
            time_since_last_edit,
            explicit_completion_signal,
            tests_finished,
            tests_passing,
            semantic_coherence,
            file_change_stability,
            risk_level,
            documentation_impact,
            code_graph_impact,
            user_instruction_strength,
            review_boundary_signal,
            max_duration_pressure
        }
        return weighted_sum(features, profile.readiness_weights)

Readiness score must include explanation. A batch should not move to ready_for_consolidation without a boundary signal or policy reason.

### Deferred Action Execution

    execute_deferred_actions(batch):
        if batch.lifecycle_state != ready_for_consolidation:
            return wait

        final_context = build_final_batch_context(batch)

        if has_deferred_action(batch, memory_consolidation):
            consolidate_memory_from_final_context(final_context)

        if has_deferred_action(batch, documentation_generation):
            generate_docs_from_final_graph_state(final_context)

        if has_deferred_action(batch, code_review):
            run_code_review_with_batch_context(final_context)

        if all_required_actions_complete(batch):
            mark_batch_completed(batch)

### Documentation Deferral Logic

    should_generate_docs_immediately(activity, batch):
        if activity_changes_public_contract:
            return true
        if activity_changes_security_or_compliance_behavior:
            return true
        if activity_changes_production_configuration:
            return true
        if user_explicitly_requested_docs:
            return true
        return false

If this function returns false, documentation generation should be represented as a DeferredAction or documentation candidate, not immediate output.

### Code Review Deferral Logic

    should_run_review_now(activity, batch):
        if high_risk_policy_triggered:
            return true
        if user_explicitly_requested_review:
            return true
        if pull_request_created:
            return true
        if task_completed and tests_finished:
            return true
        return false

### Failure Handling

- If batch state cannot be determined, create a conservative WorkBatch and defer non-critical durable actions.
- If batch exceeds maximum duration, create a consolidation Task or request user checkpoint.
- If deferred documentation generation fails, create a documentation Task with evidence references.
- If deferred review fails, create a review Task and preserve final batch context.
- If immediate policy action triggers, execute it even while the batch remains active.
- If a user forces consolidation, record the override and run with current evidence.


## Related Documents

- Parent document: `docs/06-technical-logic/02-memory-context-technical-logic.md`
