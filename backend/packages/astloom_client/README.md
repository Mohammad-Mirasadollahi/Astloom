# astloom_client

Thin CLI package for **client-only** Astloom installs (`install.sh --role client`).

## Purpose

Expose only connect / Usage Profile / process-lifecycle commands so a laptop cannot run server-admin Astloom operations. The PATH name on client-only hosts is **`astloom-client`** (bare `astloom` is not installed).

## Boundaries

| May | Must not |
| --- | --- |
| Parse allowlisted commands | Register `service`, `graph`, `mcp serve`, governance, … |
| Dispatch to shared `astloom_cli` handlers | Call local graph purge when `connect.yaml` has a remote `graph_url` |
| Own the PATH name `astloom-client` on `role=client` | Put bare `astloom` on PATH for client-only; replace full CLI on `server` / `both` |

## Start here

| File | Role |
| --- | --- |
| `main.py` | Console entry `astloom-client` |
| `parser.py` | Allowlisted argparse surface |
| `dispatch.py` | Route to `astloom_cli.commands.*` |

Shared allowlist / full-CLI gate: `astloom_cli/client_allowlist.py`.  
Remote purge: `astloom_cli/connect_flow/remote_purge.py`.  
Spec: `docs/superpowers/specs/2026-07-25-thin-client-cli-design.md`.  
Operator docs: `docs/08-software-engineering-architecture/36-astloom-cli.md`.
