---
doc_id: as.doc.stack.runtime-messaging-observability-and-deployment-stack
title: 05 - Runtime, Messaging, Observability, And Deployment Stack
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the runtime and operational stack for Astloom services, workers,
  messaging, deployment, observability, and automation.
tags:
- standard
- stack
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/05-runtime-messaging-observability-and-deployment-stack.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 05 - Runtime, Messaging, Observability, And Deployment Stack

## Purpose

This document defines the runtime and operational stack for Astloom services, workers, messaging, deployment, observability, and automation.

## Runtime Stack

| Area | Preferred Technology | Role |
| --- | --- | --- |
| Container runtime | Docker-compatible containers | reproducible service packaging |
| Local orchestration | Docker Compose profiles | local development and integration tests |
| Production orchestration | Kubernetes | scalable service deployment, health checks, secrets integration, autoscaling |
| Infrastructure as code | Terraform | cloud and infrastructure provisioning |
| Deployment packaging | Helm or Kustomize | Kubernetes release packaging |
| Service instrumentation | OpenTelemetry | traces, metrics, logs, correlation ids |
| Metrics | Prometheus-compatible metrics | service health, queues, jobs, model calls, token usage |
| Dashboards | Grafana | operational dashboards and reporting visibility |
| Logs | Loki-compatible or OpenTelemetry logs | structured logs and diagnostics |
| Traces | Tempo-compatible or OpenTelemetry traces | distributed tracing across services and agents |

## Messaging And Job Processing

Astloom should support event-driven and job-driven processing. Messaging requirements include durable events, retries, dead-letter handling, replay, idempotency, and correlation ids.

Preferred direction:

- Use a durable message broker for service events, workflow events, indexing jobs, docs sync jobs, memory consolidation, connector sync, reporting projections, and agent orchestration events.
- For production event streaming, use a durable broker profile such as NATS JetStream, Redpanda, Kafka-compatible infrastructure, or RabbitMQ depending on operational needs.

The exact broker can be selected by deployment profile, but event contracts, idempotency, outbox/inbox, and dead-letter behavior are mandatory.

## Observability Requirements

Every service must emit:

- structured logs with correlation ids.
- metrics for requests, jobs, queues, retries, dead letters, database latency, cache hit rate, graph ingestion, embedding calls, token usage, and RAG latency.
- traces across API calls, workers, broker messages, model calls, graph queries, and database operations.
- health and readiness endpoints.
- version and config-profile summary endpoints without secrets.

## Deployment Profiles

Astloom should support these profiles:

- local development: Docker Compose, local PostgreSQL with pgvector, Neo4j, optional Redis, optional object storage, and optional observability services.
- integration test: isolated containers and seeded test data.
- staging: production-like topology with isolated data and secrets.
- production: Kubernetes, managed PostgreSQL where possible, object storage, observability stack, and secret manager.

## Secrets And Configuration

Secrets must come from environment-specific secret stores. Configuration should be layered through profiles and validated at startup. Runtime values such as ports, endpoints, model names, feature flags, scoring weights, and retention policies must not be hard-coded.

## Automation Requirement

Installation and deployment should be automated through scripts, profiles, and runbooks. The first-run bootstrap should create required schemas, validate extensions such as pgvector, verify PostgreSQL connectivity, verify Neo4j connectivity, and verify Redis connectivity when the cache profile is enabled, create service profiles, and produce an evidence report.

## Port Rule

Development must not assume framework default ports. Port profiles must be configurable, project-scoped, and validated before services start.


## Local Venv And Docker Rule

Local Python dependencies must be installed inside `/root/Astloom/.venv`. Local PostgreSQL, Neo4j, Redis, and supporting infrastructure must run through Docker Compose profiles or an equivalent container orchestration profile. Newly exposed development host ports must be non-default, configurable, and validated before startup.

See `06-local-venv-docker-and-port-policy.md` for the required local runtime policy.
