---
doc_id: as.doc.ops.impact-reporting-and-benefit-measurement-continued
title: 10 - Impact Reporting And Benefit Measurement (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/09-platform-governance-operations/10-impact-reporting-and-benefit-measurement.md`
  — remaining sections after the soft size budget.
tags:
- standard
- ops
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/10-impact-reporting-and-benefit-measurement-continued.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.1.2
updated_at: 2026-08-10
---

# 10 - Impact Reporting And Benefit Measurement (Continued)

## Purpose

Continuation of `docs/09-platform-governance-operations/10-impact-reporting-and-benefit-measurement.md` — remaining sections after the soft size budget.

## KPI 6: Dead-Code Cleanup

### Definition

Dead-code cleanup measures whether Astloom-guided coding sessions remove orphaned predecessors when agents replace or retire behavior — not only whether they add new code. Astloom surfaces **scored** candidates (`score`, `evidence`, `finding_kind`, `kpi_hints`) and records evidence; external agents perform deletes. Normative loop: [`../07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md`](../07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md).

Recommended KPIs:

- dead_code_candidates_surfaced (echoed on MCP as `kpi_hints.dead_code_candidates_surfaced`).
- dead_code_candidates_resolved (removed after proof in the same task; prefer rows that were `safe_to_delete` with `score ≥ 0.8`; MCP echoes `kpi_hints.dead_code_candidates_resolved=0` as a write-back placeholder).
- dead_code_candidates_skipped_uncertain (echoed on MCP as `kpi_hints.dead_code_candidates_skipped_uncertain`).
- orphaned_symbols_remaining (delta in task neighborhood after coding tasks with cleanup guidance).
- unused_loc_removed_net (optional; unused LOC removed vs LOC added in the same task).
- cleanup_verify_pass_rate (smallest verification passed after delete).

### Instrumentation

- Graph unused-candidate query before/after task scope (`astloom_code_graph_unused_candidates`).
- Activity / WorkLog fields: paths removed, candidate ids, blockers skipped, optional score/evidence snapshot.
- Test or acceptance outcome linked to the same task id.
- Freshness / pending-sync / `index_coverage.safe_absence_claims` on the candidate snapshot.

### Data Sources

- Code-Knowledge Graph snapshots.
- `astloom_code_graph_unused_candidates` results (`candidates`, `skipped_uncertain`, `kpi_hints`).
- Activity and WorkLog cleanup payloads.
- CI / smallest verification commands recorded on the task.
- Guidance resolve evidence that cleanup skill/rule applied.

### Interpretation Rules

- Cleanup without regressions (tests/acceptance) counts as positive benefit.
- Blind deletes without proof do **not** count toward `dead_code_candidates_resolved`.
- Uncertain skips are healthy when blockers are dynamic/public or `test_only`; they are not failures.
- Low-score / triage-only rows must not be counted as resolved until graph proof and verification exist.
- Compare with and without cleanup guidance / unused-candidate capability using feature_flag_split or agent_workflow_comparison.

### Evidence Drilldown

- task_id, candidate symbol/path, confidence, blockers, deleted paths, verify command, freshness.

## Reporting Data Model

### MetricDefinition

Recommended contract:

    MetricDefinition:
        metric_id
        name
        family
        description
        numerator_definition
        denominator_definition
        unit
        aggregation_method
        required_scope_fields
        required_evidence_types
        owner
        version
        status

### MeasurementRun

Recommended contract:

    MeasurementRun:
        run_id
        metric_ids
        tenant_id
        workspace_id
        project_id
        project_group_id
        time_range
        baseline_range
        comparison_method
        feature_flags
        sample_size
        exclusions
        generated_at
        generated_by
        confidence_notes

### MetricResult

Recommended contract:

    MetricResult:
        result_id
        run_id
        metric_id
        scope
        value
        baseline_value
        delta_absolute
        delta_percent
        direction
        confidence_level
        caveats
        evidence_refs

### ReportEvidenceRef

Recommended contract:

    ReportEvidenceRef:
        evidence_id
        evidence_type
        source_ref
        metric_id
        contribution_type
        timestamp
        scope

## Reporting Events

Recommended events:

- reporting.measurement_requested
- reporting.measurement_completed
- reporting.metric_definition_changed
- reporting.baseline_created
- reporting.dashboard_viewed
- reporting.report_exported
- reporting.evidence_drilldown_opened
- reporting.caveat_acknowledged

Event rules:

- Events must include project or project group scope.
- Exported reports must include metric definitions and caveats.
- Evidence drilldown should be auditable for sensitive projects.

## Instrumentation Requirements

The system must instrument these lifecycle events:

- task created.
- task started.
- first code draft created.
- first test run started.
- first passing test recorded.
- review-ready state reached.
- review defect recorded.
- test defect recorded.
- release defect recorded.
- task reopened.
- task completed.
- WorkBatch opened.
- WorkBatch completed.
- ContextBundle built.
- prompt cache hit or miss.
- memory item retrieved.
- question observed.
- FAQ answer reused.
- documentation drift detected.
- architecture boundary violation detected.

Without instrumentation, the report should mark the metric as incomplete rather than silently estimating.

## Dashboard Requirements

Dashboards should include:

- executive summary.
- project-level comparison.
- project group comparison.
- before and after view.
- feature flag comparison.
- metric family tabs.
- time range selector.
- baseline selector.
- evidence drilldown.
- caveat panel.
- export action.
- metric definition view.

Dashboard states:

- loading.
- no_data.
- partial_data.
- insufficient_baseline.
- permission_denied.
- scoped_project_view.
- scoped_project_group_view.
- stale_instrumentation.
- ready.

## Product Experience

The reporting UI should make metrics trustworthy.

Each chart should show:

- metric definition.
- current value.
- baseline value.
- delta.
- trend.
- sample size.
- scope.
- time range.
- caveats.
- evidence link.

Users should be able to:

- select scope.
- select baseline.
- compare with and without Astloom.
- compare feature flags.
- drill into evidence.
- export report.
- mark caveat acknowledged.
- create a follow-up Task from a bad metric.
- create a Gap when measurement is incomplete.

## Example: With And Without Astloom Report

Scenario:

- Project A used Astloom for four weeks.
- The previous four weeks are used as baseline.
- Task complexity is segmented into small, medium, and large.

Report output:

- initial code generation speed improved 22 percent for medium tasks.
- escaped defects decreased 18 percent.
- review-time defects increased 9 percent, explained as earlier detection.
- dependency boundary violations decreased 35 percent.
- reopened tasks decreased 14 percent.
- total tokens per accepted patch decreased 28 percent.
- caveat: sample size for large tasks is low.

The report must link every number to MeasurementRun, MetricResult, and evidence references.

## Anti-Metrics And Misuse Risks

Avoid these mistakes:

- counting generated lines of code as productivity without quality checks.
- claiming bug reduction when only detection moved earlier.
- treating lower token usage as success when corrections increased.
- comparing unrelated projects without normalization.
- hiding incomplete instrumentation.
- aggregating tenant or project data without authorization.
- using reports to punish teams instead of improving workflows.

## Acceptance Criteria

Impact reporting is acceptable when:

- reports cover initial code generation speed, bug reduction, architecture quality, rework reduction, and token consumption.
- each metric has a formal definition, owner, unit, evidence type, and aggregation method.
- every report declares scope, baseline, comparison method, time range, sample size, and caveats.
- reports can compare with and without Astloom or with and without specific Astloom capabilities.
- metrics are segmented by project, project group, agent, repository, task type, complexity, and time range where data allows.
- dashboards allow drilldown from summary metric to source evidence.
- incomplete instrumentation is shown explicitly.
- token savings are evaluated together with success rate, correction rate, bug rate, and rework rate.
- project isolation rules are enforced for all reports.


## Related Documents

- Parent document: `docs/09-platform-governance-operations/10-impact-reporting-and-benefit-measurement.md`
