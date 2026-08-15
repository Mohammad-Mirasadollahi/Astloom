---
doc_id: as.doc.sea.astloom-cli-command-reference-continued-continued-continued
title: 42 - Astloom CLI Command Reference (Continued) (Continued) (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/08-software-engineering-architecture/42-astloom-cli-command-reference-continued-continued.md`
  — remaining sections after the soft size budget.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/42-astloom-cli-command-reference-continued-continued-continued.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/packages/astloom_cli/main.py::main
- backend/packages/astloom_cli/sync_config.py::SyncConfigError
- backend/packages/astloom_cli/software_paths.py::format_paths_env
- backend/packages/astloom_cli/docs_link_sync.py::DocsLinkSyncResult
- backend/packages/astloom_cli/commands/docs_standards/scope.py::is_docs_audit_path
- backend/packages/astloom_cli/sync_standards_gate.py::list_nonconforming_docs
- backend/services/code-graph-service/src/code_graph_service/domain/repo_discovery.py::DiscoveredFile
- backend/services/code-graph-service/src/code_graph_service/domain/doc_discovery.py::DiscoveredDocFile
- backend/services/code-graph-service/src/code_graph_service/application/ingest/human_docs.py::human_doc_symbol_id
- backend/packages/astloom_cli/cli_defaults.py::load_dotenv_files
- backend/packages/astloom_cli/identity.py::identity_path
- tests/backend/services/code-graph-service/test_human_docs_ingest.py::login
- scripts/remediate_docs_standards.py::main
- scripts/split_soft_budget_docs.py::main
- scripts/stamp_docs_revision.py::main
- backend/packages/astloom_cli/commands/followup_tasks.py::cmd_followup_tasks_list
- tests/backend/tools/astloom-cli/test_docs_standards.py::test_parser_docs_standards_word_modes
- backend/packages/astloom_cli/embedding_heal_guidance.py::print_embedding_heal_guidance
- backend/packages/astloom_cli/docs_registry_hygiene.py::purge_docs_registry_fixture_noise
doc_version: 1.5.2
updated_at: 2026-08-15
related_docs:
- docs/07-code-knowledge-graph/77-sync-embedding-heal-operator-runbook.md
- docs/superpowers/specs/2026-08-10-client-sync-auto-discovery-inventory-design.md
- docs/superpowers/specs/2026-08-10-server-client-sync-jobs-cli-design.md
---

# 42 - Astloom CLI Command Reference (Continued) (Continued) (Continued)

## Purpose

Continuation of `docs/08-software-engineering-architecture/42-astloom-cli-command-reference-continued-continued.md` — remaining sections after the soft size budget.

## Command catalog

### `astloom version` / `astloom --version`

| | |
| --- | --- |
| **Why** | Confirm which CLI binary and repo root you are using |
| **Required** | None |
| **Example** | `astloom version` |
| **What changes** | Nothing (read-only) |

### `astloom doctor`

| | |
| --- | --- |
| **Why** | Catch broken venv, missing imports, profiles, or PATH before deeper work |
| **Required** | None |
| **Example** | `astloom doctor` |
| **What changes** | Nothing (diagnostics only) |

### `astloom init`

| | |
| --- | --- |
| **Why** | Create your first tenant + workspace with **IDs you choose**, pin **software path(s)** to sync, register a project, and pin defaults for later commands |
| **Required** | `--tenant`, `--workspace`, at least one `--path` (existing directory; repeatable) |
| **Optional** | `--project` (default: cwd name), `--name` (display), `--project-name`, `--usage-profile`, `--force` |
| **Example** | `astloom init --tenant acme --workspace eng --path /opt/MyApp --project payments` |
| **What changes** | Writes `~/.astloom/identity.yaml` (scope + `paths`); upserts `ASTLOOM_*` and `ASTLOOM_SOFTWARE_PATHS` in repo `.env`; may merge scope into `~/.astloom/connect.yaml`; writes `.astloom/projects/<tenant>/<workspace>/<project>.json` including `paths` |
| **If you change IDs** | Without `--force`, re-run shows current scope/paths. With `--force`, identity/env/connect scope are replaced; graph data for the old scope is **not** deleted automatically |
| **Edit paths later** | `astloom paths list` / `add` / `remove` — see below |

### `astloom paths`

| | |
| --- | --- |
| **Why** | Show or edit the software root directories that `astloom sync` indexes |
| **Subcommands** | `list`, `add <path…>`, `remove <path…>` |
| **Example** | `astloom paths add /opt/OtherApp` · `astloom paths remove /opt/OldApp` |
| **What changes** | Updates identity `paths`, project JSON `paths`, and `.env` `ASTLOOM_SOFTWARE_PATHS` |
| **On remove** | Prints a **warning**: previously synced graph data for removed trees **remains** until `astloom purge --yes`. Removing a path only stops future sync from that root. Cannot remove the last path |

### `astloom status`

| | |
| --- | --- |
| **Why** | One-shot health: resolved scope, infra probes, graph counts, MCP config presence, next-step hints |
| **Required** | None if defaults resolve; otherwise pass scope flags |
| **Optional** | `--tenant` `--workspace` `--project`, `--json`, `--verbose` |
| **Example** | `astloom status` |
| **What changes** | Nothing (read-only). Exit hints may tell you to `init` / `sync` / start Compose |

### `astloom inventory`

**Operator UX law (applies to everyone — humans and agents):** for `inventory`, do **not** use dashed flags for modes. Use word modes only. Prefer the verb **`save`** (never `out`) when writing a report file. Keep console output to **percentages + top 10 files with models**; put full file↔model lists only via `save`.

| | |
| --- | --- |
| **Why** | Show how much of the **client software** roots (pinned via `init` / `paths`) is already in Astloom vs still outstanding, split into **Code** and **Docs** |
| **Required** | Sync filter file at each root (same as `sync`). At least one software path. Scope from identity/env/connect (no dashed scope flags on this command) |
| **Modes** | **Normal** (default): percents + **top 10** files with models. **Detail**: same top 10 with embed/docs models, status, and per-file symbol coverage. **Save**: write full file↔model lists to a path |
| **Example** | `astloom inventory` · `astloom inventory detail` · `astloom inventory save /tmp/inventory-details.txt` · `astloom inventory detail save /tmp/inventory-details.txt` |
| **What you see** | Code/Docs split into **done** (up to date), **edited** (was ingested, then changed / pending — needs `astloom sync`), and **remaining** (never ingested); percents for each; Embeddings coverage; **top 10** lists with `models=` and `reason=` (`content_changed` or `pending`). When embeddings are missing, **Need embedding heal** + `astloom sync heal`. `save` writes the **full** lists |
| **What changes** | Nothing on the graph (read-only). `save` only writes the report file you named |

### `astloom docs-standards`

**Operator UX law:** same word-mode pattern as `inventory` — no dashed mode flags; use `detail` and `save <path>` only.

| | |
| --- | --- |
| **Why** | Show which product Markdown files fail Astloom documentation standards (frontmatter, lanes, H1/title, Purpose H2, size budgets, design Mermaid) and revision debt (`doc_version` / `updated_at`), plus **percent of the scanned tree** |
| **Required** | None (uses `ASTLOOM_ROOT` / package-derived repo root) |
| **Scan roots** | Prefer `astloom.sync.yaml` discovery (`docs.match` − `docs.exclude` − `docs.audit.exclude`); fallback without sync config: `docs/`, `backend/docs/`, `frontend/docs/`, `deploy-toolkit/` |
| **Modes** | **Normal**: conforming/nonconforming + revision-debt percents + **top 10** for each. **Detail**: same with issue/warning codes. **Save**: write full nonconforming + revision debt + conforming lists to a path |
| **Example** | `astloom docs-standards` · `astloom docs-standards detail` · `astloom docs-standards save /tmp/docs-standards.txt` · `astloom docs-standards detail save /tmp/docs-standards.txt` |
| **What you see** | Totals and percents; top nonconforming and revision-debt files; optional per-issue detail; `save` writes the full report |
| **What changes** | Nothing on the graph (read-only). `save` only writes the report file you named |
| **How to fix findings** | Follow normative procedure `docs/00-master-plan/10-documentation-standardization-procedure.md` (issue-code table, remediator, soft-budget split, evidence `linked_symbols`). Helpers: `scripts/remediate_docs_standards.py`, `scripts/split_soft_budget_docs.py`, `scripts/stamp_docs_revision.py`, library `astloom_cli.commands.docs_standards.remediate` |
| **Done means** | `nonconforming_count = 0`, revision debt cleared for the remediation scope, and soft-budget warnings cleared; tree lock in `tests/backend/tools/astloom-cli/test_docs_standards.py` |
| **Normative refs** | `docs/00-master-plan/06-professional-documentation-standard.md`, `08-documentation-structure-and-machine-ingest-standard.md`, `09-documentation-classification-and-lanes.md`, **`10-documentation-standardization-procedure.md`** |

### `astloom docs-suggest-links`

**Hybrid write path:** evidence-only suggestions for `linked_symbols`. Never invents `DOCUMENTED_BY` edges.

| | |
| --- | --- |
| **Why** | Propose `path::Symbol` tokens from Markdown path citations so human docs can link to code after review + `astloom sync` Phase 2 |
| **Required** | None (repo root via `ASTLOOM_ROOT` / package). For `--path`, the file must exist |
| **Flags** | `--path FILE` (single file; always reported). `--docs-root DIR` (default `docs` when scanning). `--include-all` (report files with zero new suggestions). `--apply` (merge into YAML frontmatter). `--json` |
| **Example** | `astloom docs-suggest-links` · `astloom docs-suggest-links --path docs/foo.md` · `astloom docs-suggest-links --docs-root backend/docs --include-all` · `astloom docs-suggest-links --apply` · `astloom docs-suggest-links --json` |
| **What you see** | Files with suggested new tokens; with `--include-all`, also already-linked / empty evidence. Apply reports `applied` vs `skipped_no_frontmatter` |
| **What changes** | Dry-run: nothing. `--apply`: frontmatter `linked_symbols` only when YAML frontmatter exists. Graph edges only after later `astloom sync` resolve |
| **Exit code** | `0` when zero new suggestions; `1` when any suggested token remains (CI-friendly dry-run) |
| **Normative refs** | `docs/07-code-knowledge-graph/41-hybrid-documentation-coverage.md`, `docs/07-code-knowledge-graph/03-ingestion-and-living-documentation-workflow.md` |

### `astloom docs-catalog`

**Retrieval helper:** cached frontmatter index (tags + closed lane enums). Does not invent `DOCUMENTED_BY`.

| | |
| --- | --- |
| **Why** | Let operators/agents narrow which Markdown to open using tags/lanes without loading full bodies |
| **Required** | None |
| **Flags** | `--refresh`, `--roots`, `--tag`, `--concern`, `--lifecycle`, `--audience`, `--phase`, `--doc-type`, `--query`, `--linked-only`, `--unlinked-only`, `--limit`, `--json` |
| **Example** | `astloom docs-catalog --refresh` · `astloom docs-catalog --roots handbook --tag api` · `astloom docs-catalog --query hybrid --json` |
| **Cache** | `<ASTLOOM_DATA_ROOT>/cache/docs-catalog.json` (default sibling `<install>-data`; override `ASTLOOM_DOCS_CATALOG_CACHE`; roots via `ASTLOOM_DOCS_CATALOG_ROOTS` or `--roots`) |
| **Vocabulary** | Observed from scanned frontmatter only — not a global hardcoded tag/lane list |
| **What changes** | `--refresh` rewrites the cache file only. **`astloom sync` builds the catalog at the start** (best-effort; sync still continues if catalog build fails) |
| **Normative refs** | `docs/07-code-knowledge-graph/42-documentation-catalog-and-lane-cache.md` |

### `astloom quality-audit`

**Operator UX law:** same word-mode pattern as `inventory` / `docs-standards` — no dashed mode flags; use `detail` and `save [<path>]`.

| | |
| --- | --- |
| **Why** | One command that **discovers and categorizes** docs + code quality problems: standards gate failures, soft/hard size budgets, missing `linked_symbols` when code paths are cited, design Mermaid without flow tables, invalid lanes, missing/invalid revision stamps, never-ingested code, stale edited code, low living-doc coverage |
| **Required** | None for docs half. Code half needs pinned software paths + sync filters (same as `inventory`); if unavailable, docs findings still print and code section is marked skipped |
| **Modes** | **Normal**: category counts + top findings. **Detail**: all findings with evidence. **Save**: write full text report (and JSON twin) to a path; bare `save` uses `.astloom/quality-audit/YYYY-MM-DD_HH-MM-SS.txt` |
| **Example** | `astloom quality-audit` · `astloom quality-audit detail` · `astloom quality-audit save` · `astloom quality-audit detail save /tmp/qa.txt` |
| **Categories** | `docs.standards`, `docs.size_soft`, `docs.size_hard`, `docs.linking_gap`, `docs.flow_table_gap`, `docs.lane_invalid`, `docs.revision_missing`, `docs.revision_invalid`, `code.never_ingested`, `code.stale_edited`, `code.low_symbol_docs`, `code.missing_embeddings` (when applicable) |
| **Exit code** | `0` when zero findings; `1` when any finding exists (CI-friendly) |
| **What changes** | Does **not** mutate the code graph. Best-effort **docs registry hygiene** runs first: `purge_docs_registry_fixture_noise` unregisters live-test fixture rows whose symbol/file path contains `never_linked`, `ghost_`, or `never_should_exist` (same helper on MCP `astloom_quality_audit` and sync follow-up). Result JSON may include `docs_registry_hygiene` (`deleted_count`, `deleted`, `errors`). `save` writes report files under the path you named (or `.astloom/quality-audit/`) |
| **Normative refs** | `docs/00-master-plan/10-documentation-standardization-procedure.md`; durable Tasks: `docs/01-core-data-model/09-automated-followup-task-lifecycle-and-retention.md`; embedding heal: `docs/07-code-knowledge-graph/77-sync-embedding-heal-operator-runbook.md` |

### `astloom followup-tasks`

Operator surface for automated follow-up Tasks created by `sync` / `astloom_quality_audit` (`retention_class=automated_followup`).

| | |
| --- | --- |
| **Why** | Inspect, migrate legacy, reconcile (cancel cleared debt), and purge terminal automated Tasks without a full sync |
| **Required** | Scope optional (defaults from identity/env/connect). Destructive writes: `purge` and `adopt-legacy` need `--yes` (or use `--dry-run`) |
| **Subcommands** | `list` · `status` · `adopt-legacy` · `reconcile` · `purge` |
| **Common flags** | `--origin all\|sync-followup\|mcp-quality` · `--status all\|open\|terminal` (`list`) · `--days N` (`purge`) · `--dry-run` · `--actor` · scope flags |
| **Example** | `astloom followup-tasks list --status open` · `astloom followup-tasks status` · `astloom followup-tasks adopt-legacy --dry-run` · `astloom followup-tasks reconcile --dry-run` · `astloom followup-tasks purge --days 30 --dry-run` |
| **What changes** | `list`/`status`: read-only JSON. `adopt-legacy`: stamps fingerprints on pre-lifecycle `Quality:` / sync-style titles, cancels dupes/orphans. `reconcile`: cancels open Tasks whose fingerprint is not in the active debt set. `purge`: hard-deletes terminal automated Tasks older than retention (`ASTLOOM_FOLLOWUP_TASK_RETENTION_DAYS`, default 30; `0` = never) |
| **Env** | `ASTLOOM_FOLLOWUP_TASK_RETENTION_DAYS` |
| **Normative refs** | `docs/01-core-data-model/09-automated-followup-task-lifecycle-and-retention.md` |

### `astloom stats`

**Operator UX law:** same word-mode pattern as `inventory` — no dashed mode flags; use `detail` and `save <path>` only.

| | |
| --- | --- |
| **Why** | Count **code + docs** on pinned software roots, show **language mix** (files, bytes, % of code), and **processed vs remaining** percents (done / edited / remaining + LLM symbols + embedding coverage) |
| **Required** | Sync filter file at each root (same as `sync` / `inventory`). At least one software path. Scope from identity/env/connect |
| **Modes** | **Normal**: totals + processing percents + per-language summary. **Detail**: same with per-language done/edited/remaining counts. **Save**: full report including per-root language tables |
| **Example** | `astloom stats` · `astloom stats detail` · `astloom stats save /tmp/stats.txt` · `astloom stats detail save /tmp/stats.txt` |
| **What you see** | Code/docs file counts and sizes; done/edited/remaining percents; Embeddings indexed/eligible/missing; each language’s share of code files (and bytes in detail/save). When `missing > 0`, section **Need embedding heal** with `Do this: astloom sync heal` |
| **What changes** | Nothing on the graph (read-only). `save` only writes the report file you named |
| **Embeddings heal** | Guidance only — run `astloom sync heal` to drain the backlog; see [77 sync embedding heal runbook](../07-code-knowledge-graph/77-sync-embedding-heal-operator-runbook.md) |

### `astloom connect`

| | |
| --- | --- |
| **Why** | Materialize coding-agent MCP configs from `<project>/.astloom/connect.yaml` (HTTPS or same-host local) |
| **Required** | For normal connect: TTY wizard or a connect config (create with `init`). For `--local`: Astloom checkout available |
| **Optional** | word `edit` or `init`, `PATH[,PATH…]` (comma-separated project dirs; default cwd), `--local`, `--config`, `--project`, `--server`, `--clients`, `--include-user-clients`, `--dry-run`, `--tenant`, `--workspace`, `--remote-root` |
| **Example (template)** | `astloom connect init` then edit `<checkout>/.astloom/connect.yaml` |
| **Example (dogfood)** | `astloom connect --local` (scope from `init` / identity / env — not hardcoded) |
| **Example (remote)** | `astloom connect` from the app repo (cwd = that project for MCP + sync pins) |
| **Example (multi)** | `astloom connect /opt/App1,/opt/App2` |
| **What changes** | Writes/merges MCP JSON under each project `.cursor/` / `.vscode/` (and optional user-global clients); pins software paths for sync; may register project on server; may ingest/sync depending on connect options |
| **If you change scope in connect.yaml** | Re-run `connect` so MCP env and registration match the new scope |

### `astloom sync`

| | |
| --- | --- |
| **Why** | Load or refresh the code graph for a repo root (auto chooses full vs incremental vs noop) |
| **Required** | Sync filter file at each sync root (see [Sync filters](#sync-filters)). At least one software path from `init` / `paths` (or override with `--path`). Scope defaults if identity/env already set |
| **Optional** | Word `heal` (full-project embedding heal after the same incremental file pass), `--path` (repeatable override; default = pinned paths), bare `max-file <n>` (omit = **auto** discovery up to 20 000; explicit `N` caps), `--progress-interval`, `--allow-cloud-llm`, `--skip-nonconforming`, `--sync-nonconforming`, `--exclude-dir`, `--include-path`, `--include-ext`, scope flags |
| **Example** | `astloom sync`, `astloom sync heal`, `astloom sync max-file 200`, or `astloom sync --path /opt/MyApp` |
| **Embeddings** | Normal `sync` heals embeddings for touched files only (noop: capped backlog). `sync heal` runs full-project missing/mismatch + orphan cleanup without re-parsing healthy hash-stable files — see [Sync vs sync heal](./42-astloom-cli-command-reference-part-4.md#sync-vs-sync-heal) and [77 sync embedding heal runbook](../07-code-knowledge-graph/77-sync-embedding-heal-operator-runbook.md) |
| **What changes** | Phase 1: upserts code symbols/edges/embeddings. Phase 2 (when `docs.match` is non-empty): indexes human Markdown in docs-sync and projects `DOCUMENTED_BY` for resolved `linked_symbols`. After standards gate: best-effort automated follow-up Tasks (`create_sync_followup_tasks`) + local mirror `.astloom/quality-followup-tasks.json` (reconcile/purge per lifecycle doc 09) |
| **If you change `--path` or scope** | You sync a different tree or different isolation bucket; previous scope data remains |
| **Software preflight** | If Compose/MCP are not fully running, an interactive TTY asks `Start software now? [y/N]`. `y`/`yes` runs `astloom service start` first, then sync. Decline or non-TTY → exit with a hint to start services manually. After start, prints each component’s **start time to the second** (`postgres`, `neo4j`, `MCP HTTP`) |
| **Cloud LLM consent** | Non-private LLM routes (non-loopback host or non-local model prefix) fail closed until the operator consents. Interactive TTY shows **tenant**, **workspace**, **project**, **software path(s)**, API host, and models, then requires **two** yes answers: (1) allow cloud LLM for this run, (2) confirm the scope IDs in use. Sync starts only after both. `--allow-cloud-llm` skips both prompts (scripts). Non-TTY without the flag → exit with a hint. **Skip:** when preflight has no code edited/remaining **and** LiteLLM embeddings are disabled (noop / docs-only human sync cannot send code prompts). Structural sync without living docs: `ASTLOOM_LITELLM_DOCS_ENABLED=false astloom sync` |
| **Standards gate** | Before Phase 1/2 ingest (local `astloom sync` and `astloom-client sync` content-push), runs Full-tier `docs-standards` on Phase-2-discovered Markdown that is audit-eligible: not README/AGENTS basename; not matching built-in or `docs.audit.exclude` globs from `astloom.sync.yaml`. Package README maps still sync (Phase 1 package-readme / Phase 2 discovery) but are not `docs_bad`. Precedence: CLI `--skip-nonconforming` / `--sync-nonconforming` → (planned) Astloom Client project preference Skip/Ingest → interactive TTY ask (default **N** = include / do not skip) → non-TTY include (CI-safe). Report field `standards_gate` records counts. Skill `astloom-standards-on-edit` remediates on edit so skipped paths can sync later. Normative Client + watcher policy: [`../07-code-knowledge-graph/51-client-standards-gate-and-watcher-policy.md`](../07-code-knowledge-graph/51-client-standards-gate-and-watcher-policy.md) |
| **Before sync** | Prints a **work-only** preview: scope/paths, **Need sync** (code/docs pending), remaining undocumented LLM symbols when any, and **Need embedding heal** when searchable symbols lack rows (plain sync → `Do this: astloom sync heal`; already `heal` → this-run full heal note). Not already-synced totals or language inventory (use `astloom stats` for full snapshot) |
| **Cold start** | Default local BGE embeddings may download/load a HuggingFace model on first sync (can take minutes). For a fast operator check: `ASTLOOM_EMBEDDING_PROVIDER=stub astloom sync max-file 50` |
| **Progress** | While syncing, prints `%` / **code** or **docs** done/total / ETA / rate about every **30s** (override with `--progress-interval`). Phase 1 (code ingest) and Phase 2 (human docs link) each get their own progress block; the tracker resets rate/ETA between phases. Both phases use ``sync_max_file_workers`` (see ``ASTLOOM_SYNC_MAX_FILE_WORKERS`` / CPU percent); Phase 2 docs-sync writes run concurrently (Postgres per-thread connections; in-memory store ``RLock``). **done/total** and the queue line show **only work this run processes** (`new` / `changed` / code `lang_backfill` / docs `link_refresh`). Already-synced hash-stable paths are omitted from the queue and progress denominator. Docs body-stable without `linked_symbols` are not enqueued; body-stable linked docs may still refresh edges/anchors (`link_refresh`) but skip re-embed when the body hash matches. Full inventory stays on `astloom stats`. Each block is blank-line separated and includes wall-clock `at YYYY-MM-DD HH:MM:SS` plus `elapsed`. **ETA** uses a blend of **lifetime average** (`done/elapsed`, weight 0.65) and **recent-window average** (~60s, weight 0.35), lightly EWMA-smoothed — resists one slow file, still tracks sustained slowdowns; before any completion, rate is marked `provisional`. `astloom status` shows a Live sync section if another sync is running. **`astloom-client sync`** uses the same `SyncProgressTracker` / `print_progress_line` UI over HTTPS: default discovers the full tree (auto/`HARD_SYNC_MAX_FILES`), splits `ingest-push` into size-capped batches (`push batch i/N`), streams NDJSON progress per batch, and only sends `present_paths`+`inventory_complete` when the inventory is authoritative. Design: [auto discovery + prune](../superpowers/specs/2026-08-10-client-sync-auto-discovery-inventory-design.md). Server operators watch live jobs with `astloom sync jobs` (part 4). Honors `--progress-interval` the same way |
| **Usage log** | Each sync writes one JSON file named by **execution time** (`YYYY-MM-DD_HH-MM-SS.json`) under `ASTLOOM_SYNC_USAGE_LOG_DIR` (default `<ASTLOOM_DATA_ROOT>/sync-usage`). Record field `execution_at` is date+time to the second. Folder cap: `ASTLOOM_SYNC_USAGE_LOG_DIR_MAX_BYTES` (default **5 GiB**, FIFO deletes oldest files). Gitignored |
| **Filters** | Mandatory YAML + wildcards + built-in language excludes — [Sync filters](#sync-filters) |

### `astloom llm test`

| | |
| --- | --- |
| **Why** | Verify which LiteLLM model the root `.env` resolves and that a one-shot completion works |
| **Required** | None (uses `ASTLOOM_LITELLM_*` from `.env`) |
| **Optional** | `--prompt` (default `Hi`), `--model` (override `ASTLOOM_LITELLM_DEFAULT_MODEL`) |
| **Example** | `astloom llm test` |
| **What you see** | JSON with `ok`, `configured_model`, `model`, `api_base`, `api_key_configured`, `reply`, `usage` (or `error` on failure) |
| **What changes** | Nothing local; one provider completion request |

### `astloom llm sessions`

| | |
| --- | --- |
| **Why** | Inspect in-flight / recent RPM LiteLLM sessions during sync or from the running code-graph service |
| **Required** | None |
| **Example** | `astloom llm sessions` |
| **What changes** | Nothing (read-only) |

### `astloom purge`

| | |
| --- | --- |
| **Why** | Wipe graph data for one scope so a clean `sync` can rebuild |
| **Required** | `--yes` (safety latch) |
| **Optional** | Scope flags |
| **Example** | `astloom purge --yes` |
| **What changes** | Deletes graph content for that tenant/workspace/project (not your source files; not unrelated scopes) |
| **If you omit `--yes`** | Command refuses to wipe |

### `astloom destroy-profile`

| | |
| --- | --- |
| **Why** | Remove a chosen scope **ID** and all **Astloom profile / platform data** tied to it when you are done with that profile |
| **Required** | Interactive terminal: type **two different** confirmation phrases (not `--yes` flags). Scope from flags or identity/env defaults |
| **Optional** | `--tenant` `--workspace` `--project` |
| **Example** | `astloom destroy-profile --tenant acme --workspace eng --project astloom` then type `DELETE PROFILE DATA`, then type `acme/eng/astloom` |
| **What is deleted (profile data only)** | Code-graph symbols/edges/embeddings for this scope; `.astloom/projects/...` Usage Profile state; `~/.astloom/identity.yaml` if it pins this scope; matching `ASTLOOM_*` scope keys in repo `.env`; matching `scope` in `connect.yaml`; Astloom entries in this repo’s IDE `mcp.json` files |
| **What is NOT deleted** | Your **source code**, git history, unrelated files, or data for other tenant/workspace/project IDs |
| **If a confirmation is wrong or stdin is not a TTY** | Exits; **nothing** is deleted |
| **Afterward** | Run `astloom init --tenant … --workspace … --path …` again to choose new IDs/roots, then `connect` / `sync` |

### `astloom list-profiles`

| | |
| --- | --- |
| **Why** | See which local **tenant/workspace/project** profiles exist and which one is active (before destroy or switch) |
| **Required** | None |
| **Optional** | `--json`, `--verbose` |
| **Example** | `astloom list-profiles` |
| **What you see** | Active scope; each registered profile’s IDs, Usage Profile id, status, display name; `*` marks the active row. Also surfaces identity-only pins with no project file yet |
| **Not the same as** | `astloom profile list` (catalog of Usage Profile *templates*). `list-profiles` = your local instances |
| **What changes** | Nothing (read-only) |

### `astloom profile list` / `astloom profile show <id>`

| | |
| --- | --- |
| **Why** | Inspect Usage Profile catalog (which MCP tools / packs a profile enables) |
| **Required** | `show` needs `profile_id` |
| **Example** | `astloom profile list` · `astloom profile show programming-cursor-mcp` |
| **What changes** | Nothing (read-only) |

### `astloom project register`

| | |
| --- | --- |
| **Why** | Create local project state without going through `init` (multi-project / explicit setup) |
| **Required** | `--tenant` `--workspace` `--project` |
| **Optional** | `--name`, `--usage-profile`, `--domain-pack`, `--feature-profile`, `--force` |
| **Example** | `astloom project register --tenant acme --workspace eng --project payments --name "Payments" --usage-profile programming-cursor-mcp` |
| **What changes** | Writes `.astloom/projects/<tenant>/<workspace>/<project>.json` |
| **If you change IDs** | Creates a **new** project file; does not migrate the old one |

### `astloom project activate`

| | |
| --- | --- |
| **Why** | Bind a Usage Profile onto an existing project state |
| **Required** | Scope flags + `--usage-profile` |
| **Example** | `astloom project activate --tenant acme --workspace eng --project payments --usage-profile programming-cursor-mcp` |
| **What changes** | Updates the project state file’s profile fields |

### `astloom project show` / `astloom project effective`

| | |
| --- | --- |
| **Why** | Inspect saved state vs resolved effective profile |
| **Required** | Scope flags |
| **Example** | `astloom project show --tenant acme --workspace eng --project payments` |
| **What changes** | Nothing (read-only) |

### `astloom cursor export`

| | |
| --- | --- |
| **Why** | Export an `mcpServers` JSON fragment for Cursor without full `connect` |
| **Required** | Scope flags |
| **Optional** | `--out` |
| **Example** | `astloom cursor export --tenant acme --workspace eng --project payments --out ~/.cursor/astloom-mcp.json` |
| **What changes** | Writes the `--out` file when provided; otherwise prints JSON |

## Related Documents

- Continued command catalog: `docs/08-software-engineering-architecture/42-astloom-cli-command-reference-part-4.md`
