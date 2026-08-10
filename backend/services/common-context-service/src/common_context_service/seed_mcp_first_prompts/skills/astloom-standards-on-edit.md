---
name: astloom-standards-on-edit
description: >-
  Fix-on-write: remediate product docs or hard-module code to standards in the same turn.
---

# Astloom standards on edit (fix-on-write)

## When

- Create/edit product Markdown under `docs/`, `backend/docs/`, `frontend/docs/`, `ai-toolstack/docs/`, or `deploy-toolkit/**/*.md`.
- Create/edit hard modules or package/folder seams needing README maps.
- User asks to bring touched code/docs up to standards.
- After `astloom sync` skipped nonconforming paths — fix when next touching them.

## Law

**Same turn as the edit:** do not leave known nonconforming work you just wrote. Prefer root-cause remediation at the shared seam.

## How (docs)

1. Skill `astloom-documentation-authoring` + `astloom_docs_authoring_standards`.
2. Apply Full-tier law (English, frontmatter, lanes, Purpose/H1, design Mermaid+flow, size budgets, evidence `linked_symbols`).
3. **Revision stamp (required on material create/edit):**
   - Keep body/frontmatter truthful to the change (not stamp-only).
   - Bump `doc_version` (semver `MAJOR.MINOR.PATCH`; patch+ for small edits, minor/major when structure/contract changes).
   - Set `updated_at` to today's UTC date (`YYYY-MM-DD`).
4. Prefer drift/catalog/`linked_symbols` to find which docs a code change affects — do not rely on dates alone.
5. Gate after edits: MCP `astloom_quality_audit` (and CLI `docs-standards` when needed). Soft size and linking gaps **must** be remediated or tasked — not left as ignored warnings.
6. Fix-on-read still applies for any nonconforming product doc already opened.

## How (code)

1. Skill `astloom-source-contracts` for hard modules (49) and package README maps (50).
2. Keep module contracts accurate; update in the same change when invariants change.
3. Honor always-on engineering laws (tests with implementation, root-cause fixes, English, orphan cleanup).
4. After material symbol/API edits, prefer graph refresh when available; update linked product docs (content + revision stamp) in the same change when drift applies.

## Sync

- Sync may skip nonconforming docs (`--skip-nonconforming` or interactive Y). That keeps the graph clean — it does not replace remediation.
- Fix standards on edit first; next sync can ingest.

## Do not

- Ship new/edited product docs that still fail Full-tier.
- Bump `doc_version` / `updated_at` without aligning the body (cargo-cult stamping).
- Edit a hard module and leave a missing/wrong contract header.
- Treat Body-tier `validate` as Full-tier.
- Use `# tsoc-defer` for standards gaps unless the user explicitly accepted it.
