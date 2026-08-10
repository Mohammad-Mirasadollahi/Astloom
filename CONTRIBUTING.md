# Contributing to Astloom

Thank you for helping improve Astloom. This guide covers how to propose changes, report bugs, and request features.

## Ways to contribute

| Path | Use when |
|------|----------|
| [Bug report](.github/ISSUE_TEMPLATE/bug_report.yml) | Something is broken, incorrect, or regressing |
| [Feature request](.github/ISSUE_TEMPLATE/feature_request.yml) | You want new product or platform behavior |
| Pull request | You have a concrete fix or slice ready for review |
| [SECURITY.md](SECURITY.md) | Suspected vulnerability (do not file a public issue) |

## Before you start

1. Read the product boundary and roadmap:
   - [docs/00-master-plan/07-agent-control-plane-product-boundary.md](docs/00-master-plan/07-agent-control-plane-product-boundary.md)
   - [docs/00-master-plan/02-roadmap-and-phase-gates.md](docs/00-master-plan/02-roadmap-and-phase-gates.md)
2. Prefer extending an existing vertical slice over inventing a new service.
3. Follow backend structure and naming standards:
   - [backend/docs/STRUCTURE_STANDARD.md](backend/docs/STRUCTURE_STANDARD.md)
   - [docs/14-api-design-and-naming-standards/00-index.md](docs/14-api-design-and-naming-standards/00-index.md)
4. Keep secrets, customer data, and private runtime dumps out of issues, PRs, and commits.

## Development setup

```bash
bash install.sh
# or venv only: bash install.sh --skip-infra
```

See [39-local-install-runbook.md](docs/08-software-engineering-architecture/39-local-install-runbook.md).

Run the suite that owns your change (examples):

```bash
PYTHONPATH=backend/services/<service>/src .venv/bin/python -m pytest tests/backend/<service> -q
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/phase<N>-verification -q
```

See the root [README.md](README.md) for the full phase map and named commands.

## Coding rules (short)

- English only in source, comments, commits, and repo docs.
- No hard-coded ports, credentials, tenant IDs, project IDs, model names, or provider endpoints.
- Prefer stdlib and existing packages; do not add dependencies without a clear need.
- Put executable tests under `tests/backend/<owner>/`, not under service-local `tests/` trees.
- Ship required tests in the **same change** as production behavior (see [37-test-authoring-standard.md](docs/08-software-engineering-architecture/37-test-authoring-standard.md)).
- Keep diffs minimal and aligned with the service’s existing `core.py` / `api.py` / `testing.py` pattern.
- Update the relevant API contract or phase acceptance doc when behavior changes.

## Pull requests

1. Open an issue first for non-trivial work (bug or feature template).
2. Keep each PR focused on one concern.
3. Include:
   - what changed and why,
   - which phase/service/gate is affected,
   - exact pytest commands you ran and the result,
   - docs or contract updates when behavior changed.
4. Do not commit secrets, `.env` files, PAT files, or `scripts/.git-sync*` local credentials.
5. Do not upload repository contents to public cloud services unless maintainers explicitly approve that action.

Suggested PR title style:

```text
fix(core-data): keep decision supersede idempotent
feat(memory): add decay API for stale items
docs: clarify Phase 10 gap register exit checks
```

## Feature requests

Use the [feature request](.github/ISSUE_TEMPLATE/feature_request.yml) template and include:

- problem / job to be done,
- proposed behavior,
- affected phase or service,
- acceptance criteria,
- alternatives considered.

Maintainers may redirect large requests into the gap register or a phase design doc before implementation.

## Bug reports

Use the [bug report](.github/ISSUE_TEMPLATE/bug_report.yml) template and include:

- expected vs actual behavior,
- reproduction steps,
- environment (OS, Python, service, commit/SHA if known),
- failing command or log excerpt with secrets removed,
- severity / blast radius.

## Communication

- Prefer GitHub Issues for bugs and features.
- Prefer Pull Requests for concrete code or documentation changes.
- Security issues: follow [SECURITY.md](SECURITY.md) only.

## License

By contributing, you agree that your contributions are licensed under the same license as this repository ([LICENSE](LICENSE)).
