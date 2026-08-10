# Agent entry

**Law:** always-on rule `mcp-first-astloom`.

## Session start

1. Resolve workspace guidance via MCP when available.
2. Apply always-on rules from the bundle.
3. Load the matching skill before heavy memory, graph, docs, or durable-write work.

## Skills

- `astloom-session-bootstrap` — session start / MCP bootstrap
- `astloom-memory` — recall or persist project memory
- `astloom-code-graph` — symbols, callers, ownership, blast radius
- `astloom-remove-dead-code` — prove and delete orphans after replace/retire (scored unused-candidates MCP; prefer `safe_to_delete` + `score ≥ 0.8`)
- `astloom-remove-stale-docs` — prove and remediate orphan/ghost/wiki/duplicate/stale docs (scored `astloom_docs_stale_candidates`; prefer update/unlink over delete)
- `astloom-durable-write` — memory / task / activity / decision records
- `astloom-documentation-authoring` — Full-tier Markdown; write + fix-on-read
- `astloom-standards-on-edit` — fix-on-write for docs and hard modules
- `astloom-quality-audit` — session/edit quality debt; remediate high/medium
- `astloom-docs-sync` — Body-tier drift / coverage / validate / note / draft / index
- `astloom-source-contracts` — standards 49/50; fix-on-read for hard modules
- `astloom-create-task` — durable follow-up Task
