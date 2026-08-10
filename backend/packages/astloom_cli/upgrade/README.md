# Astloom upgrade package

## Purpose

Server install upgrade, client↔server contract handshake, and control-plane
upgrade jobs (plan → approval → backup → deploy → smoke → evidence → rollback).

## Boundaries

- **May:** stamp `.astloom/install-state.env`, write jobs under
  `.astloom/upgrade-jobs/`, call `install.sh`, enqueue Accept gates.
- **Must not:** copy Compose secrets into backups; Dockerize coding-agent clients;
  treat product-version drift alone as a hard failure (contract is fail-closed).

## Start here

| File | Role |
| --- | --- |
| `versions.py` | Product/contract constants + install-state stamp |
| `compat.py` | Server↔client compatibility check |
| `engine.py` | Job state machine (hard module) |
| `../commands/upgrade.py` | CLI surface |
| Normative runbook | `docs/08-software-engineering-architecture/51-software-upgrade-server-and-client.md` |
