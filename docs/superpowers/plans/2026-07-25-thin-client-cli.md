---
doc_id: as.doc.sea.thin-client-cli-plan
title: Thin Client CLI Implementation Plan
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-engineering
summary: Implementation plan for astloom_client thin entry, allowlist gate, remote purge,
  and client-role PATH shim.
tags:
- cli
- client
- plan
phase: 08-software-engineering-architecture
canonical_path: docs/superpowers/plans/2026-07-25-thin-client-cli.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols:
- backend/packages/astloom_cli/client_allowlist.py::client_command_allowed
- backend/packages/astloom_cli/main.py::main
- tests/backend/tools/astloom-cli/test_client_allowlist.py::test_client_allowlist_includes_process_and_profile_commands
- tests/backend/tools/astloom-cli/test_astloom_client_entry.py::test_thin_help_omits_server_commands
- backend/packages/astloom_cli/connect_flow/remote_purge.py::locked_scope_from_settings
- backend/packages/astloom_cli/commands/sync/cmd.py::cmd_sync
- tests/backend/tools/astloom-cli/test_client_purge_remote.py::test_scope_mismatch_hard_fails
- backend/packages/astloom_cli/commands/path_cmd.py::default_shell_rc_names
- backend/packages/astloom_client/main.py::main
related_docs:
- docs/superpowers/specs/2026-07-25-thin-client-cli-design.md
- docs/08-software-engineering-architecture/36-astloom-cli.md
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Thin Client CLI Implementation Plan

## Purpose

Ship the thin client CLI and security gates described in the design spec, with testable tasks for allowlist, packaging, remote purge, and PATH.

> **For agentic workers:** Inline execution in this session (user asked to write code).

**Goal:** Ship `astloom_client` thin entry for client-only installs; server/both keep full CLI with client workflows; secure remote purge for connected scope.

**Architecture:** Shared allowlist + remote purge helpers in `astloom_cli`; thin package only registers allowlisted parsers and dispatches; `path install` points client role at `astloom-client`; full `main` denies non-allowlisted cmds when `role=client`.

**Tech Stack:** Python 3.12, argparse, existing connect_flow SSH, pytest.

## Global Constraints

- Fail-closed scope lock on client purge (CLI flags must match connect.yaml or hard fail).
- No local GraphService purge on client path.
- Allowlist gate only when `install_role == client`.
- English identifiers/docs; no new deps.

---

### Task 1: Allowlist + full-CLI gate

**Files:**
- Create: `backend/packages/astloom_cli/client_allowlist.py`
- Modify: `backend/packages/astloom_cli/main.py`
- Test: `tests/backend/tools/astloom-cli/test_client_allowlist.py`

### Task 2: Thin package + pyproject

**Files:**
- Create: `backend/packages/astloom_client/{__init__,main,parser,dispatch,README}.py/md`
- Modify: `pyproject.toml`
- Test: `tests/backend/tools/astloom-cli/test_astloom_client_entry.py`

### Task 3: Remote purge

**Files:**
- Create: `backend/packages/astloom_cli/connect_flow/remote_purge.py`
- Modify: `backend/packages/astloom_cli/commands/sync/cmd.py`, `connect_flow/__init__.py`
- Test: `tests/backend/tools/astloom-cli/test_client_purge_remote.py`

### Task 4: PATH for client role

**Files:**
- Modify: `backend/packages/astloom_cli/commands/path_cmd.py`
- Test: extend path tests or `test_path_install_client_role.py`

### Task 5: Verify + rsync client host
