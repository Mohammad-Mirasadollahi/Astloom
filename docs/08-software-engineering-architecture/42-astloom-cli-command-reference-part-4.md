---
doc_id: as.doc.sea.astloom-cli-command-reference-part-4
title: 42 - Astloom CLI Command Reference (Continued) (Continued) (Continued) (Part 4)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Remaining `astloom` command catalog entries split from `docs/08-software-engineering-architecture/42-astloom-cli-command-reference-continued-continued-continued.md`
  to satisfy the soft body-size budget.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/42-astloom-cli-command-reference-part-4.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/packages/astloom_cli/main.py::main
- backend/packages/astloom_cli/commands/mcp_tokens.py::cmd_mcp_tokens
- backend/packages/astloom_cli/mcp_token_report.py::build_report
- backend/packages/astloom_cli/mcp_usage_log.py::append_mcp_usage_event
- backend/services/mcp-gateway-service/src/mcp_gateway_service/server.py::handle_message
- backend/packages/astloom_cli/sync_config.py::SyncConfigError
- backend/packages/astloom_cli/software_paths.py::format_paths_env
- backend/packages/astloom_cli/docs_link_sync.py::DocsLinkSyncResult
- backend/services/code-graph-service/src/code_graph_service/domain/repo_discovery.py::DiscoveredFile
- backend/services/code-graph-service/src/code_graph_service/domain/doc_discovery.py::DiscoveredDocFile
- backend/services/code-graph-service/src/code_graph_service/application/ingest/human_docs.py::human_doc_symbol_id
- backend/packages/astloom_cli/cli_defaults.py::load_dotenv_files
- backend/packages/astloom_cli/identity.py::identity_path
- backend/packages/astloom_cli/commands/sync/jobs.py::cmd_sync_jobs
- backend/services/code-graph-service/src/code_graph_service/api/client_sync_job_snapshots.py::list_live_job_snapshots
- tests/backend/services/code-graph-service/test_human_docs_ingest.py::login
- backend/packages/astloom_cli/docs_audit_scope.py::is_docs_audit_path
- backend/packages/astloom_cli/sync_config.py::resolve_sync_filters
- backend/packages/astloom_cli/parser/_core.py::peel_sync_words
- backend/packages/astloom_cli/commands/sync/one_root.py::embedding_refresh_mode_from_args
- backend/packages/astloom_cli/embedding_heal_guidance.py::print_embedding_heal_guidance
- backend/services/code-graph-service/src/code_graph_service/application/embedding_refresh.py::EmbeddingRefreshMixin.refresh_embeddings_after_ingest
doc_version: 1.5.1
updated_at: 2026-08-10
related_docs:
- docs/09-platform-governance-operations/13-project-scoped-backup-and-restore.md
- docs/superpowers/specs/2026-08-01-project-backup-restore-design.md
- docs/07-code-knowledge-graph/77-sync-embedding-heal-operator-runbook.md
- docs/superpowers/specs/2026-08-10-server-client-sync-jobs-cli-design.md
- docs/superpowers/specs/2026-08-10-client-sync-auto-discovery-inventory-design.md
---

# 42 - Astloom CLI Command Reference (Continued) (Continued) (Continued) (Part 4)

## Purpose

Remaining `astloom` command catalog entries split from `docs/08-software-engineering-architecture/42-astloom-cli-command-reference-continued-continued-continued.md` to satisfy the soft body-size budget.

## Command catalog (continued)

### `astloom mcp tools`

| | |
| --- | --- |
| **Why** | List MCP tool names for a Usage Profile (verify catalog wiring) |
| **Required** | None |
| **Optional** | `--usage-profile` (default `programming-cursor-mcp`) |
| **Example** | `astloom mcp tools` |
| **What changes** | Nothing (read-only) |

### `astloom mcp tokens`

| | |
| --- | --- |
| **Why** | Estimate how many tokens Astloom MCP injects on connect (`tools/list` lazy facade vs full catalog), list heavy tool payload estimates, and summarize logged MCP usage by **client id** and **scope id** over a time range |
| **Required** | None |
| **Optional** | `--usage-profile` · `--since` / `-s` (`24h`, `7d`, `30d`, ISO; default `7d`) · `--until` / `-u` · `--clients` (`all` or `cursor,vscode,…`) · `--id` (`all` or `tenant/workspace/project[,…]`) · `--project-dir` · `--include-user-clients` · `--format text\|json` |
| **Example** | `astloom mcp tokens --since 24h` · `astloom mcp tokens --clients cursor,vscode --id mir/dev/astloom` · `astloom mcp tokens -f json` |
| **What changes** | Nothing (read-only). Gateway appends `<ASTLOOM_DATA_ROOT>/mcp-usage/events.jsonl` on `initialize` / `tools/list` / `tools/call` when an IDE is connected (`ASTLOOM_MCP_CLIENT_ID` stamped at wire/connect time) |
| **Token unit** | Approx UTF-8 bytes/4 (same heuristic as sync usage) |
| **Normative design** | [44-mcp-token-accounting.md](./44-mcp-token-accounting.md) |

### `astloom mcp serve`

| | |
| --- | --- |
| **Why** | Run the MCP gateway on **stdio** for one project scope (what IDEs spawn) |
| **Required** | Scope flags |
| **Optional** | `--usage-profile` |
| **Example** | `astloom mcp serve --tenant acme --workspace eng --project payments` |
| **What changes** | Long-running process; talks MCP on stdin/stdout. Does not rewrite IDE configs |

### `astloom mcp serve-http`

| | |
| --- | --- |
| **Why** | Run Streamable HTTP MCP for concurrent agents (Phase B) |
| **Required** | Server env for token/public URL when used remotely (see doc 41) |
| **Optional** | `--host`, `--port`, `--usage-profile` |
| **Example** | `astloom mcp serve-http --host 0.0.0.0 --port 32500` |
| **What changes** | Binds an HTTP listener; clients use bearer auth configured at connect time |

### `astloom service start` / `stop` / `restart` / `status` / `detail`

| | |
| --- | --- |
| **Why** | One operator command for local Compose infra (postgres + neo4j) **and** the MCP HTTP backend daemon |
| **Required** | Prior `bash install.sh` (compose `.env.local` + Docker). Repo root or `ASTLOOM_ROOT` |
| **Optional** | `start --json` · `stop --json` · `restart --json` · `status --json` · `detail --json` |
| **Example** | `astloom service start` · `astloom service status` · `astloom service detail` · `astloom service restart` |
| **What changes** | Starts/stops Compose profile `core` services; backgrounds MCP HTTP (pid/log under `.astloom/run/`). If no MCP token env is set, creates `.astloom/mcp-http.secret` |
| **Status fields** | `status` / `detail` show **Restarted** (latest start among running postgres/neo4j/MCP HTTP) and **UpTime** since that time |
| **Exit** | `status` / `detail` exit `1` unless State is `all running`. Failed `start`/`restart` prints the MCP HTTP log tail automatically |
| **Diagnose** | When State is not `all running`, run `astloom service detail` to see MCP HTTP log (and Compose logs for unhealthy containers) |

### `astloom boot enable` / `disable`

| | |
| --- | --- |
| **Why** | Start Astloom automatically on machine boot via systemd |
| **Required** | `systemctl` available; write access to unit path (system unit needs root/sudo; `--user` does not) |
| **Optional** | `--user` — install `~/.config/systemd/user/astloom.service` instead of `/etc/systemd/system/` |
| **Example** | `sudo $(which astloom) boot enable` · `astloom boot enable --user` · `astloom boot disable` |
| **What changes** | Writes a oneshot systemd unit that runs `astloom service start` / `stop`, then `systemctl enable` / `disable`. User units may need `loginctl enable-linger $USER` to run at boot without an interactive login |
| **Note** | Distinct from `astloom status` (graph/sync view). Use `astloom service status` for process health |

### `astloom client list-mcp-clients`

| | |
| --- | --- |
| **Why** | Show which IDE/agent MCP config targets the CLI knows how to write |
| **Required** | None |
| **Example** | `astloom client list-mcp-clients` |
| **What changes** | Nothing |

**Removed:** `astloom client wire-remote` / `astloom client doctor-remote` (SSH stdio wiring) have been removed from the product (API-only HTTPS migration). Use `astloom connect` — see [41-one-command-cross-platform-agent-onboarding.md](./41-one-command-cross-platform-agent-onboarding.md).

### `astloom path install`

| | |
| --- | --- |
| **Why** | Put `astloom` on `~/.local/bin` (and optionally shell rc PATH) |
| **Required** | Working `.venv/bin/astloom` from install |
| **Optional** | `--shell-rc` (e.g. `.bashrc`) |
| **Example** | `astloom path install --shell-rc .bashrc` |
| **What changes** | Symlink under `~/.local/bin`; may append PATH export to shell rc |

### `astloom ports show` / `astloom ports check`

| | |
| --- | --- |
| **Why** | Show or bind-check ports from the port profile before starting services |
| **Required** | None |
| **Optional** | `--profile` path |
| **Example** | `astloom ports show` · `astloom ports check` |
| **What changes** | Nothing persistent; `check` exits `1` if any port cannot bind |

### `astloom graph ingest`

| | |
| --- | --- |
| **Why** | Explicit ingest of a path (lower-level than `sync`; useful in scripts/smokes) |
| **Required** | Scope flags, `--path` |
| **Optional** | `--max-files` |
| **Example** | `astloom graph ingest --tenant acme --workspace eng --project payments --path .` |
| **What changes** | Same class of graph writes as sync for that path/scope |

### `astloom graph freshness`

| | |
| --- | --- |
| **Why** | Show pending-sync / freshness for a scope |
| **Required** | Scope flags |
| **Optional** | `--mark-pending <file>` |
| **Example** | `astloom graph freshness --tenant acme --workspace eng --project payments` |
| **What changes** | Read-only unless `--mark-pending` is set |

### `astloom graph explore` / `astloom graph hybrid`

| | |
| --- | --- |
| **Why** | Operator smoke for retrieve packs without an IDE |
| **Required** | Scope flags, `--query` |
| **Optional** | `--top-k` |
| **Example** | `astloom graph explore --tenant acme --workspace eng --project payments --query "login auth"` |
| **What changes** | Nothing durable (query only) |

### `astloom graph generation-context`

| | |
| --- | --- |
| **Why** | Print the generation context pack for a seed symbol, including `hybrid_documentation` (human → living → rationale → AST) |
| **Required** | Scope flags, and either `--symbol-id` or `--qualified-name` |
| **Optional** | `--max-symbols` (default 12) |
| **Example** | `astloom graph generation-context --tenant acme --workspace eng --project payments --qualified-name src.auth.login` |
| **What changes** | Nothing durable (read-only). Does not invent graph edges |

### `astloom graph smoke`

| | |
| --- | --- |
| **Why** | One-process ingest + freshness + hybrid + explore for lab verification |
| **Required** | Scope flags, `--path` |
| **Optional** | `--query`, `--max-files` |
| **Example** | `astloom graph smoke --tenant acme --workspace eng --project payments --path . --query "login"` |
| **What changes** | Performs an ingest into the graph CLI backend |

### `astloom graph watch`

| | |
| --- | --- |
| **Why** | Batched pending-sync poll sidecar (debounced; **not** per-keystroke continuous indexing) |
| **Required** | Scope flags, `--path` |
| **Optional** | `--interval`, `--debounce`, `--max-wait`, `--once` |
| **Example** | `astloom graph watch --tenant acme --workspace eng --project payments --path . --once` |
| **What changes** | May flush pending sync **banners** into freshness state while running; does not replace explicit ingest. Any future flush-to-ingest path must honor Client Skip/Ingest preference — see [`../07-code-knowledge-graph/51-client-standards-gate-and-watcher-policy.md`](../07-code-knowledge-graph/51-client-standards-gate-and-watcher-policy.md) |

Default graph CLI backend is in-memory (`ASTLOOM_GRAPH_CLI_BACKEND=memory`). Set `ASTLOOM_GRAPH_CLI_BACKEND=neo4j` (plus Neo4j env) for durable Compose labs. See [wedge connect runbook](../07-code-knowledge-graph/35-wedge-operator-connect-runbook.md).

---

## Sync vs `sync heal`

Normative operator runbook (contracts, MCP, verification, failure):  
[`../07-code-knowledge-graph/77-sync-embedding-heal-operator-runbook.md`](../07-code-knowledge-graph/77-sync-embedding-heal-operator-runbook.md).

| Command | File ingest | Embedding refresh |
| --- | --- | --- |
| `astloom sync` | Incremental only: new / changed / lang-backfill / structural edge-repair. Hash-stable healthy files are skipped. | Scoped to touched files; on noop, drains a small capped backlog (default 256). |
| `astloom sync heal` | Same incremental file pass as `sync` (never force-reparses healthy hash-stable files). | Full-project heal: missing/mismatch rows + orphan cleanup, uncapped. |

```bash
astloom sync
astloom sync heal
astloom sync heal max-file 200
```

Env overrides (service): `ASTLOOM_EMBEDDING_REFRESH_FULL=1` forces full heal; `ASTLOOM_EMBEDDING_REFRESH_MAX_PENDING` caps the noop backlog for normal sync. MCP parity: `astloom_code_graph_sync` accepts `embedding_refresh_mode: "touched" | "full"`.

pgvector wiring: set `ASTLOOM_CODE_GRAPH_DATABASE_URL` or fall back to `ASTLOOM_DATABASE_URL` (Settings + Compose/`local_mcp`). Missing both → `embedding_index_unavailable` (heal cannot write rows; hybrid may expose `semantic_error`).

Operator surfaces: `astloom stats`, `inventory`, and the **Before sync** preflight print **Need embedding heal** (missing count + `astloom sync heal`) when searchable symbols lack rows. If the run is already `sync heal`, the preflight says this run will full-heal instead of suggesting another command.

---

## Server: live client sync jobs

**Server role only.** While a remote `astloom-client sync` content-push is in flight, the graph process writes best-effort snapshots under `{ASTLOOM_DATA_ROOT}/run/client-sync-jobs/<job_id>.json`. Operators inspect them with:

| Command | Behavior |
| --- | --- |
| `astloom sync jobs` | List live `job_id` rows (scope, done/total, %, age). Empty → exit 0. |
| `astloom sync jobs <job_id>` | Heavy detail: rate, ETA, in-flight paths, workers, graph CPU%/RSS (best-effort `/proc`). |
| `… --json` | Same payloads as JSON. |

Client installs fail closed. Designs: [`../superpowers/specs/2026-08-10-server-client-sync-jobs-cli-design.md`](../superpowers/specs/2026-08-10-server-client-sync-jobs-cli-design.md), auto discovery / prune [`../superpowers/specs/2026-08-10-client-sync-auto-discovery-inventory-design.md`](../superpowers/specs/2026-08-10-client-sync-auto-discovery-inventory-design.md).

**Note:** `done/total` on a live job tracks the **current HTTP batch** (size-capped), not necessarily the full tree `present` count printed on the client note line.

---

## Sync filters

`astloom sync` **refuses to run** unless a filter file exists under the sync root (`--path`). Filters are **exclude-only**, with **separate** lists for code vs docs.

### Required files (any one)

| Path | Typical use |
| --- | --- |
| `astloom.sync.yaml` | Local operator copy (**gitignored**; create via `cp` from example) |
| `astloom.sync.yml` | Same as above |
| `.astloom/sync.yaml` | Local-only override (under gitignored `.astloom/`) |

Template (tracked): repo-root `astloom.sync.yaml.example`.

```bash
cp astloom.sync.yaml.example astloom.sync.yaml
## edit code.exclude / docs.match / docs.exclude
astloom sync --path .
```

### Preferred schema

| Section | Role |
| --- | --- |
| `code.exclude` | Skip noise from **code** discovery (dirs + globs) |
| `code.include_extensions` | Which language suffixes count as source (not a path allow-list) |
| `docs.match` | Wildcard set of human docs (default idea: `**/*.md`, `**/*.mdx`) |
| `docs.exclude` | Docs-only skips for **Phase 2 discovery** (independent from `code.exclude`) |
| `docs.audit.exclude` | Extra skips for **Full-tier / quality-audit / sync standards gate** only (still may sync). Always merged with built-in README/AGENTS/skill/tests defaults |

Do **not** list `docs` under `code.exclude` just to “enable” documentation — Markdown is not a code extension. Use `docs.match: []` or `docs.enabled: false` to disable Phase 2.

Path allow-lists (`include_paths`) are **legacy**; prefer exclude-only. Top-level `exclude` still maps to code excludes for older configs.

### Merge order (lowest → highest priority)

1. Repo `astloom.sync.yaml` (or `.yml`) — **source of truth for excludes**
2. Local `.astloom/sync.yaml` (if present; last key wins for overlapping top-level keys)
3. Env: `ASTLOOM_SYNC_EXCLUDE_DIRS`, `ASTLOOM_SYNC_DOC_MATCH`, `ASTLOOM_SYNC_DOC_EXCLUDE`, `ASTLOOM_SYNC_DOC_AUDIT_EXCLUDE`, `ASTLOOM_SYNC_INCLUDE_EXTENSIONS`
4. CLI: `--exclude-dir`, `--include-ext` (and legacy `--include-path`)

There is **no hardcoded product exclude list in Python**. Operators edit `code.exclude` / `docs.exclude` in the YAML. Hidden directories whose names start with `.` are still skipped during tree walks as a filesystem safety (e.g. `.git`).

### Wildcards

Patterns use `fnmatch` with `**` = any depth. Leading `**/` matches zero or more directories.

| Pattern | Typical use |
| --- | --- |
| `**/*.md` | Every Markdown file under the sync root (`docs.match`) |
| `**/tests/**` | Skip tests trees (`code.exclude`) |
| `**/*.min.js` | Skip minified JS |
| `**/CHANGELOG.md` | Skip changelog from docs Phase 2 |

Brace expansion (`*.{ts,tsx}`) is **not** supported — list two patterns.

### Minimal example

```yaml
code:
  exclude:
    - tests
    - "**/__pycache__/**"
    - "**/__init__.py"
    - "**/generated/**"
    - "**/*.min.js"
  include_extensions:
    - .py
    - .ts
    - .tsx

docs:
  match:
    - "**/*.md"
    - "**/*.mdx"
  exclude:
    - "**/CHANGELOG.md"
```

### CLI / env extras

```bash
astloom sync --exclude-dir generated --exclude-dir '**/*.spec.ts'
ASTLOOM_SYNC_EXCLUDE_DIRS='tests,**/generated/**' astloom sync
ASTLOOM_SYNC_DOC_MATCH='**/*.md,**/*.mdx' astloom sync
ASTLOOM_SYNC_DOC_EXCLUDE='**/CHANGELOG.md' astloom sync
```

---

### `astloom backup export`

| | |
| --- | --- |
| **Why** | Export one project scope to a portable `.asbak` for migrate/DR drills |
| **Required** | `--output` / `-o`; scope from flags/env/identity/connect |
| **Optional** | `--tenant` `--workspace` `--project` |
| **Example** | `astloom backup export -o ./project.asbak` |
| **What changes** | Writes `.asbak`; updates `<ASTLOOM_DATA_ROOT>/backup/last-job.json` |
| **Client-only** | No (server / both) |

### `astloom backup validate`

| | |
| --- | --- |
| **Why** | Check checksums, contract, and schema fingerprint before restore |
| **Required** | `--input` / `-i` |
| **Optional** | `--skip-contract` |
| **Example** | `astloom backup validate -i ./project.asbak` |
| **What changes** | Nothing (read-only; may read DB for schema gate) |

### `astloom backup dry-run`

| | |
| --- | --- |
| **Why** | Preview conflict/remap without writing stores |
| **Required** | `--input` / `-i` |
| **Optional** | `--replace`, remap flags, `--skip-contract` |
| **Example** | `astloom backup dry-run -i ./project.asbak` |
| **What changes** | Updates last-job JSON only |

### `astloom backup restore`

| | |
| --- | --- |
| **Why** | Import a `.asbak` into this server’s stores for a scope |
| **Required** | `--input` / `-i`; empty target **or** `--replace --yes` |
| **Optional** | `--remap-tenant` `--remap-workspace` `--remap-project` `--skip-contract` |
| **Example** | `astloom backup restore -i ./project.asbak --replace --yes` |
| **What changes** | Writes Postgres/Neo4j/local project pin; may wipe scope first |

### `astloom backup status`

| | |
| --- | --- |
| **Why** | Show last backup/restore/dry-run job summary |
| **Required** | None |
| **Example** | `astloom backup status` |
| **What changes** | Nothing (read-only) |

Normative operator detail: [13-project-scoped-backup-and-restore.md](../09-platform-governance-operations/13-project-scoped-backup-and-restore.md).

## Destructive and safety notes

| Action | Safety |
| --- | --- |
| `purge` | Requires `--yes`; scopes wipe only (graph data) |
| `paths remove` | Warns that graph data for removed trees **remains** until `purge`; cannot remove the last path |
| `destroy-profile` | Two different typed confirmations in a TTY; deletes profile/platform data for one scope; **never** source code |
| `backup restore --replace` | Requires `--yes`; wipes target scope stores then imports bundle |
| `init --force` | Overwrites identity pin; does not auto-purge old graph |
| Changing tenant/workspace/project | Isolates new data; old scope stays until purged or destroyed |
| `connect` | Overwrites/merges MCP config files for selected clients |

Do not put secrets in docs or chat examples. MCP bearer secrets belong in env / connect auth, not committed files.

## Implementation map

| Area | Path |
| --- | --- |
| Parser | `backend/packages/astloom_cli/parser/` |
| Dispatch | `backend/packages/astloom_cli/main.py` |
| Commands | `backend/packages/astloom_cli/commands/` |
| Project backup | `backend/packages/astloom_backup/` + `commands/backup_cmd.py` |
| Sync filter merge | `backend/packages/astloom_cli/sync_config.py` |
| Software paths | `backend/packages/astloom_cli/software_paths.py` |
| Docs link Phase 2 | `backend/packages/astloom_cli/docs_link_sync.py` |
| File discovery | `backend/services/code-graph-service/src/code_graph_service/domain/repo_discovery.py` |
| Doc discovery | `backend/services/code-graph-service/src/code_graph_service/domain/doc_discovery.py` |
| Human doc projection | `backend/services/code-graph-service/src/code_graph_service/application/ingest/human_docs.py` |
| Operator exclude list | `astloom.sync.yaml` / `astloom.sync.yaml.example` |
| Scope defaults | `backend/packages/astloom_cli/cli_defaults.py` |
| Identity | `backend/packages/astloom_cli/identity.py` |
| Tests | `tests/backend/tools/astloom-cli/` (incl. `test_sync_config.py`, `test_docs_link_sync.py`); `tests/backend/services/code-graph-service/test_human_docs_ingest.py` |

## Related Documents

- Previous chunk: `docs/08-software-engineering-architecture/42-astloom-cli-command-reference-continued-continued-continued.md`
- Upgrade CLI catalog (normative): [51-software-upgrade-server-and-client.md](./51-software-upgrade-server-and-client.md#cli-catalog-astloom-upgrade)
- Overview: [36-astloom-cli.md](./36-astloom-cli.md)
