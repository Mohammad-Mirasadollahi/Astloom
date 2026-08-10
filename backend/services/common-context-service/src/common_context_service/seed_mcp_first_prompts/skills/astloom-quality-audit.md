---
name: astloom-quality-audit
description: >-
  Run astloom_quality_audit (MCP) or CLI; remediate high/medium findings same turn.
---

# Astloom quality audit

## When

- Session start (after guidance resolve).
- After material code or product-doc edits.
- User asks what is broken / nonconforming / stale.
- Sync skipped nonconforming paths or wrote `.astloom/quality-followup-tasks.json`.

## How

1. Call MCP `astloom_quality_audit` (optional `severities=["high","medium"]`). Prefer MCP over inventing a local scan.
2. If `must_remediate` is true:
   - Docs findings → skill `astloom-standards-on-edit` / `astloom-documentation-authoring`; fix each path (soft size = split sibling; linking = evidence `linked_symbols`; revision = bump stamps with body).
   - Code never-ingested / stale → run `astloom sync` for those paths (AST-only if cloud LLM blocked); do not leave debt silent.
3. Re-call `astloom_quality_audit` until high/medium are clear, or create durable tasks (`create_tasks=true` or `astloom_create_task`) with the finding list. Prefer `reconcile_tasks=true` (implied by create) so cleared debt cancels.
4. CLI fallback when MCP tool missing: `astloom quality-audit` / `astloom docs-standards`.
5. Inspect / lifecycle ops: `astloom followup-tasks list|status|reconcile|purge`; one-time `adopt-legacy` for pre-lifecycle `Quality:` Tasks.

## Do not

- Skip the audit at session start when the tool is on the effective profile.
- Treat Body-tier docs-sync validate as Full-tier / quality-audit.
- Leave `docs.size_soft` or linking gaps as “warnings only” without remediation or a durable task.
- Assume Astloom will edit the repo — you remediate; Astloom reports and stores tasks.
