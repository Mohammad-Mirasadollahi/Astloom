---
doc_id: as.doc.master.documentation-structure-and-machine-ingest-standard-continued
title: 08 - Documentation Structure And Machine Ingest Standard (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/00-master-plan/08-documentation-structure-and-machine-ingest-standard.md`
  — remaining sections after the soft size budget.
tags:
- standard
- master
phase: 00-master-plan
canonical_path: docs/00-master-plan/08-documentation-structure-and-machine-ingest-standard-continued.md
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

# 08 - Documentation Structure And Machine Ingest Standard (Continued)

## Purpose

Continuation of `docs/00-master-plan/08-documentation-structure-and-machine-ingest-standard.md` — remaining sections after the soft size budget.

## 5. Body Structure For RAG And LLMIndex

### 5.1 Chunking contract

Default chunk strategy for Astloom docs:

1. Split on **H2** boundaries.
2. Keep H3+ with their parent H2 when under `chunk_hints.max_tokens`.
3. Prepend to each chunk a **machine preamble** built by the indexer (not necessarily written twice by the author):

```text
doc_id: …
title: …
section: <H2 text>
canonical_path: …
tags: …
```

Authors help the indexer by:

- Keeping each H2 section focused on **one** concern.
- Starting each H2 with a short definitional paragraph (2–4 sentences) before tables or lists.
- Preferring tables for structured facts (fields, states, APIs).
- Putting long code samples in fenced blocks immediately after the prose that explains them.
- Avoiding “continued below” without a heading break.

### 5.2 Self-contained sections

A retrieved chunk must remain understandable without the previous section. Therefore:

- Restate the entity name in the first sentence of an H2 when the heading alone is ambiguous.
- Do not rely on “as above” for normative rules; link or restate the rule id.
- Put prerequisites in a `## Dependencies` / `## Related Documents` section rather than implied narrative order only.

### 5.3 Summary and TL;DR patterns

- Frontmatter `summary` = document-level card.
- Optional `## Summary` H2 near the top for human skimming; keep it aligned with `summary`.
- Do not invent conflicting abstracts in the middle of the file.

### 5.4 Code and path citations

- Use fenced code blocks with a language tag (` ```python `, ` ```yaml `, ` ```text `).
- Cite repository paths in backticks: `` `backend/services/docs-sync-service/` ``.
- Prefer stable symbol paths over line numbers in prose.

### 5.5 Lists and tables

- Use tables for contracts, enums, state models, and field dictionaries.
- Use bullet lists for unordered requirements; numbered lists for algorithms and ordered procedures.
- Keep table cells short; move long prose to a following paragraph.

### 5.6 Token hygiene

- Prefer precise short sentences over filler.
- Deduplicate: one canonical section; elsewhere link.
- Avoid pasting large OpenAPI dumps; link to contract packages instead.
- Images need alt text that states the diagram’s claim in one sentence.

---

## 6. GraphRAG And Knowledge-Graph Authoring

### 6.1 Node types authors should imply

Through frontmatter and explicit sections, authors should make these nodes easy to extract:

| Node | Source |
| --- | --- |
| `Document` | `doc_id`, `title`, `canonical_path` |
| `Section` | H2 heading + anchor |
| `Entity` | `primary_entities`, glossary terms |
| `Service` / `Module` | ownership sections, path citations |
| `Symbol` | `linked_symbols` |
| `Decision` | `decision_refs` |
| `Requirement` | clause IDs / acceptance criteria bullets |
| `API` | contract tables |
| `RunbookStep` | numbered operational steps |

### 6.2 Edge types authors may declare

Use `relations_declared` and Related Documents sections. Preferred types (align with docs-as-code graph):

| Edge | Meaning |
| --- | --- |
| `explains` | Doc/section explains a symbol or API |
| `complements` | Sibling standard; both needed |
| `depends_on` | Must read target first |
| `implements` | Code/service implements this spec |
| `supersedes` | Replaces older doc |
| `owned_by` | Team ownership |
| `related_to` | Weak link when none of the above fit |

Do not invent undocumented edge types in frontmatter without updating docs-as-code contracts.

### 6.3 Related Documents section (mandatory for normative docs)

Every `standard`, `hld`, `lld`, `feature_spec`, and `service_design` **must** include:

```markdown

## Related Documents

- `doc_id` or relative path — one-line relationship.
- Summarize folder purpose.
- List each file with one-line description.
- State reading order when order matters.
- Link outward to sibling phases when required.
- Keep each major required section as its **own H2** (maps 1:1 to chunks).
- Put state machines and algorithms under clearly named H2s.
- Put acceptance criteria in a final H2 with verifiable bullets.
- Purpose / Scope
- Symptoms
- Diagnosis
- Remediation Steps (numbered)
- Rollback
- Verification
- Escalation
- Related Documents
- `01-….md` — …
- [ ] Path under the correct numbered folder; listed in folder `00-index.md`.
- [ ] Filename zero-padded + kebab-case.
- [ ] Modular: one concern per file; body within soft/hard size budgets (§1.4); no mega-doc growth.
- [ ] Exactly one H1; matches `title`.
- [ ] H2 sections are unique, specific, and chunk-sized (≤ ~12 H2s preferred).
- [ ] Frontmatter validates for intended ingest tier (Full for new normative docs).
- [ ] `summary` is accurate and non-marketing.
- [ ] Related Documents present; links resolve; no duplicated canonical tables.
- [ ] English only in committed body.
- [ ] No secrets, credentials, or customer data in examples.
- [ ] Complements `06-…` content requirements where applicable.
- [ ] Fallback: body remains readable if frontmatter were stripped.
- New normative docs use numbered paths, single H1, H2 chunk boundaries, and Full-tier frontmatter.
- Documentation grows as **modular sibling files** under size budgets (§1.4), not as unbounded mega-documents.
- Indexes list new files and state reading order where needed.
- Retrievers can filter and cite by `doc_id`, path, and section heading, and load only relevant modules.
- Graph builders can create at least Document, Section, and weak Related-Document edges without NLP.
- Documents with missing frontmatter remain searchable and human-readable via Fallback tiers.
- Authors have a single checklist (§10) that covers modularity, structure, metadata, RAG shape, and links.
- Standardization of the `docs/` tree follows `10-documentation-standardization-procedure.md` until `docs-standards` is machine-green (including soft-budget clearance).
- This document is linked from `00-index.md` and `docs/README.md` reading order beside `06-professional-documentation-standard.md`.
- `06-professional-documentation-standard.md` — professional content and tone requirements.
- `09-documentation-classification-and-lanes.md` — lifecycle, concern, audience, authority, visibility lanes.
- `10-documentation-standardization-procedure.md` — audit → remediate → split → link → accept.
- `../03-docs-as-code-sync/00-index.md` — docs knowledge graph, frontmatter validation, drift.
- `../06-technical-logic/03-docs-sync-technical-logic.md` — indexing and CI gate algorithms.
- `../08-software-engineering-architecture/22-product-design-and-engineering-specification-discipline.md` — specification discipline.
- `../14-api-design-and-naming-standards/00-index.md` — API naming parallel for contracts.
- `../../backend/docs/STRUCTURE_STANDARD.md` — backend folder structure (code, not docs prose).
- Parent document: `docs/00-master-plan/08-documentation-structure-and-machine-ingest-standard.md`
