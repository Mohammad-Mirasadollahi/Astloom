# astloom_backup

Project-scoped `.asbak` export/import for Astloom.

## Purpose

Own the bundle format, checksum/version gates, and per-store codecs used by
`astloom backup` and MCP `backup.status` / `backup.dry_run`.

## Start here

1. `orchestrator.py` — export / validate / restore / dry-run
2. `ports.py` — per-store `export_scope` / `import_scope` adapters
3. `tables.py` — Postgres table registry (includes audit/reporting + memory id map)
4. `pg.py` / `neo4j_store.py` — store codecs
5. `manifest.py` / `bundle.py` — archive contract + schema fingerprint

## Install

Listed in root `pyproject.toml` as `astloom_backup`. Verified by
`scripts/ensure-venv.sh` and `astloom doctor` (`import_astloom_backup`).

## Boundaries

- CLI and MCP call this package; they do not reach into service private modules.
- Outbox/idempotency tables, adapter broker deliveries, and connector secrets are not exported.
