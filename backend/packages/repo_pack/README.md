# repo_pack

Path: `backend/packages/repo_pack/`

## Purpose

Clean-room helpers for Repomix / CBM prior-art ideas that Astloom adopts:
layered ignore, secret scan before export, token estimates, change-scoped review packs.

## Boundaries

- **Owns:** ignore file parse, heuristic secret rules, review-pack markdown, token heuristic.
- **Does not own:** Neo4j graph packs (`explore`), LiteLLM, whole-repo paste as primary UX.
- **Law:** docs `21`, `52`, `53`; fail closed on secrets for export.

## Start here

| File | Role |
| --- | --- |
| `layered_ignore.py` | `.gitignore` + `.astloomignore` → exclude globs |
| `secret_scan.py` | Heuristic secret findings |
| `tokens.py` | chars÷4 token estimate |
| `review_pack.py` | Change-scoped pack builder |
