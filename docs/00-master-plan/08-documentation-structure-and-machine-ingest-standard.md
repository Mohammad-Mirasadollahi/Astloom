---
doc_id: as.doc.master.documentation-structure-machine-ingest
title: 08 - Documentation Structure And Machine Ingest Standard
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: 'Normative authoring rules for Astloom documentation: modular small files, tree
  layout, numbering, titles, YAML frontmatter, RAG/LLMIndex chunking, GraphRAG links, and
  fallback ingest.'
tags:
- documentation
- rag
- llmindex
- graphrag
- authoring
- frontmatter
phase: 00-master-plan
canonical_path: docs/00-master-plan/08-documentation-structure-and-machine-ingest-standard.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
doc_version: 1.0.1
updated_at: 2026-08-10
linked_symbols:
- backend/packages/astloom_cli/commands/docs_standards/check.py::check_markdown_doc
- backend/packages/astloom_cli/commands/docs_standards/remediate.py::remediate_markdown_doc
- backend/packages/astloom_cli/markdown_frontmatter.py::parse_markdown_frontmatter
placeholder: 1
---

# 08 - Documentation Structure And Machine Ingest Standard

## 08 - Documentation Structure And Machine Ingest Standard
## Purpose

This document is the normative **authoring and structure** standard for Astloom documentation. It defines how humans and agents must name files, number folders, write titles and headings, attach metadata, cross-link entities, and shape prose so documentation is:

1. **Modular** — many focused files beat one mega-document; size stays bounded so humans and agents load only what they need.
2. **Discoverable** — indexes, stable IDs, and predictable paths find the right doc fast.
3. **Chunkable** — RAG, LLMIndex, and similar embedders split text at safe boundaries without losing meaning.
4. **Graph-linkable** — GraphRAG and the docs knowledge graph can attach nodes and edges without guessing.
5. **Fallback-safe** — missing or invalid machine metadata never makes a document unreadable to humans or to a plain Markdown reader.

This standard complements, and does not replace:

| Document | Owns |
| --- | --- |
| `06-professional-documentation-standard.md` | Audience, tone, required *content* sections, acceptance quality |
| `09-documentation-classification-and-lanes.md` | Lifecycle / concern / audience / authority / visibility **lanes** |
| `../03-docs-as-code-sync/` and `../06-technical-logic/03-docs-sync-technical-logic.md` | Indexing pipelines, AST anchors, drift detection, CI gates |
| `../08-software-engineering-architecture/22-product-design-and-engineering-specification-discipline.md` | Dual-track product + engineering specification discipline |

Authors **must** follow this document when creating or materially revising any Markdown under `docs/`, service `docs/`, runbooks, and ADRs that participate in product knowledge.

## Design Goals

| Goal | Requirement |
| --- | --- |
| Modular by default | One concern per file; prefer a new numbered sibling over growing an existing file past size budgets |
| One tree, one grammar | Phase folders, zero-padded file numbers, and H1/H2 shapes stay consistent across the tree |
| Machine-first metadata, human-first body | YAML frontmatter routes; Markdown body explains |
| Stable identity over path | `doc_id` and heading anchors survive renames better than raw paths alone |
| Optimal retrieval | Chunks are self-describing; sections answer one question; retrieval pulls few small files, not a wall of prose |
| Graceful degradation | Tiered ingest: full metadata → partial → body-only heuristics → raw Markdown |

## Non-Goals

- Replacing product feature specs with a second parallel doc set.
- Requiring every historical file to be rewritten in one pass (migrate opportunistically; new docs must comply).
- Mandating a specific commercial RAG vendor.
- Putting Persian (or any non-English) into committed documentation bodies.
- Writing “complete encyclopedia” single files that mix HLD, LLD, runbook, API catalog, and examples in one body.

---

## 1. Tree Layout And Numbering

### 1.1 Top-level phase folders

Product documentation lives under `docs/` in **zero-padded, numbered phase folders**:

```text
docs/
  NN-kebab-topic/
    00-index.md
    NN-kebab-topic.md
```

Rules:

- Folder prefix `NN` is two digits (`00` … `99`), then a kebab-case topic slug.
- Each phase folder **must** contain `00-index.md` as the local entry point.
- Phase numbers are assigned in the master reading order; do not reuse a retired number for a different topic.
- New cross-cutting standards may use a new top-level `NN-…` folder (example: `14-api-design-and-naming-standards/`) instead of stuffing unrelated files into an existing phase.

### 1.2 File numbering inside a folder

| Pattern | Meaning |
| --- | --- |
| `00-index.md` | Folder map, purpose, file list, reading order |
| `01-…`, `02-…`, … | Ordered content files |
| Suffix `-HLD.md`, `-LLD.md`, `-service-design.md` | Allowed type markers after the number and slug |

Rules:

- Use **two-digit** prefixes (`01`, `02`, …). Prefer contiguous numbers; gaps are allowed only when a reserved slot is documented in the folder index.
- Filename slug is **kebab-case ASCII**, max ~80 characters, no spaces.
- Do not encode version in the filename (`-v2`); use frontmatter `schema_version` / `doc_version` and `supersedes`.
- One primary topic per file. Split oversized documents; do not bury a second topic under a misleading title. See §1.4.

### 1.3 Canonical path identity

For citations and indexes, the **canonical path** is repo-relative from the repository root, forward slashes only:

```text
docs/00-master-plan/08-documentation-structure-and-machine-ingest-standard.md
```

Indexes (`docs/README.md`, folder `00-index.md`) **must** list every normative file in that folder.

### 1.4 Modular files And Size Budgets (normative)

**Principle:** documentation volume is controlled by **splitting into modules**, not by stuffing more sections into one file. A thin `00-index.md` plus several focused siblings is the default shape for every phase folder.

| Rule | Requirement |
| --- | --- |
| One concern per file | Feature spec, HLD, LLD, contracts, risks, runbook, and examples are **separate files** when the topic is non-trivial (mirror `03-docs-as-code-sync/` and `14-api-design-and-naming-standards/`) |
| Soft size budget | Target **≤ ~400 lines** of body Markdown per content file (excluding frontmatter). Crossing ~400 is a signal to split |
| Hard size budget | New or materially revised normative files **must not** exceed **~800 lines** of body without an explicit split plan in the folder index |
| Section budget | Prefer **≤ ~12 H2 sections** per file; more H2s usually means a second file |
| No duplication | Shared facts live in one canonical file; others link with one-line context |
| Index stays thin | `00-index.md` maps and orders; it must not become a second full design doc |
| Split, do not append | When adding a large new capability, create `NN-new-topic.md` (or a subfolder with its own `00-index.md`) instead of growing an unrelated sibling |

**When to split immediately**

- Two audiences need different depth (operator runbook vs engineer LLD).
- Two lifecycles diverge (stable contract vs evolving examples).
- A single H2 subsection is becoming a mini-document (> ~80–100 lines).
- RAG/context packs would pull mostly irrelevant neighbors from the same file.

**How to split**

1. Keep a stable `doc_id` on the canonical file that still owns the core topic; give each new file its own `doc_id`.
2. Move whole H2 sections (not half-paragraphs) into the new file.
3. Leave a short stub H2 or Related Documents entry pointing to the new path/`doc_id`.
4. Update the folder `00-index.md` and any reading-order lists.
5. Declare `relations_declared` / `related_docs` between the siblings (`complements` or `depends_on`).

**Anti-patterns**

- One “phase bible” Markdown that mixes every design depth.
- Copy-pasting the same API table into five files.
- Deep folder trees of one-line stubs with no real ownership (prefer a sibling file in the same phase).
- Inflating `summary` or Purpose with content that belongs in a dedicated sibling.

Modularity improves retrieval: agents and RAG load **only the relevant module**, keep citation precision high, and avoid token waste from mega-files.

---

## 2. Titles And Heading Grammar

### 2.1 Document title (H1)

- Exactly **one** H1 per file.
- H1 form: `# NN - Title In Title Case` when the file is numbered, or `# Title In Title Case` for unnumbered service READMEs.
- H1 **must** match frontmatter `title` when frontmatter is present (same words; punctuation may differ only by trailing period).
- Do not put the full folder path in the H1.

### 2.2 Section headings (H2+)

| Level | Use |
| --- | --- |
| H2 (`##`) | Primary sections; preferred **chunk boundaries** for RAG |
| H3 (`###`) | Subsections inside one chunkable topic |
| H4+ | Rare; prefer lists/tables over deep nesting |

Rules:

- Heading text is **sentence-style Title Case or short noun phrases** — stable, searchable, unique within the file.
- Prefer headings that stand alone as retrieval queries, e.g. `## Drift Detection Algorithm`, not `## Details`.
- Do not number headings manually (`## 3.2 Foo`) unless the number is part of a stable public clause ID (see §3.3). Prefer unnumbered headings; file numbering carries order.
- Do not skip levels (H2 → H4).
- Avoid emoji, marketing adjectives, and vague headings (`Overview`, `Notes`, `Misc`) unless followed by a specific qualifier (`## Overview Of Ingest Tiers`).

### 2.3 Heading anchors

Authors should assume GitHub-style / CommonMark slug anchors:

- Lowercase, spaces → `-`, strip most punctuation.
- Prefer heading text that yields a short, unique slug.
- When linking to a section, use relative links with explicit fragments:

```markdown
See [Fallback Tiers](./08-documentation-structure-and-machine-ingest-standard.md#7-fallback-tiers-and-graceful-degradation).
```

If two headings would collide, disambiguate the heading text rather than relying on auto-suffixes.

### 2.4 Opening paragraph after H1

Immediately after the H1 (and optional frontmatter), place a **Purpose** (or equivalent) H2 whose first paragraph states:

- what the document owns,
- who uses it,
- what it does **not** own (pointer to sibling docs).

This paragraph is the preferred **document-level summary** for indexes and LLMIndex document nodes.

---

## 3. Stable Identifiers

### 3.1 `doc_id`

Format (normative):

```text
as.doc.<domain>.<slug>
```

Examples:

```text
as.doc.master.documentation-structure-machine-ingest
as.doc.memory.dynamic-context-rag
as.doc.docs_sync.feature-specification
```

Rules:

- `doc_id` is **immutable** after first publish. Renaming a file does not change `doc_id`.
- Use lowercase ASCII, digits, dots, and hyphens only.
- Domain segment mirrors the phase or bounded context (`master`, `memory`, `docs_sync`, `api`, `ops`, …).
- Never reuse a retired `doc_id`; mark `status: archived` and point successors with `supersedes` / `superseded_by`.

### 3.2 Entity references in body

When referring to system entities, prefer stable tokens that indexers can extract:

| Entity | Pattern in prose / lists |
| --- | --- |
| Document | `doc_id` or relative Markdown link |
| Code symbol | `linked_symbols` entry / `` `path::Symbol` `` |
| Decision | `DEC-YYYY-NNN` or ADR path |
| Issue / Task | tracker id as used by the platform |
| API route | `` `METHOD /api/v1/...` `` |
| Config key | `` `ENV_OR_KEY_NAME` `` |
| Service | kebab service name as in architecture docs |

### 3.3 Optional clause IDs

For normative requirements that must be cited in tests or ADRs, authors **may** tag a short clause after a heading or bullet:

```markdown
## Frontmatter Required Fields

- **[DOC-INGEST-REQ-001]** Every new normative doc under `docs/` must include valid frontmatter at ingest tier Full.
```

Clause IDs are uppercase, hyphen-separated, stable, and listed once. Do not renumber casually.

---

## 4. YAML Frontmatter Schema

### 4.1 Placement

Frontmatter is a YAML block at the **very start** of the file, enclosed by `---` lines. The H1 follows the closing `---`.

Documents without frontmatter remain **human-readable** (Fallback Tier Body / Raw). They **must not** be treated as synchronized technical documentation by docs-sync (see technical logic).

### 4.2 Required fields (ingest tier Full)

```yaml
---
doc_id: as.doc.master.documentation-structure-machine-ingest
title: "08 - Documentation Structure And Machine Ingest Standard"
doc_type: standard
status: active
schema_version: "1.0"
owner: platform-docs
summary: >-
  Normative authoring rules for tree layout, numbering, titles, frontmatter,
  RAG chunking, GraphRAG links, and fallback ingest.
tags:
  - documentation
  - rag
  - graphrag
  - authoring
phase: "00-master-plan"
canonical_path: docs/00-master-plan/08-documentation-structure-and-machine-ingest-standard.md
---
```

| Field | Type | Rules |
| --- | --- | --- |
| `doc_id` | string | See §3.1 |
| `title` | string | Matches H1 |
| `doc_type` | enum | See §4.4 |
| `status` | enum | `draft` \| `active` \| `deprecated` \| `archived` |
| `schema_version` | string | Semver of **this frontmatter schema**, not product version |
| `owner` | string | Team or role slug |
| `summary` | string | 1–3 sentences; used as embedding preamble / card text |
| `tags` | string[] | Lowercase kebab; 3–12 items |
| `phase` | string | Folder name or `service:<name>` / `adr` / `runbook` |
| `canonical_path` | string | Repo-relative path |

### 4.3 Recommended fields (enrich GraphRAG / filters)

```yaml
linked_symbols: []          # code symbols this doc explains
decision_refs: []           # DEC-… / ADR paths
related_docs:               # doc_id list
  - as.doc.master.professional-documentation
related_issues: []
supersedes: null            # prior doc_id
superseded_by: null
reviewed_by: null
reviewed_at: null           # ISO-8601 date (periodic human/agent review)
doc_version: "1.0.0"        # document revision (semver); bump on material edit
updated_at: "2026-07-24"    # UTC YYYY-MM-DD of last material edit (required on write/edit)
audience:
  - engineer
  - architect
  - agent
## Classification lanes (normative detail in 09-documentation-classification-and-lanes.md)
lifecycle_lane: current     # initial | current | future | transition | historical
concern_lane: standard      # standard | design | decision | problem | gap | …
audience_lane:              # filter audiences; see 09-…
  - platform-engineering
  - agents
authority: normative        # normative | informative | speculative | example-only
visibility: internal        # internal | cross-team | operator | restricted
primary_entities:           # ubiquitous language nouns for graph nodes
  - DocumentationStructure
  - IngestTier
  - DocChunk
relations_declared:         # author-declared edges (hint for GraphRAG)
  - type: complements
    target: as.doc.master.professional-documentation
  - type: implemented_by
    target: docs-sync-service
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
```

**Revision policy (agents):** On material create/edit, keep the body truthful, bump
`doc_version` (`MAJOR.MINOR.PATCH`), and set `updated_at` to the UTC calendar date.
Never stamp version/date without content alignment. Prefer docs-sync drift /
`linked_symbols` / catalog to decide which docs a code change must update — do not
treat dates alone as the drift signal. Machine gate: missing `doc_version` /
`updated_at` → `docs-standards` **warnings**; invalid formats → **issues**.
language: en
security_classification: internal
```

**Lane fields** (`lifecycle_lane`, `concern_lane`, `audience_lane`, `authority`, `visibility`) are required for new normative Full-tier docs. Enumerations, combinations, and RAG filter rules are defined in `09-documentation-classification-and-lanes.md` — do not fork a second taxonomy here.

### 4.4 `doc_type` values

| Value | Use |
| --- | --- |
| `index` | Folder `00-index.md` |
| `standard` | Normative rules |
| `hld` | High-level design |
| `lld` | Low-level design |
| `feature_spec` | Feature specification |
| `service_design` | Full service design |
| `runbook` | Operational procedure |
| `adr` | Architecture decision |
| `contract` | API / event / schema contract narrative |
| `example` | Logical implementation example |
| `gap` | Gap analysis |
| `glossary` | Glossary / ubiquitous language |
| `readme` | Local README |

### 4.5 Validation failures (machine)

Invalid or incomplete frontmatter ⇒ emit validation findings via `astloom docs-standards` / `check_markdown_doc`. Full-tier sync and standardization **must not** treat the file as conforming until issues are cleared.

**Normative remediation method:** follow `10-documentation-standardization-procedure.md` (audit → remediate → size split → evidence `linked_symbols` → re-audit → optional `astloom sync` Phase 2). Do not invent a parallel checklist.

Automatic remediator helpers may rewrite metadata/structure; they **must not** invent code-graph edges or delete body prose. Soft-budget warnings **must** be cleared during a standardization pass (split siblings); hard budget overruns are blocking.

---

## Related Documents

- Continued in `docs/00-master-plan/08-documentation-structure-and-machine-ingest-standard-continued.md`
- Standardization procedure: `docs/00-master-plan/10-documentation-standardization-procedure.md`
