---
name: astloom-docs-sync
description: Run Astloom docs-sync drift, status, Body-tier validate, note, draft, and index via MCP.
---

# Astloom docs sync

## When

- Docs drift / coverage (docs-as-code).
- Body-tier validate / note / draft / index via MCP.
- Scored stale-doc candidates after linking gaps or code replace/retire with exclusive docs.

## How

1. **Before** writing or explaining product Markdown: `astloom_docs_authoring_standards` + skill `astloom-documentation-authoring` (Full-tier).
2. Which docs to open: `astloom_docs_catalog` (optional `refresh`, filters).
3. Coverage/gaps: `astloom_docs_status`.
4. Symbol drift: `astloom_docs_drift_check` (`symbol`, optional `file_path`).
5. Stale candidates: `astloom_docs_stale_candidates` (default `task_neighborhood`; discovery via `project_scan` + `path_prefix`). Prefer skill `astloom-remove-stale-docs` for act policy.
6. Write: `astloom_docs_write` `mode` = `validate` | `note` | `draft` | `index`.
7. Committed docs: English only.
8. After Full-tier disk edits: gate with MCP `astloom_quality_audit` and/or CLI `docs-standards` / `quality-audit`; refresh catalog when needed.

## Do not

- Treat `validate` as Full-tier compliance.
- Bypass docs-sync for governed docs-as-code when these tools are on the profile.
- Skip `astloom_docs_authoring_standards` when asked how documentation writing works.
- Invent `DOCUMENTED_BY` from catalog tags alone.
- Treat Memory as a stale-doc candidate queue.
