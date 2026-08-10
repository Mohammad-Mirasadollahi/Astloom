---
doc_id: as.doc.sea.backend-di-composition-hld
title: 46 - Backend DI Composition High Level Design
doc_type: hld
status: draft
schema_version: '1.0'
owner: platform-architecture
summary: 'Phases A–D shipped: process composition roots, ServiceContainer, FastAPI/MCP adapters,
  ports.'
tags:
- dependency-injection
- composition-root
- hld
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/46-backend-di-composition-high-level-design.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols:
- backend/services/code-graph-service/src/code_graph_service/bootstrap.py::build_service
related_docs:
- as.doc.sea.backend-di-composition-feature-spec
- as.doc.sea.backend-di-composition-lld
- as.doc.sea.backend-di-composition-risks
- docs/08-software-engineering-architecture/30-dependency-injection-and-composition-root.md
doc_version: 1.0.1
audience:
- engineer
- architect
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 46 - Backend DI Composition High Level Design

## Implementation status

**Phases A–D shipped** for code-graph, MCP, thin-service composition roots, port
hygiene (`ports.py` + allowlisted `PostgresStore` imports), and CLI process-scoped
container reuse.

## Purpose

Describe the runtime topology for Dependency Injection across Astloom Python
processes without introducing a third-party IoC container.

## Architecture overview

```mermaid
flowchart TB
  subgraph process [Deployable process]
    settings[Settings]
    root[Composition root]
    container[ServiceContainer]
    settings --> root --> container
    subgraph app_layer [Application]
      uc[Use cases / handlers]
    end
    subgraph ports_layer [Ports]
      storePort[Store port]
      llmPort[LLM port]
      clockPort[Clock port]
    end
    subgraph infra [Infrastructure adapters]
      neo[Neo4jStore]
      pg[PostgresStore]
      litellm[LiteLLM gateway]
    end
    container --> uc
    uc --> storePort
    uc --> llmPort
    uc --> clockPort
    storePort --> neo
    storePort --> pg
    llmPort --> litellm
  end
  http[FastAPI / MCP / CLI] --> container
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Bootstrap | Bind settings → adapters → use cases | `ServiceContainer` |
| 2 | HTTP/MCP/CLI | Hold container for process lifetime | Single wiring graph |
| 3 | Use case | Call ports only | Swappable adapters |
| 4 | Adapter | Talk to Neo4j/Postgres/LiteLLM | Infra isolated |

## Components

| Component | Responsibility |
| --- | --- |
| Settings | Typed env validation; no I/O beyond reading mapping |
| Composition root | Only place allowed to `new` infrastructure clients |
| ServiceContainer | Frozen bundle of application services and shared adapters |
| Ports | Protocols / ABCs owned by application or domain |
| Adapters | Implement ports; live under `infrastructure/` or `*_store.py` |
| Framework adapter | FastAPI lifespan / MCP server ctor attaches container |

## Process variants

| Process | Composition root today (as-is anchor) | Target |
| --- | --- | --- |
| code-graph HTTP | `code_graph_service.bootstrap` | `build_container` + `build_app(container)` |
| MCP gateway | `mcp_gateway_service.store_factory` + server ctor | One root producing `StoreBundle` + backends |
| Thin microservice | `*_service.bootstrap.build_service` | Same pattern; shared checklist |
| CLI (`astloom`) | Command modules call services | Commands receive container or call root once |

## Dependency rules

- Application → ports (OK)
- Infrastructure → ports implementations (OK)
- Application → infrastructure concrete classes (**forbidden**)
- Framework adapter → composition root (**OK**, only at edge)
- Domain → framework FastAPI/MCP types (**forbidden**)

## Lifetimes

| Lifetime | Examples |
| --- | --- |
| Process | DB pools, Neo4j driver, LiteLLM gateway, embedding model |
| Request/job | Correlation id, scoped auth claims (not new DB engines) |
| Transient | Pure value objects, command DTOs |

## Failure modes (design)

| Failure | Handling |
| --- | --- |
| Missing env | Fail at Settings validation before binding adapters |
| Adapter construct error | Fail boot; do not serve half-wired app |
| Handler imports Store | Caught by import gate in Phase A/B |
| Accidental second root | Single `build_app` entry; tests assert one container identity |

## Related Documents

- `45-backend-di-composition-feature-specification.md`
- `47-backend-di-composition-low-level-design.md`
- `48-backend-di-composition-risks-challenges-and-acceptance.md`
- `30-dependency-injection-and-composition-root.md`
