# unused_candidates

Graph-backed dead-code candidate discovery (scores + evidence). Astloom never deletes files.

## Boundaries

- **May:** compute unused / unreachable / zombie / runtime-dead / flag-controlled rows; filter report pool via `path_prefix`.
- **Must not:** mutate the repo; treat Memory as candidate SoT; raise `safe_to_delete` via triage; dump the whole project graph for anchored MCP modes.

## Graph load (MCP)

Callers go through `QueryUseCases.unused_candidates` (`application/queries.py`):

- Anchored `scope_mode` (`changed_symbols` / `task_neighborhood` / `explicit_paths`): 1-hop neighborhood — never unscoped `list_edges`.
- `project_scan`: full compact listing under `deadline_monotonic`; on timeout return `degraded` without blocking the HTTP reply.

Normative: `docs/07-code-knowledge-graph/83-mcp-tool-budget-and-small-batch-sync.md` (load) and `36-dead-code-candidates-and-cleanup-loop.md` (scores).

## Start here

1. `find.py` — orchestration + MCP payload (`find_unused_candidates`)
2. `liveness.py` — live roots / test_only / inbound edges
3. `findings.py` — unreachable_file, zombie_package / unwired_shared_package, runtime_dead
4. `package_class.py` — wire / keep_public / retire for ``backend/packages/``
5. `rows.py` — score + row shape
6. `../dead_code_scoring.py` — numeric score model
7. Normative: `docs/07-code-knowledge-graph/79-shared-package-wiring-and-unwired-findings.md` (plus docs 36 and 83)
