---
name: astloom-code-graph
description: Search Astloom code knowledge graph before wide local search.
---

# Astloom code graph

## When

- Locating symbols, owners, callers, related modules, or blast radius.
- Planning a change with graph-guided context.

## How

1. Structural first: `astloom_code_graph_callers`, `astloom_code_graph_impact` (`direction`), `astloom_code_graph_community`, `astloom_code_graph_call_path` — before wide Read/`rg`. These use `reference_kind=structural`.
2. Semantic / “how does X work” / survey: `astloom_code_graph_explore`; follow `escalate_hint.next_tools` when present.
3. Name/meaning lookup only: `astloom_code_graph_hybrid_search` or `astloom_code_graph_search`.
4. Related human Markdown: `astloom_docs_catalog` (tags/lanes/query) then Read matches — never invent `DOCUMENTED_BY`.
5. Seed pack: `astloom_code_graph_generation_context`; prefer `hybrid_documentation` (human → living → rationale → AST), including `MODULE_CONTRACT` / package README maps when present.
6. Reviews/PRs: `astloom_code_graph_detect_changes` with changed paths.
7. Architecture: `astloom_code_graph_architecture_overview` or `astloom_code_graph_path`.
8. IDE-precise rename/refs/definition (local LSPs): `astloom_code_graph_ide_references` / `ide_definition` / `ide_rename` (`reference_kind=ide_semantic`). Reconcile via rename or `astloom_code_graph_reconcile_after_edit` — never durable `CODE_REL` from LSP. `available=false` → configure `ASTLOOM_LSP_CMD_*`.
9. Escalate to Read/`rg` only for pending-sync, low-confidence edges, empty graph, or after structural + explore/hybrid fails; report degraded mode.
10. After replace/retire → skill `astloom-remove-dead-code` in the same change (scored `astloom_code_graph_unused_candidates`; act on `safe_to_delete` with `score ≥ 0.8`).

## Do not

- Prefer workspace crawl when graph tools are healthy.
- Re-verify explore packs with wide Grep when verbatim source already returned.
- Treat catalog hits as graph edges.
- Skip `escalate_hint` and dump full files.
- Confuse structural neighbors with IDE find-refs, or dual-write LSP into the durable graph.
