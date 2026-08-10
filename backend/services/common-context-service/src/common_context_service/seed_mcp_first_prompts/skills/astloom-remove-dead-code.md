---
name: astloom-remove-dead-code
description: Prove and delete orphaned symbols, imports, and exclusive tests after a replace or retire.
---

# Astloom remove dead code

## When

- After implement/replace/retire leaves old symbols, imports, re-exports, or exclusive tests.
- Cleanup request in the scope already touched.
- Unused-candidate MCP / explore shows safe deletes nearby.
- Quality-audit category `code.dead_code_cleanup_hint` fires after sync inventory.

## How

1. **Same change:** after replace/retire, call `astloom_code_graph_unused_candidates` before treating the task done. Default `scope_mode=task_neighborhood` (or `changed_symbols` with anchors). Prefer that over whole-repo discovery.
2. For ranked discovery only, use `project_scan` with `min_confidence` (agents acting on deletes: `0.8`) and prefer `path_prefix` to one package/directory so coverage stays actionable. Pass `repo_root` when classifying `backend/packages/` (wire signals). Optional: `disk_search`, `coverage_hits`, `flag_states`, `triage`. Else explore + `rg` on bare names and import paths.
3. Read `score`, `confidence` tier, `evidence`, `finding_kind`, and `recommendation` on each row. **Act only** on `safe_to_delete` with `score ≥ 0.8` and empty hard blockers. For `unwired_shared_package` / `zombie_package`: follow `wire` / `keep_public` / `retire` — never treat as safe delete. Skip uncertain / blocked rows (optionally open a human Task — do **not** store candidates in Memory as SoT; the graph is the truth).
4. Treat each candidate as **live until proven**: dynamic loaders, string registries, public HTTP/IAM/SDK exports, `test_only`, entrypoints, `tsoc-defer`, ambiguous/`unresolved` CALLS, cross-package callers outside `path_prefix`, shared-package recommendations.
5. Delete only proven-unused symbols **and** their exclusive tests, fixtures, barrels, and docs that only described them — in the **same** change as the replace when possible.
6. Do not widen into unrelated refactors; avoid whole-repo deletes from a casual `project_scan` without `path_prefix`.
7. Verify with the smallest check that would fail if the delete were wrong.
8. Record Activity/WorkLog using MCP `kpi_hints` field names: `dead_code_candidates_surfaced`, `dead_code_candidates_resolved`, `dead_code_candidates_skipped_uncertain`.
9. List skipped uncertain symbols + blockers + evidence in the chat summary. Optional `triage=true` is advisory only and cannot raise `safe_to_delete`.

Normative: `docs/07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md` and `docs/07-code-knowledge-graph/79-shared-package-wiring-and-unwired-findings.md`.

## Do not

- Ask Astloom to delete files — it only surfaces candidates.
- Treat Memory / chat notes as a durable unused-candidate queue (recompute from the graph).
- Delete public APIs, plugin hooks, `tsoc-defer` stopgaps, or `unwired_shared_package` rows without an explicit wire/retire plan.
- Count unproven deletes as successful cleanup.
- Trust LLM triage alone over graph evidence.
