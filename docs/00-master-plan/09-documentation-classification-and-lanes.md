---
doc_id: as.doc.master.documentation-classification-lanes
title: 09 - Documentation Classification And Lanes
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: 'Multi-axis classification for Astloom docs: lifecycle, concern, audience, authority,
  and visibility lanes so humans and retrieval stacks filter the right module.'
tags:
- documentation
- classification
- lanes
- audience
- rag
- authoring
phase: 00-master-plan
canonical_path: docs/00-master-plan/09-documentation-classification-and-lanes.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
authority: normative
visibility: internal
linked_symbols:
- backend/packages/astloom_cli/commands/docs_standards/check.py::check_markdown_doc
related_docs:
- as.doc.master.documentation-structure-machine-ingest
- as.doc.master.professional-documentation
doc_version: 1.0.1
audience:
- engineer
- architect
- agent
primary_entities:
- DocLane
- LifecycleLane
- ConcernLane
- AudienceLane
relations_declared:
- type: complements
  target: as.doc.master.documentation-structure-machine-ingest
- type: complements
  target: as.doc.master.professional-documentation
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 09 - Documentation Classification And Lanes

## Purpose

This document defines how Astloom documentation is **classified**. Structure, numbering, and ingest live in `08-documentation-structure-and-machine-ingest-standard.md`. Content quality lives in `06-professional-documentation-standard.md`. This file owns **lanes**: which design era a doc belongs to, what kind of problem it solves, who it is for, how binding it is, and who may see it.

Classification exists so:

- authors put work in the right modular file,
- other teams find interface docs without reading internal design,
- RAG / LLMIndex / GraphRAG can **filter before ranking**,
- speculative future design never pollutes “current truth” retrieval,
- problems and gaps stay visible without being mistaken for shipped behavior.

## Design Goals

| Goal | Requirement |
| --- | --- |
| Multi-axis, not one tag | Lifecycle, concern, audience, authority, and visibility are independent |
| Filter-first retrieval | Context packs apply lane filters before semantic search |
| Modular placement | Lane differences that would confuse readers become **separate files**, not mixed H2 dumps |
| Honest speculation | Future and problem lanes are explicit; never silently presented as current |
| Honest voice | Unimplemented design may live in git; prose must not read as shipped product readiness |
| Fallback | Missing lane fields degrade to Body-tier heuristics; body stays readable |

## Non-Goals

- Replacing tracker tools (Issues/Tasks) with Markdown problem dumps.
- A deep folder tree per lane (lanes are metadata + light path hints, not infinite directories).
- Perfect taxonomy for every possible note; prefer the smallest enum that still filters well.

---

## 1. Classification Axes (overview)

Every Full-tier normative doc **must** declare these frontmatter fields (in addition to fields in `08-…`):

| Axis | Frontmatter key | Cardinality | Purpose |
| --- | --- | --- | --- |
| Lifecycle | `lifecycle_lane` | one | Design era / truthfulness over time |
| Concern | `concern_lane` | one | Why the doc exists |
| Audience | `audience_lane` | one or more | Who should load it by default |
| Authority | `authority` | one | How binding the text is |
| Visibility | `visibility` | one | Intended sharing boundary |

`doc_type` (from `08-…`) remains the **document shape** (hld, runbook, …). Lanes are **routing and trust**, not a second `doc_type`.

---

## 2. Lifecycle Lane (`lifecycle_lane`)

Answers: *Is this initial intent, current truth, or future intent?*

| Value | Meaning | Retrieval default |
| --- | --- | --- |
| `initial` | Early / foundational design that established direction; may be partially historical | Include when asking “why was it designed this way?”; demote for “how does it work now?” |
| `current` | Normative description of behavior authors treat as **true for implementation/ops now** (prefer as-built; as-designed only when binding and not aspirational) | **Default include** for implementation and ops questions |
| `future` | Planned, proposed, or roadmap design **not yet** binding for implementation | **Exclude by default** from implementation context packs unless the query is about roadmap/future |
| `transition` | Migration, dual-run, or deprecation bridge between current and future | Include for upgrade/migration queries; pair with `current` |
| `historical` | Superseded record kept for audit; not for new work | Exclude by default; include only for archaeology / incident history |

### Rules

- A file has **one** `lifecycle_lane`. If a topic needs both current and future, **split into two files** and link them (`depends_on` / `complements`).
- Do not bury a large `## Future ideas` inside a `current` doc. Move to a `future` sibling.
- When future work ships, either: (a) move content into the `current` doc and set the old file to `historical` + `superseded_by`, or (b) flip `lifecycle_lane` to `current` only if the whole file became truth.
- `initial` is for founding specs that remain useful as intent; if they still govern implementation, prefer `current` and mention origin in Purpose.
- **Publishing unimplemented design is fine.** Putting HLD/LLD/proposals on the repository before code exists is normal. The failure mode is presenting that design as **shipped / product-ready** (see `06-professional-documentation-standard.md` Designed Vs Shipped Honesty).
- Body voice **must** match the lane: `future` (and unfinished slices of `transition`) use design intent language; only `current` as-built behavior uses unqualified present-tense product claims.
- Every `future` design file **must** state Implementation status near the top (not started / partial / blocked) so humans and agents cannot treat it as live product truth.
- Never claim “ready”, “production”, or “customers can …” for capabilities that lack verified code paths or release gates.

### Examples

| Doc intent | `lifecycle_lane` |
| --- | --- |
| Phase-0 product boundary decision still in force | `current` |
| First sketch of memory tiers kept for rationale | `initial` |
| Proposed GraphRAG ranking v2 not approved | `future` |
| Dual-write memory migration plan | `transition` |
| Old broker payload format after cutover | `historical` |
| Full LLD for a feature with no code yet (honest design) | `future` |
| Same LLD written as if operators already run it in prod | **invalid** — fix voice + lane |

---

## 3. Concern Lane (`concern_lane`)

Answers: *What job does this document do?*

| Value | Meaning | Typical `doc_type` pairing |
| --- | --- | --- |
| `standard` | Normative rules authors/implementers must follow | `standard` |
| `design` | Architecture / behavior design (HLD, LLD, feature) | `hld`, `lld`, `feature_spec`, `service_design` |
| `decision` | Chosen option and rejected alternatives (ADR-style) | `adr` |
| `problem` | Known defect, pain, risk, or failure mode under discussion | `gap` or focused design note |
| `gap` | Missing capability, open question, unresolved assumption | `gap` |
| `contract` | API, event, schema, or SDK contract narrative | `contract` |
| `ops` | Runbook, deployment, incident, operability | `runbook` |
| `example` | Worked scenario, checklist, logical implementation sample | `example` |
| `cross_team` | Interface / handshake doc primarily for **another team** | often `contract`, `hld`, or `readme` |
| `onboarding` | How a human or agent starts productive work in an area | `readme`, `index`, guided standard |
| `security` | Threat, trust boundary, abuse case, control mapping | design / standard / runbook with security focus |
| `product` | Workflow, IA, interaction states, acceptance for product roles | feature / experience specs |

### Rules

- One primary `concern_lane` per file. Secondary themes belong in `tags`, not a second primary concern.
- **Problems are first-class:** use `problem` or `gap`, never hide them only inside a happy-path design doc.
- **Cross-team docs** use `cross_team` when the main reader is outside the owning team (even if engineers wrote it).
- Do not mark a speculative brainstorm as `standard` or `contract`.

### Problem vs gap

| Lane | Use when |
| --- | --- |
| `problem` | Something is wrong, painful, risky, or failing (known issue shape) |
| `gap` | Something is missing or undecided (unknown / unfinished shape) |

Both stay modular under `docs/10-gap-analysis/` or a phase-local `NN-…-problems.md` / `NN-…-gaps.md` when volume grows.

---

## 4. Audience Lane (`audience_lane`)

Answers: *Who should this be retrieved for by default?*

Multi-valued list. Use the smallest set that is true.

| Value | Who |
| --- | --- |
| `platform-engineering` | Astloom platform / control-plane engineers |
| `service-owners` | Owners of a specific backend/frontend service |
| `partner-teams` | Other internal teams integrating with Astloom |
| `operators` | Deploy, SRE, on-call, install |
| `security` | Security reviewers / appsec |
| `product` | Product designers / PMs for workflow and acceptance |
| `agents` | Coding / ops agents using docs as context |
| `sdk-consumers` | Developers building against published SDKs/APIs |
| `exec-lite` | Short brief only (rare; keep files tiny) |

### Rules

- Always include `agents` when the doc is intended as implementation context for AI agents (most normative `current` design/standard docs).
- Partner-facing material **must** include `partner-teams` and usually `visibility: cross-team`.
- Do not list every audience “just in case”; over-tagging defeats filters.
- The older recommended field `audience` in `08-…` (engineer / architect / …) may remain as a coarse hint; **`audience_lane` is normative for filtering**. Prefer setting both consistently during edits.

### “For another team” pattern

When writing for a partner or sibling team:

1. `concern_lane: cross_team` (or `contract` if it is purely an interface contract).
2. `audience_lane` includes `partner-teams` (and `sdk-consumers` if applicable).
3. `visibility: cross-team`.
4. Body focuses on **stable interface, ownership, SLAs, error contracts, and contact path** — not internal algorithms.
5. Link inward to internal `design` docs for the owning team; do not duplicate internals.

---

## 5. Authority (`authority`)

Answers: *Must implementers obey this?*

| Value | Meaning |
| --- | --- |
| `normative` | Requirements (`must` / `should` as defined in prose); CI or review may enforce |
| `informative` | Explanation, rationale, background; does not alone change implementation duty |
| `speculative` | Ideas, options, spikes; not approved |
| `example-only` | Illustrative scenario; adapt before copying |

### Rules

- `lifecycle_lane: future` is usually `speculative` or `informative` until approved; after approval and before ship it may be `normative` **only** for planning work, still filtered as future for runtime implementation packs.
- `concern_lane: standard` and `contract` with `lifecycle_lane: current` **must** be `normative` or explicitly `informative` with a pointer to the normative sibling.
- Problem/gap docs are typically `informative` (they describe reality) unless they state a binding interim constraint.

---

## 6. Visibility (`visibility`)

Answers: *Who is the doc meant to be shared with?*

| Value | Meaning |
| --- | --- |
| `internal` | Owning product/engineering org only |
| `cross-team` | Other internal teams may rely on it as an interface |
| `operator` | Operators/installers; may ship with private deploy packs |
| `restricted` | Security-sensitive; tighter distribution; still **no cloud exfiltration** of repo content |

### Rules

- Classification does **not** authorize uploading docs to public or third-party clouds. Sovereignty rules in project law still apply.
- `cross-team` docs must avoid secrets, customer data, and environment-specific credentials.
- Prefer a dedicated cross-team module over marking a deep internal LLD as `cross-team`.

---

## 7. How Lanes Combine (decision guide)

Authors pick lanes in this order:

1. **lifecycle_lane** — initial / current / future / transition / historical  
2. **concern_lane** — standard / design / decision / problem / gap / …  
3. **audience_lane** — who loads it  
4. **authority** — normative vs not  
5. **visibility** — sharing boundary  

### Quick matrix (common cases)

| Situation | lifecycle | concern | audience (min) | authority | visibility |
| --- | --- | --- | --- | --- | --- |
| Foundational HLD still true | `current` | `design` | platform-engineering, agents | normative | internal |
| Early rationale kept | `initial` | `design` | platform-engineering | informative | internal |
| Roadmap design spike | `future` | `design` | platform-engineering | speculative | internal |
| Known scaling pain | `current` | `problem` | platform-engineering, operators | informative | internal |
| Open product decision | `current` | `gap` | product, platform-engineering | informative | internal |
| Partner integration guide | `current` | `cross_team` | partner-teams, sdk-consumers, agents | normative | cross-team |
| On-call runbook | `current` | `ops` | operators, agents | normative | operator |
| ADR | `current` | `decision` | platform-engineering, agents | normative | internal |
| Migration dual-run | `transition` | `ops` or `design` | operators, service-owners | normative | internal |

---

## 8. Placement Hints (modular, not deep trees)

Lanes are primarily **metadata**. Path hints (optional) when a folder grows:

| Lane signal | Placement hint |
| --- | --- |
| Most product design | Existing phase folders under `docs/NN-…/` |
| Gaps / open decisions | `docs/10-gap-analysis/` |
| Problems that outgrow a phase note | phase file `NN-…-problems.md` or gap folder |
| Future proposals | same phase folder with clear filename + `lifecycle_lane: future`, or `docs/10-gap-analysis/` if undecided |
| Cross-team interfaces | phase or `docs/14-api-…` / SDK docs; filename should say `…-partner-…` or `…-integration-…` when helpful |
| Ops | `docs/09-platform-governance-operations/` or service `runbooks/` |

Do **not** create `docs/future/`, `docs/problems/`, `docs/other-teams/` as parallel universes unless volume later justifies a dedicated standards folder with its own `00-index.md`.

---

## 9. Frontmatter Example

```yaml
---
doc_id: as.doc.memory.partner-context-pack-contract
title: "04 - Partner Context Pack Contract"
doc_type: contract
status: active
schema_version: "1.0"
owner: memory-service
summary: >-
  Stable context-pack fields partner teams may rely on when calling memory retrieval.
tags: [memory, contract, partner]
phase: "02-memory-and-context"
canonical_path: docs/02-memory-and-context/04-partner-context-pack-contract.md
lifecycle_lane: current
concern_lane: cross_team
audience_lane:
  - partner-teams
  - sdk-consumers
  - agents
authority: normative
visibility: cross-team
related_docs:
  - as.doc.memory.dynamic-context-rag
language: en
security_classification: internal
---
```

---

## 10. Retrieval And RAG Rules (implementers)

| Query class | Default filters |
| --- | --- |
| Implement feature / fix bug | `lifecycle_lane in (current, transition)` + `authority in (normative, informative)` + exclude pure `speculative` |
| Roadmap / design future | include `lifecycle_lane: future` |
| Why was this chosen | include `initial`, `decision`, and `current` |
| Incident / ops | `concern_lane: ops` + `audience_lane` contains `operators` |
| Partner integration | `visibility: cross-team` or `concern_lane: cross_team` |
| Known pains | `concern_lane in (problem, gap)` |

Additional rules:

- Prefer **lane filter → hybrid search → rerank** over unconstrained semantic search across all Markdown.
- Never treat `future` + `speculative` chunks as evidence of shipped behavior in judge/eval prompts.
- Never treat present-tense design prose as shipped evidence when `lifecycle_lane` is `future` or Implementation status says not implemented.
- GraphRAG edges should label lifecycle on Document nodes so traversals can avoid jumping from current code symbols into future-only docs without an explicit edge type such as `planned_for`.
- Fallback when lanes are missing: infer `lifecycle_lane: current` only if `status: active` and path is not under gap-analysis; otherwise leave unset and demote confidence.

---

## 11. Authoring Workflow

1. Decide if this is a **new modular file** (`08-…` §1.4) rather than a section dump.
2. Set the five lane fields before writing long prose. Use **only** the closed concern set in §3; normalize forbidden aliases using `10-documentation-standardization-procedure.md` §4.
3. If lanes conflict inside one draft (e.g. current design + future brainstorm), split files first.
4. For partner/other-team docs, write the external contract module first; link internal design second.
5. For problems/gaps, file under the gap process when they need tracking; keep the Markdown as the durable explanation.
6. When bringing a file or tree to Full-tier compliance, follow **`10-documentation-standardization-procedure.md`** end-to-end (machine audit → remediate → soft-budget split → evidence `linked_symbols` → re-audit).
7. Pass the checklist in §12 and the standardization acceptance checklist in `10-…` §10.

---

## 12. Review Checklist

- [ ] `lifecycle_lane`, `concern_lane`, `audience_lane`, `authority`, `visibility` set and consistent with body.
- [ ] Future material not mixed into a `current` normative file.
- [ ] Unimplemented design is allowed in-repo, but body voice does not read as shipped / product-ready.
- [ ] `future` (and partial) docs include Implementation status near the top.
- [ ] Problems/gaps use `problem` / `gap` (or live under gap-analysis) rather than only a footnote in a happy-path design.
- [ ] Cross-team docs avoid internal-only algorithms and secrets.
- [ ] `authority` matches how strongly the prose uses must/should.
- [ ] Folder index lists the file; Related Documents link lifecycle siblings when split.
- [ ] Retrieval filters would not misread this file as shipped truth if it is future/speculative.

---

## 13. Acceptance Criteria

This classification standard is satisfied when:

- New normative docs declare all five lane axes in frontmatter.
- Initial vs future vs current design are separable by filter without reading the full body.
- Problem and gap knowledge has an explicit concern lane and modular home.
- Other-team / partner docs are marked `cross_team` / `cross-team` and stay interface-focused.
- RAG/context packs can exclude speculative future content from implementation answers by default.
- Design-ahead-of-code docs remain honest in prose (no false product-ready voice), not only in metadata.
- Missing lane metadata does not make the Markdown unreadable; ingest falls back per `08-…`.

## Related Documents

- `08-documentation-structure-and-machine-ingest-standard.md` — structure, modularity, frontmatter base, RAG chunking, fallbacks.
- `10-documentation-standardization-procedure.md` — mandatory audit/remediate/split/link acceptance method for Full-tier `docs/`.
- `06-professional-documentation-standard.md` — professional content sections and tone.
- `../10-gap-analysis/00-index.md` — gap triage home for unresolved assumptions and open decisions.
- `../03-docs-as-code-sync/00-index.md` — docs graph and validation pipelines.
