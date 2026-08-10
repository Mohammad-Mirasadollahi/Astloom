# Astloom install modules

Entrypoint options:

- **Empty machine:** [`../get-astloom.sh`](../get-astloom.sh) (curl|bash) — choose `release` or `main`, then runs root `install.sh`
- **Already cloned:** repository root [`../../install.sh`](../../install.sh) → [`load.sh`](load.sh)

| Module | Responsibility |
|--------|----------------|
| [`../get-astloom.sh`](../get-astloom.sh) | Fetch from GitHub (`release` = latest Release tag tarball; `main` = branch tip); preserve `.astloom/`, `.env`, compose `.env.local`, `.venv` |
| [`common.sh`](common.sh) | Logging, root paths, state file, secret helpers, root/sudo runner |
| [`01_prerequisites.sh`](01_prerequisites.sh) | Check/install Python 3.12+, curl, git; Docker/Compose only when **server** (not client / `--skip-infra`) |
| [`02_venv.sh`](02_venv.sh) | Create `.venv`, install deps, editable `astloom` CLI; seed `.env` + `astloom.sync.yaml` from examples |
| [`03_compose_env.sh`](03_compose_env.sh) | Seed repo templates; create `backend/deployments/compose/.env.local` with generated secrets + `ASTLOOM_DATA_ROOT` |
| [`04_docker_infra.sh`](04_docker_infra.sh) | `docker compose --profile core up` for Postgres + Neo4j, wait healthy |
| [`05_verify.sh`](05_verify.sh) | `astloom doctor` + infra re-check; optional ai-toolstack |
| [`06_runtime_bringup.sh`](06_runtime_bringup.sh) | Ensure JWT+bootstrap secrets (preserve on upgrade); optional API key mint; host MCP or Docker `mcp-gateway`; PATH |
| [`load.sh`](load.sh) | Source order + stage orchestration (`all`, `upgrade`, `stage`, …) |

Python helper: [`backend/packages/astloom_cli/install_auth.py`](../../backend/packages/astloom_cli/install_auth.py) (`ensure_server_auth_secrets`, `mint_install_api_key`).

Add new install steps in the smallest matching module. Keep root `install.sh` as flags + exit codes only.

**Auth on server/both:** JWT signing secret (`.astloom/mcp-http.secret`) and connect-bootstrap secret (`.astloom/connect-bootstrap.secret`) are **auto-created when missing**. Interactive install asks whether to mint an API key (`as1.*`); use `--mint-api-key` / `--no-mint-api-key` unattended. **Upgrade never regenerates** existing secrets and skips API key mint unless `--mint-api-key`.

**Upgrade:** `bash install.sh --upgrade` backs up `.astloom/install-state.env` (and auth secret copies under `upgrade-backups/…/auth/`), re-runs stages, then `astloom upgrade finalize`. Control-plane / client paths: `astloom upgrade …` (see docs/08…/51-software-upgrade-server-and-client.md). To refresh code from GitHub first, re-run `get-astloom.sh` with the same channel.

**Install-root marker:** after verify/runtime stages, install writes a readable
`install-root` file under `<ASTLOOM_ROOT>/.astloom/` and `$HOME/.astloom/`
(and `SUDO_USER` home when installing via sudo). Client `astloom connect`
discovers that path over SSH after password/key setup — operators are never
prompted for the remote Astloom root (missing marker → clear error; optional
`server.remote_root` in connect.yaml as override). Local checkout path for
`get-astloom.sh` defaults to `/opt/Astloom` (override with `--root` /
`ASTLOOM_ROOT`; no interactive prompt).

**Data root:** server/both install prompts for a durable directory (Enter =
sibling `<install>-data`, e.g. `/opt/Astloom-data`) or accepts `--data-root` /
`ASTLOOM_DATA_ROOT`. Postgres, Neo4j, usage logs, and caches
live there. Install stamps `<ASTLOOM_ROOT>/.astloom/data-root` and persists
`data_root=` in `install-state.env` so remote `astloom-client sync` stages to
the correct path. The sibling data tree is outside the checkout, so
`get-astloom.sh` refresh does not overwrite it.

| Related | Path |
|---------|------|
| Operator guide | [`docs/08-software-engineering-architecture/39-local-install-runbook.md`](../../docs/08-software-engineering-architecture/39-local-install-runbook.md) |
| Upgrade guide | [`docs/08-software-engineering-architecture/51-software-upgrade-server-and-client.md`](../../docs/08-software-engineering-architecture/51-software-upgrade-server-and-client.md) |
| E2E smoke | [`tests/e2e/install/run-install-smoke.sh`](../../tests/e2e/install/run-install-smoke.sh) |
| Pytest smoke | [`tests/backend/tools/install/test_install_smoke.py`](../../tests/backend/tools/install/test_install_smoke.py) |
| Get/bootstrap tests | [`tests/backend/tools/install/test_get_astloom.py`](../../tests/backend/tools/install/test_get_astloom.py) |
