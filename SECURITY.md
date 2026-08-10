# Security Policy

## Purpose

This document defines the security expectations for Astloom development, deployment, and vulnerability handling.

## Supported Status

Astloom ships vertical-slice implementations and phase verification gates (see the root README). Security review covers architecture decisions, dependency choices, secret handling, deployment profiles, isolation boundaries, and the behavior of implemented services and catalogs.

## Reporting Security Issues

Do not disclose suspected vulnerabilities publicly before triage.

Security reports should include:

- affected component or document path.
- reproduction steps or threat scenario.
- expected impact.
- affected environment.
- relevant logs or evidence with secrets removed.
- suggested mitigation if known.

If a private reporting channel is configured later, this file must be updated with the official contact path.

## Security Baseline

Astloom implementation must follow these rules:

- Keep secrets out of source code, logs, generated documents, screenshots, and evidence bundles.
- Use environment variables or secret managers for credentials.
- Do not hard-code ports, credentials, tenant ids, project ids, model names, provider endpoints, or feature behavior.
- Enforce project isolation at every persistence, retrieval, cache, queue, and graph boundary.
- Apply authorization before returning memory, graph, metadata, document, or source-derived context.
- Store durable operational data in PostgreSQL.
- Store RAG embeddings in PostgreSQL with pgvector and enforce relational filters before ranking.
- Store code graph relationships in Neo4j and scope graph queries by project and repository.
- Use Redis only for ephemeral cache, coordination, locks, rate limits, and short-lived job state.
- Run infrastructure dependencies through Docker Compose or an equivalent orchestration profile for local development and integration testing.
- Avoid unsupported, deprecated, end-of-life, or unmaintained technologies.

## Dependency Security

Implementation manifests must pin exact versions through lockfiles or equivalent reproducible dependency mechanisms.

Dependency changes should include:

- compatibility review.
- security advisory review.
- migration notes when behavior changes.
- rollback notes for risky upgrades.
- test evidence for affected services.

## Agent And Memory Safety

Astloom agents must not persist arbitrary user-provided secrets into long-term memory. Memory writes must be governed by policy, project isolation, confidence, retention, and explicit source attribution.

Agent activity logs must be traceable without exposing secrets. Sensitive command output must be redacted before being stored in durable records or shared through the web interface.

## Infrastructure Security

Local development ports must use documented non-default Astloom ports. Vendor defaults such as PostgreSQL `5432`, Neo4j `7687` and `7474`, Redis `6379`, FastAPI `8000`, and Next.js `3000` must not be used as Astloom host ports unless an explicit deployment profile justifies it.

Docker profiles must not bake secrets into images. Runtime configuration must come from environment profiles, Compose overrides, or deployment configuration.

## Security Testing Expectations

When implementation code is added, security validation should include:

- dependency vulnerability scanning.
- secret scanning.
- static analysis for backend and frontend code.
- authorization tests for project isolation.
- integration tests for data boundary enforcement across PostgreSQL, pgvector, Neo4j, Redis, and object storage.
- audit logging tests for sensitive operations.

## Incident Handling

Security incidents should produce an evidence bundle containing timeline, affected components, impact, mitigation, regression tests, and follow-up actions. Evidence bundles must not contain raw secrets.
