# Install

Path: `backend/runbooks/install`

## Purpose

Installation and bootstrap runbooks for Astloom operators and developers.

## Canonical operator guide

Use the modular root installer and its runbook:

- Entrypoint: [`install.sh`](../../../install.sh) at the repository root
- Modules: [`scripts/install/`](../../../scripts/install/)
- Runbook: [`docs/08-software-engineering-architecture/39-local-install-runbook.md`](../../../docs/08-software-engineering-architecture/39-local-install-runbook.md)
- Design target (broader zero-touch): [`docs/08-software-engineering-architecture/19-zero-touch-installation-and-bootstrap-automation.md`](../../../docs/08-software-engineering-architecture/19-zero-touch-installation-and-bootstrap-automation.md)

```bash
bash install.sh
bash install.sh --check
```

## Modular Boundary

This directory is part of the Astloom backend modular architecture. It must expose behavior through documented contracts, public interfaces, configuration, or events. It must not import private internals from sibling modules.

## Allowed Contents

- README and design notes for this boundary.
- Source, configuration, fixtures, tests, or generated artifacts that belong to this boundary.
- Subdirectories that follow the backend structure standard.

## Rules

- Keep ownership clear and local to this boundary.
- Do not hard-code ports, credentials, tenant IDs, project IDs, model names, provider endpoints, or feature behavior.
- Prefer dependency inversion: domain and application logic should not depend on infrastructure implementation details.
- Use shared packages only for stable contracts or cross-cutting primitives.
- Add or update tests and documentation when this boundary receives implementation code.

## Status

Operator path is implemented at repository root (`install.sh` + `scripts/install/`). This folder remains the runbook index pointer for backend-layout discovery.
