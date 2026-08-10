---
name: astloom-session-bootstrap
description: Bootstrap an Astloom MCP session—ping, profile, resolve guidance, then code.
---

# Astloom session bootstrap

## When

- Starting work on an Astloom-connected project.
- After MCP reload or Usage Profile change.

## How

1. Lazy MCP: `mcp_search_tools` → `mcp_execute_tool`; start with `astloom_ping`.
2. `astloom_get_effective_profile` for allowed tools.
3. `astloom_guidance_resolve` → apply `agents_entry` + `always_rules`.
4. Matching catalog skill → `astloom_guidance_get_skill` before improvising.
5. Product docs → `astloom_docs_authoring_standards` + `astloom-documentation-authoring`.
6. Hard modules / package seams → `astloom-source-contracts` (49/50).
7. **Quality debt:** `astloom_quality_audit` → if `must_remediate`, skill `astloom-quality-audit` (remediate or durable tasks) before coding further.
8. Only then memory / graph / docs / write tools or local edits.

## Do not

- Large refactors before guidance resolve when the tool exists.
- Assume tools without search or the effective profile.
- Skip `astloom_quality_audit` at session start when it is on the effective profile.
