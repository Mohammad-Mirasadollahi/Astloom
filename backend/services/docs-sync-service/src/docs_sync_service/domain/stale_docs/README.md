# stale_docs

Graph/registry-backed stale-documentation candidates. Astloom never deletes Markdown.

## Boundaries

- **May:** score orphan/ghost/stale-anchor/superseded/coverage_gap/`wiki_orphan`/`duplicate_authority` rows; filter via `path_prefix`.
- **Must not:** mutate docs; invent `DOCUMENTED_BY`; use Memory as candidate SoT.

## Start here

1. `find.py` — orchestration (`find_stale_doc_candidates`)
2. `scoring.py` — monotonic score + act flags
3. Normative: `docs/07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md`
