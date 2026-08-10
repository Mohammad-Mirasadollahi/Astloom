---
doc_id: as.doc.ops.impact-reporting-and-benefit-measurement
title: 10 - Impact Reporting And Benefit Measurement
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom must prove its value with measurable, auditable, scope-aware reporting.
tags:
- standard
- ops
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/10-impact-reporting-and-benefit-measurement.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
placeholder: 1
doc_version: 1.2.1
updated_at: 2026-08-10
---

# 10 - Impact Reporting And Benefit Measurement

## Purpose

Astloom must prove its value with measurable, auditable, scope-aware reporting. The platform should help teams compare engineering outcomes with Astloom enabled versus disabled, or with specific Astloom capabilities enabled versus disabled. Reports must show whether the platform improves initial code generation speed, bug reduction, architecture quality, rework reduction, token consumption, dead-code cleanup after AI coding changes, and stale-documentation cleanup after code or docs edits.

This document defines the measurement framework, KPI definitions, event instrumentation, baseline strategy, comparison methodology, dashboard requirements, evidence model, interpretation rules, and acceptance criteria.

## Corrected Requirement

The raw user requirement can be formalized as follows:

Astloom must include an impact reporting system that measures the practical difference between using and not using the platform. The system should not only show activity counts. It should measure outcome quality and engineering efficiency across defined scopes. The required metrics are initial code generation speed, bug reduction, architecture quality, rework reduction, token consumption, dead-code cleanup, and stale-documentation cleanup. Each metric must have a clear definition, data source, baseline, time range, project scope, confidence caveat, and evidence drilldown.

The reporting system should be useful for engineering leaders, product owners, platform operators, and architects who need to decide whether Astloom is improving real delivery outcomes or only adding process overhead.

## Professional Audience

This document is written for:

- engineering leaders measuring productivity and quality.
- software architects measuring architecture health and boundary integrity.
- platform operators measuring adoption, reliability, and token efficiency.
- product managers measuring workflow improvements and bottlenecks.
- data analysts building dashboards and metric pipelines.
- finance or operations stakeholders evaluating AI tool cost and benefit.
- security and governance reviewers validating evidence and auditability.

## Measurement Principles

Reporting must follow these principles:

- Measure outcomes, not only activity.
- Always show scope, baseline, and time range.
- Never mix unrelated projects without explicit ProjectGroup scope.
- Segment results by task complexity where possible.
- Pair speed metrics with quality metrics.
- Pair token savings with success and correction metrics.
- Link aggregate numbers to evidence.
- Separate early detection from defect creation.
- Make caveats visible instead of hiding uncertainty.
- Avoid claiming causality when only correlation is available.

## Required Business Questions

The reporting system should answer:

- Did initial code generation become faster.
- Did bugs decrease or shift earlier in the lifecycle.
- Did architecture quality improve.
- Did rework decrease.
- Did token consumption decrease.
- Did documentation drift decrease.
- Did repeated questions decrease after FAQ memory and documentation generation.
- Did agent work become easier to audit.
- Did project context retrieval become more accurate.
- Did dead-code cleanup increase after coding tasks (orphans removed, not only code added).
- Did automation overhead exceed measured benefit.

## Metric Families

| Metric Family | Primary Question | Required Output |
| --- | --- | --- |
| Initial Code Generation Speed | How fast does a task reach first useful implementation | duration, percentile, baseline delta, evidence |
| Bug Reduction | Are fewer defects introduced or escaping | defect counts, severity, phase found, baseline delta |
| Architecture Quality | Is the system becoming structurally healthier | boundary violations, coupling, contract drift, decisions, orphaned symbols |
| Rework Reduction | Is repeated work decreasing | reopen rate, duplicate work, repeated fixes, repeated questions |
| Token Consumption | Is context and model usage more efficient | tokens, cost, cache hit, useful context ratio, quality guardrail |
| Dead-Code Cleanup | Are AI coding changes leaving less orphaned code | candidates resolved, orphans remaining, evidence |
## Scope Model

Every report must declare scope.

Required scope fields:

- tenant_id.
- workspace_id.
- project_id or project_group_id.
- included repositories.
- included agents.
- included human roles.
- included task types.
- included feature flags.
- excluded data.
- time range.
- baseline window.
- comparison method.

A report that aggregates across projects without explicit ProjectGroup policy is invalid.

## Baseline And Comparison Methods

Astloom should support multiple comparison methods.

| Method | Description | Best Use |
| --- | --- | --- |
| before_after_project | compare project before and after Astloom adoption | early rollout |
| control_project | compare similar project with no Astloom | stronger organizational comparison |
| feature_flag_split | compare same project with a feature enabled or disabled | feature impact measurement |
| agent_workflow_comparison | compare agent workflow with and without memory, docs, or rules | subsystem evaluation |
| manual_vs_agent_assisted | compare human-only or manual workflow to Astloom-assisted workflow | productivity analysis |
| cohort_by_task_type | compare similar task classes | reducing complexity bias |

Every comparison must state limitations.

Common limitations:

- task complexity differs.
- team maturity differs.
- repository maturity differs.
- release phase differs.
- measurement instrumentation changed.
- small sample size.
- quality moved from late detection to early detection.

## KPI 1: Initial Code Generation Speed

### Definition

Initial code generation speed measures how quickly a task reaches first useful implementation. It should not only measure first output. It should measure output that reaches a meaningful engineering state.

Recommended KPIs:

- time_to_first_code_draft.
- time_to_first_compilable_state.
- time_to_first_test_run.
- time_to_first_passing_test.
- time_to_review_ready_state.
- time_to_first_accepted_patch.
- clarification_cycles_before_first_draft.

### Required Segmentation

Segment by:

- project.
- repository.
- agent type.
- task type.
- complexity band.
- risk level.
- new feature vs bug fix vs refactor.
- language or framework.

### Data Sources

- TaskCreated event.
- WorkBatch opened and completed events.
- Activity records.
- code graph change events.
- test run events.
- review-ready events.
- PR or patch events.
- WorkLog summaries.

### Interpretation Rules

- Faster first draft is positive only if bug, rework, and review rejection metrics do not worsen.
- First text output should not count as implementation speed unless it produces code evidence.
- Exploratory tasks should be reported separately from well-scoped implementation tasks.

## KPI 2: Bug Reduction

### Definition

Bug reduction measures whether Astloom reduces defects or moves detection earlier in the lifecycle.

Recommended KPIs:

- defects_found_in_review.
- defects_found_by_tests.
- escaped_defects_after_release.
- regression_count.
- severity_weighted_defect_score.
- bug_reopen_rate.
- policy_prevented_bug_count.
- security_issue_prevented_count.

### Defect Phase Classification

Each bug should include phase found:

- during_generation.
- during_agent_self_review.
- during_automated_tests.
- during_human_review.
- during_staging.
- after_release.
- during_incident.

Early detection may increase reported defects while reducing escaped defects. Reports must explain this.

### Data Sources

- Issue records.
- test reports.
- CI failures.
- review comments.
- rule evaluations.
- incident records.
- audit evidence.
- rollback events.

### Interpretation Rules

- An increase in review-time defects can be good if release-time defects decrease.
- Defect counts should be severity-weighted.
- Bug reduction should be measured per task complexity band.

## KPI 3: Architecture Quality

### Definition

Architecture quality measures whether Astloom helps preserve modularity, contract integrity, documentation alignment, and system design coherence.

Recommended KPIs:

- dependency_boundary_violation_count.
- forbidden_import_count.
- circular_dependency_count.
- contract_drift_count.
- undocumented_public_api_count.
- stale_architecture_decision_count.
- unresolved_architecture_gap_count.
- code_graph_modularity_score.
- service_ownership_coverage.
- docs_to_symbol_coverage.
- migration_risk_score.
- orphaned_symbols_remaining (task-neighborhood unused candidates still present after coding tasks that enabled cleanup guidance).
- dead_code_candidates_resolved (scored unused candidates removed after proof in the same agent task; see dead-code cleanup loop).
- stale_docs_candidates_surfaced (scored stale-documentation candidates returned by `astloom_docs_stale_candidates`).
- stale_docs_candidates_resolved (docs remediated or retired after proof in the same agent task; see stale-docs cleanup loop).
- stale_docs_candidates_skipped_uncertain (candidates left for human Task / blockers).

### Architecture Health Dimensions

Dimensions:

- modularity.
- coupling.
- contract stability.
- documentation coverage.
- decision traceability.
- ownership clarity.
- migration safety.
- project isolation compliance.
- orphan debt (proven-unused symbols left after AI replace/retire).
- stale-doc debt (orphan/ghost/superseded docs left after AI replace/retire or doc edits).

### Data Sources

- code graph snapshots.
- unused-candidate query results (`astloom_code_graph_unused_candidates` with `score` / `evidence` / `finding_kind` / `kpi_hints`, including `dead_code_candidates_resolved` placeholder for Activity write-back).
- stale-doc candidate query results (`astloom_docs_stale_candidates` with `score` / `evidence` / `finding_kind` / `kpi_hints`, including `stale_docs_candidates_resolved` placeholder for Activity write-back).
- dependency boundary checks.
- docs graph.
- contract registry.
- decision records.
- gap analysis.
- CI architecture checks.
- review outcomes.
- Activity / WorkLog cleanup fields (paths removed, candidate ids).

### Interpretation Rules

- Architecture quality is not a single subjective score.
- Composite scores must show component metrics.
- Boundary violations should be normalized by repository size and change volume.
- A temporary increase in gaps can be positive if it means hidden risks became visible.
- Dead-code cleanup counts only when proof + verification occurred; blind deletes do not improve architecture quality scores.

## KPI 4: Rework Reduction

### Definition

Rework reduction measures whether Astloom reduces repeated effort, duplicate fixes, repeated questions, reopened tasks, and avoidable rediscovery.

Recommended KPIs:

- reopened_task_rate.
- duplicate_task_count.
- repeated_fix_count.
- revert_count.
- repeated_question_count.
- repeated_documentation_drift_count.
- repeated_rule_false_positive_count.
- repeated_connector_failure_count.
- correction_rate_for_agent_outputs.
- time_spent_on_clarification.
- orphaned_predecessor_left_behind_rate (replace/retire tasks that leave unused candidates in the changed neighborhood).

### Data Sources

- Task history.
- WorkBatch history.
- WorkLog records.
- QuestionMemory records.
- documentation drift records.
- git activity summaries.
- rule feedback.
- connector validation history.
- human correction records.
- dead-code cleanup Activity fields (candidates surfaced vs resolved).
- stale-docs cleanup Activity fields (`stale_docs_candidates_surfaced` / `resolved` / `skipped_uncertain`; do not double-count the same remediation with `repeated_documentation_drift_count`).

### Interpretation Rules

- Rework should decrease after memory consolidation, QuestionMemory, FAQ memory, docs sync, and stronger contracts become active.
- Reopened tasks should be separated into legitimate scope changes versus quality failures.
- Leaving orphaned predecessors after AI replace/retire counts as rework debt even when the new behavior works.
- Repeated questions should be segmented by unanswered, answered, stale, and FAQ-promoted status.

## KPI 5: Token Consumption

### Definition

Token consumption measures how efficiently Astloom uses model context and model calls while preserving or improving output quality.

Recommended KPIs:

- total_tokens_per_task.
- input_tokens_per_task.
- output_tokens_per_task.
- tokens_per_successful_patch.
- tokens_per_accepted_review.
- tokens_per_documentation_update.
- prompt_cache_hit_rate.
- context_bundle_size.
- useful_context_ratio.
- discarded_context_ratio.
- repeated_question_token_cost.
- model_tier_mix.
- estimated_model_cost.

### Quality Guardrails

Token savings are valid only when quality does not degrade.

Pair token metrics with:

- task success rate.
- human correction rate.
- bug rate.
- rework rate.
- answer confidence.
- review rejection rate.

### Data Sources

- model provider usage records.
- prompt assembly logs.
- ContextBundle records.
- prompt cache events.
- Memory retrieval logs.
- QuestionMemory records.
- WorkBatch records.
- task outcome records.

### Interpretation Rules

- Lower tokens are not automatically better.
- Token savings should be compared against task success and defect outcomes.
- Reports should separate deterministic context reduction from model quality degradation.

## Related Documents

- Continued in `docs/09-platform-governance-operations/10-impact-reporting-and-benefit-measurement-continued.md`
