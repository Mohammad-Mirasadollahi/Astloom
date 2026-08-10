# Backup Restore

Path: `backend/runbooks/backup-restore`

## Purpose

Operator boundary for **project-scoped** backup and restore (`.asbak` bundles).

## Normative docs (read these)

| Doc | Role |
| --- | --- |
| [`docs/09-platform-governance-operations/13-project-scoped-backup-and-restore.md`](../../../docs/09-platform-governance-operations/13-project-scoped-backup-and-restore.md) | Operator runbook (commands, gates, install verify) |
| [`docs/superpowers/specs/2026-08-01-project-backup-restore-design.md`](../../../docs/superpowers/specs/2026-08-01-project-backup-restore-design.md) | Design / architecture |
| [`docs/09-platform-governance-operations/04-data-retention-backup-and-disaster-recovery.md`](../../../docs/09-platform-governance-operations/04-data-retention-backup-and-disaster-recovery.md) | Platform DR context |

## Commands (quick)

```bash
astloom backup export --output ./project.asbak
astloom backup validate --input ./project.asbak
astloom backup dry-run --input ./project.asbak
astloom backup restore --input ./project.asbak
astloom backup restore --input ./project.asbak --replace --yes
astloom backup restore --input ./project.asbak \
  --remap-tenant NEW_T --remap-workspace NEW_W --remap-project NEW_P
astloom backup status
```

Gates: checksums, `contract_version` (optional `--skip-contract`), schema fingerprint,
post-restore row-count verification, Neo4j required when `ASTLOOM_CODE_GRAPH_STORE=neo4j`.

MCP (status / dry-run only): `astloom_backup_status`, `astloom_backup_dry_run`.

## Implementation home

| Piece | Path |
| --- | --- |
| Package | `backend/packages/astloom_backup/` |
| Store ports | `backend/packages/astloom_backup/ports.py` |
| CLI | `backend/packages/astloom_cli/commands/backup_cmd.py` |
| Parser | `backend/packages/astloom_cli/parser/backup.py` |
| MCP backends | `backend/services/mcp-gateway-service/src/mcp_gateway_service/backends/backup.py` |
| Usage profile tools | `backend/configs/usage-profiles/programming-cursor-mcp.json` |
| Tests | `tests/backend/unit/astloom_backup/`, `tests/backend/integration/astloom_backup/` |

## Install

Ships with the `astloom` distribution (`pyproject.toml` package `astloom_backup`).
Post-install checks: `import astloom_backup` in `ensure-venv.sh` and `astloom doctor`.

## Modular Boundary

Expose behavior through the CLI and `astloom_backup` public APIs. Do not import
private internals from sibling service packages beyond documented store codecs.
