---
doc_id: as.doc.sea.module-contract-docstrings
title: 49 - Module Contract Docstrings Standard
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-engineering
summary: 'Normative Astloom standard for selective module-level contract docstrings: default-skip
  hard-module test, three-axis template (role, source of truth / invariants, allowed vs forbidden
  failures), anti-patterns, freshness, and how this layer relates to WHY/NOTE/HACK and Markdown.'
tags:
- documentation
- docstring
- in-source
- agents
- contracts
- authoring
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/49-module-contract-docstrings-standard.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.sea.package-folder-readme
- as.doc.agents.team-handout-astloom-documentation-complete
- as.doc.ckg.hybrid-documentation-coverage
- as.doc.ckg.ingestion-and-living-documentation-workflow
- as.doc.sea.engineering-best-practices-and-implementation-standards
- as.doc.sea.data-persistence
language: en
security_classification: internal
doc_version: 1.1.1
audience:
- engineer
- architect
- agent
updated_at: 2026-08-10
---

# 49 - Module Contract Docstrings Standard

## Purpose

Define when and how Astloom modules **must** carry a short **module-level contract docstring**
so coding agents and humans learn non-obvious system contracts without reading the whole file
or inventing the wrong source of truth.

This standard is **selective** and **default-deny**. It does **not** require a module docstring on
every file. **If the Hard Module Test fails, do not write a header.** Signal density beats volume:
stale or obvious headers lower agent quality.

In-source tagged rationale (`# WHY:` / `# NOTE:` / `# HACK:`) and Full-tier Markdown under
`docs/` remain separate layers (see Related Documents). This document owns only the
**module header contract** pattern.

## Goals And Non-Goals

### Goals

- Raise agent edit quality on hard modules (queues, workers, dual-store durability, state machines,
  trust boundaries, fail-open / fail-closed policy).
- Give a fixed three-axis template so headers stay short and comparable.
- Keep English-only committed source aligned with project language law.
- Make freshness an explicit duty when contracts change.
- Make **skip** the default so agents do not stamp low-importance files.

### Non-Goals

- Replacing `# WHY:` / `# NOTE:` / `# HACK:` rationale comments (statement-level intent).
- Replacing Full-tier design / LLD Markdown under `docs/`.
- Mandating module docstrings on CRUD mappers, DTO-only modules, constants, thin re-exports,
  parsers without trust policy, CLI arg wiring, or other files whose behavior is obvious from
  names and types.
- Long architecture essays in source (those belong in `docs/`).
- Per-file encyclopedias in folder `README.md` files (those are rejected; see `50-package-folder-readme-standard.md`).

## Decision Flow

```mermaid
flowchart TD
  start[Editing, adding, or reading a Python module] --> doubt{Hard Module Test: any YES?}
  doubt -->|no or unsure| skip[MUST NOT add module contract docstring]
  doubt -->|yes| has{Contract docstring present and accurate?}
  has -->|no| write[Write or fix 3-6 line contract docstring same turn]
  has -->|yes| keep[Keep; update only if this change alters contract]
  write --> axes[Cover role + SoT/invariants + failure policy]
  axes --> done[Done for this layer]
  keep --> done
  skip --> done
```

| Step | Condition | Action |
| --- | --- | --- |
| 1 | Hard Module Test = **no** or **unsure** | **MUST NOT** add a module contract docstring |
| 2 | Hard Module Test = **yes**, missing or wrong header (on edit **or** on Read) | Write/fix 3–6 lines using the three-axis template in the **same turn** |
| 3 | Hard module, header still true after the change | Leave it; do not expand for style |
| 4 | Change alters SoT, wake path, or fail policy | Update the docstring in the **same** change |

## Hard Module Test (required gate)

**Default answer: no → skip.**

A module is **hard** only when **at least one** question below is a clear **yes**. If you are
unsure, treat the answer as **no** and **do not** invent a header.

| # | Question (yes ⇒ hard) |
| --- | --- |
| 1 | Does this file own a **durable SoT** vs a **wake/cache** layer that agents often swap? |
| 2 | Does it define **queue / worker / outbox / inbox / lease / poison** behavior? |
| 3 | Does it encode an explicit **fail-open** or **fail-closed** policy that must not be “simplified”? |
| 4 | Does it own a **state machine / ticket lifecycle** with durable states? |
| 5 | Is it a **trust boundary** (authz, tenant isolation, approval, secret redaction entry)? |
| 6 | Does it enforce **non-obvious exclusivity** (single-flight, fencing, sticky shard)? |

A module **should** become hard (add a header) only when agents have **already** mis-edited it
for the wrong SoT or crash policy — not because the file “feels important.”

### When Required (after a yes)

When the Hard Module Test passes, the file **must** have a module-level contract docstring.

| Trigger (maps to test) | Examples |
| --- | --- |
| Dual durability / wake path | DB is SoT; Redis LIST is a wake signal rebuilt from DB |
| Worker / queue / outbox / inbox | One-at-a-time analysis queue; lease reclaim; poison handling |
| Explicit fail-open or fail-closed | Redis timeout fails open to DB poll; authz fails closed |
| State machine or ticket lifecycle | `queued` / `analyzing` as durable states |
| Trust boundary or security policy | Tenant isolation seam; approval gate; secret redaction entry |
| Non-obvious ordering or exclusivity | Single-flight, fencing token, sticky shard |

### When To Skip (MUST NOT write)

**MUST NOT** add a module contract docstring when **any** of the following is true (even if the
file sits next to a hard module):

| Skip class | Examples |
| --- | --- |
| Pure helpers / utils | Path join, string normalize, small pure transforms |
| Schemas / DTOs / models | Pydantic models, TypedDicts, dataclass bags with no policy |
| Thin re-exports | `__init__.py` that only imports/exports |
| Thin HTTP/MCP/CLI wiring | Route registration, argparse, request/response mapping with no local durability policy |
| Fixtures / tests / generated | `conftest.py`, generated clients, protobuf stubs |
| Obvious from names/types | CRUD mapper whose SoT is the function name alone |
| Already covered neighbor | Sibling file has the SoT header **and** this file adds no extra failure/trust contract |
| Restating README or docs | Copying architecture from `docs/` into every leaf file |

Do **not** paste the same essay into every related file. One SoT header at the ownership seam.

**Doubt rule:** Prefer **skip** over a weak header. A missing header on a non-hard file is correct;
a decorative header is debt.

## Three-Axis Template

Module docstring (Python triple-quote at file top, after shebang/`from __future__` if any):
**3–6 lines**, English, covering all three axes:

1. **Role** — what this module owns in one sentence.
2. **Source of truth / invariants** — which store or state is authoritative; what must stay true.
3. **Allowed vs forbidden failures** — what may fail open, what must never be treated as an unexpected crash, what must fail closed.

Optional fourth line only if needed: **wake / rebuild / recovery** hint (e.g. rebuild queue from DB on startup).

Do not narrate line-by-line implementation. Do not list every function. Do not market the feature.

## Normative Example

Good (hard module — dual store + fail-open):

```python
"""
Persistent MA analysis queue — one malware sample at a time.

Durability: PostgreSQL ticket status (`queued` / `analyzing`) is the source of truth.
Redis LIST (`ma:analysis:queue`) wakes the worker; rebuilt from DB on startup.
Redis timeouts/disconnects fail-open to DB poll — never treated as unexpected crashes.
"""
```

Why this works for agents:

- Names the **unit of work** (one sample at a time).
- Pins **SoT** (Postgres ticket status) vs **wake layer** (Redis LIST).
- States **recovery** (rebuild from DB).
- States **failure policy** (fail-open; not a crash).

### Anti-Patterns

| Bad | Why |
| --- | --- |
| `"""Queue helpers."""` | No contract; agents invent SoT |
| Header on a helper/DTO/`__init__` that failed the Hard Module Test | Decorative noise; delete it |
| Restating `def enqueue(...):` in the module header | Noise; use function docstring or `# WHY:` |
| Multi-page architecture in the module string | Belongs in `docs/`; will go stale |
| Persian or mixed-language committed docstring | Violates English-only source law |
| Header that contradicts the code | Worse than none — delete or fix in the same change |
| Writing a header “just in case” when unsure | Violates default-deny; prefer skip |

## Relation To Other In-Source Layers

| Layer | Form | Owns |
| --- | --- | --- |
| **Module contract docstring** (this standard) | File-top `"""…"""` | Module SoT, invariants, failure policy |
| **Public API docstring** | Function/class docstring | Inputs, outputs, raised errors |
| **Tagged rationale** | `# WHY:` / `# NOTE:` / `# HACK:` | Local non-obvious intent → `RATIONALE` on ingest |
| **Stopgap** | `# tsoc-defer: …` | User-approved temporary debt only |
| **Human Markdown** | `docs/…` Full-tier | Architecture, APIs, runbooks, evidence `linked_symbols` |

Preference for agent context overall remains hybrid coverage: human → living → rationale → AST
(`41-hybrid-documentation-coverage.md`). Module contract docstrings are **source text** agents
read when the file is opened; they complement (they do not replace) graph layers.

## Freshness And Definition Of Done

When a change alters any of role / SoT / wake path / fail-open-or-closed policy:

1. Update the module contract docstring in the **same** change.
2. If the contract is now trivial or false, **delete** the header rather than leave a lie.
3. Do not mark the task done while a hard module’s header contradicts the new behavior.

Agents **must** read an existing module contract docstring before “simplifying” durability,
retries, or crash handling in that file.

**Fix-on-read:** When an agent **Reads** a hard module and the file-top contract docstring is
missing or inaccurate, it **must** add or fix the header in the **same turn** (skill
`astloom-source-contracts` / always-on rule `mcp-first-astloom` clause 13) before continuing
other work. Skip still applies for non-hard modules.

**Ingest / retrieval:** On file ingest, Astloom indexes selective module contract docstrings onto the
FILE symbol (`ai_documentation`) and as a `MODULE_CONTRACT` rationale node linked via `DOCUMENTED_BY`,
so explore / generation-context / hybrid coverage can retrieve SoT and fail policy without a wide crawl.

## Verification

- [ ] Hard Module Test applied first; non-hard / unsure files have **no** new decorative header.
- [ ] Hard modules touched by the change have an accurate three-axis header (or an explicit skip reason that matches When To Skip).
- [ ] English only; no `ponytail:` markers; stopgaps use `tsoc-defer` only when user-approved.
- [ ] No duplicate architecture essay that should live only under `docs/`.
- [ ] Header length stays roughly 3–6 lines unless a fourth recovery line is required.

## Related Documents

| Document | Role |
| --- | --- |
| `50-package-folder-readme-standard.md` | Selective folder maps; rejects per-file README encyclopedias |
| `../agents/TEAM-HANDOUT-astloom-documentation-complete.md` | LIST D in-source practices; points here for module contracts |
| `../07-code-knowledge-graph/41-hybrid-documentation-coverage.md` | Hybrid layer preference order |
| `../07-code-knowledge-graph/03-ingestion-and-living-documentation-workflow.md` | Ingest of symbols and rationale |
| `29-engineering-best-practices-and-implementation-standards.md` | Broader implementation guardrails |
| `09-data-and-persistence-engineering.md` | Persistence / outbox ownership context |
| `.agents/skills/tsoc-source-comments/SKILL.md` | Comment law: English / `tsoc-defer` / no `ponytail:` |
