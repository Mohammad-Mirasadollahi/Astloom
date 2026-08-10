---
name: astloom-remove-stale-docs
description: Prove and remediate orphaned, ghost-linked, hash-stale, wiki-orphan, or duplicate-authority documentation after code or docs changes.
---

# Astloom remove stale docs

## When

- After replace/retire of code that had exclusive human docs.
- After material doc edits, drift findings, or linking-gap quality-audit rows.
- Quality-audit category `docs.stale_cleanup_hint` fires after sync inventory.
- Rows with `finding_kind` in `wiki_orphan` / `duplicate_authority` appear.

## How

1. Call `astloom_docs_stale_candidates` (default `scope_mode=task_neighborhood`). For discovery use `project_scan` with `path_prefix` and `min_confidence` (destructive act: `0.8`).
2. Prefer `safe_to_update` and `safe_to_unlink` over `safe_to_delete`. Act only when score ≥ 0.8 and blockers empty. `wiki_orphan` and `duplicate_authority` never auto-delete — add anchors / declare `related_docs` or open a Task.
3. Prove with catalog lanes, `rg` on `doc_id` / path citations, and Related Documents. Never invent `DOCUMENTED_BY`.
4. Remediations: refresh anchors/body, fix `linked_symbols`, mark `historical` + `superseded_by`, split duplicate SoT, or delete true orphans — in the **same** change when possible.
5. Skip uncertain / normative-current (open a Task if needed). Graph + docs registry are SoT — **not** Memory.
6. Verify with `astloom docs-standards` / quality-audit on touched paths.
7. Record Activity/WorkLog using `kpi_hints`: `stale_docs_candidates_surfaced`, `stale_docs_candidates_resolved`, `stale_docs_candidates_skipped_uncertain`.

## Do not

- Ask Astloom to delete Markdown — it only surfaces candidates.
- Treat Memory as a durable stale-doc queue.
- Delete normative `lifecycle_lane: current` standards without human Task.
- Trust triage alone over evidence.
