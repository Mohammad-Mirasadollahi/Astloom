---
doc_id: as.doc.rules.llm-judge-operating
title: 11 - LLM Judge Operating Standard
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-architecture
summary: Normative operating standard for deterministic LLM-as-a-Judge evaluation — eligible
  policies, temperature 0 with JSON object mode, low-confidence escalation, and reproducibility
  fields (closes GAP-T05).
tags:
- rules
- llm
- litellm
- judge
- gap-t05
- standard
phase: 04-rule-engine-orchestration
canonical_path: docs/04-rule-engine-orchestration/11-llm-judge-operating-standard.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
- product
authority: normative
visibility: internal
linked_symbols:
- backend/services/rule-engine-service/src/rule_engine_service/domain/judge.py::Judge
- backend/services/rule-engine-service/src/rule_engine_service/litellm_judge.py::LiteLLMJudge
- backend/configs/schemas/llm-judge-verdict.schema.json
related_docs:
- docs/04-rule-engine-orchestration/03-low-level-design.md
- docs/04-rule-engine-orchestration/06-detailed-section-design.md
- docs/06-technical-logic/04-rules-orchestration-technical-logic.md
- docs/13-technology-stack-and-platform-decisions/10-model-routing-profiles-with-litellm.md
- docs/10-gap-analysis/03-technical-implementation-gaps.md
doc_version: 1.0.1
audience:
- engineer
- architect
- product
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 11 - LLM Judge Operating Standard

## Purpose

Close **GAP-T05** by defining how Astloom runs LLM-as-a-Judge so verdicts are structured, fail-closed on ambiguity, and reproducible from stored metadata.

## Judge flow

```mermaid
flowchart TD
  subject[Subject + Rule] --> eligible{Eligible for LLM Judge?}
  eligible -->|no| det[Deterministic / manual path only]
  eligible -->|yes| call[LiteLLMJudge temperature 0 + json_object]
  call --> parse{Schema-valid JSON?}
  parse -->|no| escalateMalformed[Escalate fail-closed]
  parse -->|yes| conf{Confidence below threshold?}
  conf -->|yes| escalateLow[Escalate low-confidence]
  conf -->|no| verdict[Emit structured verdict]
  escalateMalformed --> attach[Attach replay metadata]
  escalateLow --> attach
  verdict --> attach
  attach --> store[Persist evaluation + judge_replay]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Rule engine | Selects active rule and subject evidence | Evaluation context ready |
| 2 | Policy gate | Checks eligibility (semantic / hybrid-after-deterministic) | Call LLM Judge or skip |
| 3 | LiteLLMJudge | Completes with `temperature=0`, `response_format=json_object`, route `rules.judge` | Raw JSON content |
| 4 | Validator | Validates against `llm-judge-verdict.schema.json` | Accepted object or malformed escalate |
| 5 | Confidence gate | Compares confidence to threshold (default `0.7`) for medium+ risk | May force `escalate` |
| 6 | Store | Persists verdict plus reproducibility fields | Replayable evaluation record |

## Eligible policies

LLM Judge is **not** the default path for every rule.

| Evaluation mode | LLM Judge |
| --- | --- |
| `deterministic` | Never |
| `manual` | Never (always escalate to human) |
| `hybrid` | Only when deterministic pre-check returns `allow` and semantic ambiguity signals apply |
| `semantic` | Always (after cheaper pre-checks if the service layer runs them) |

Additional eligibility constraints:

- Reserved for ambiguous semantic cases; deterministic secret / sensitive-domain blockers stay first.
- Domain packs and feature profiles may mark policies `llm_judge_eligible=false` to force deterministic-only.
- Bootstrap default remains `HeuristicJudge` (no network). Production LLM path requires `ASTLOOM_RULE_JUDGE=litellm`.

## Generation constraints

Every production LLM Judge call MUST use:

| Parameter | Required value | Reason |
| --- | --- | --- |
| `temperature` | `0` | Maximize reproducibility |
| `response_format` | `{ "type": "json_object" }` | Structured verdict only |
| Route task class | `rules.judge` | ModelRoutingProfile + env overrides |
| Reasoning extras | Disabled unless an ADR explicitly allows | Avoid non-deterministic chain-of-thought |

The judge MUST NOT invent evidence references that were not supplied in the constrained prompt.

## Structured verdict schema

Canonical schema: `backend/configs/schemas/llm-judge-verdict.schema.json`.

Required fields:

- `verdict`: `allow` \| `warn` \| `block` \| `escalate`
- `confidence`: number in `[0, 1]`
- `rationale`: non-empty string
- `matched_examples`: string array
- `missing_evidence`: string array
- `recommended_action`: string

Malformed JSON, schema violations, or gateway failures → **escalate** (fail-closed). Do not coerce to `allow`.

## Low-confidence escalation

Default confidence threshold: **`0.7`**.

Rules:

1. If `confidence < threshold` and rule severity is `medium`, `high`, or `critical` → force `verdict=escalate`.
2. If `confidence < threshold` and severity is `low` → prefer `warn` or `escalate` (never silent `allow` when evidence is thin).
3. Service-layer hybrid/semantic paths may apply an additional high/critical escalate fallback; the adapter still enforces the gate first.

Escalation is correct behavior at a risk boundary, not an infrastructure failure.

## Reproducibility fields

Every LLM Judge result MUST attach (and the evaluation record SHOULD persist) the following replay metadata:

| Field | Source |
| --- | --- |
| `model_id` | Gateway completion model actually used |
| `route_profile_id` | ModelRoutingProfile `profile_id` |
| `route_profile_version` | ModelRoutingProfile `version` |
| `prompt_template_version` | Fixed prompt/template identifier (for example `llm-judge-prompt-v1`) |
| `generation_params` | `{ temperature, max_tokens, response_format_json, task_class, risk_level }` |
| `raw_structured_response` | Parsed JSON object when valid; otherwise raw content string under a failure envelope |

Callers may also retain gateway `usage` when present. Replay tests freeze gateway responses and assert these fields are present and stable.

## Adapter selection

| Env | Judge |
| --- | --- |
| unset / `heuristic` | `HeuristicJudge` (tests, bootstrap default) |
| `litellm` | `LiteLLMJudge` behind the `Judge` protocol |

Composition root: `rule_engine_service.bootstrap.build_container`.

## Related Documents

- `03-low-level-design.md` — evaluation pipeline and judge placement
- `06-detailed-section-design.md` — LLM-as-a-Judge rationale
- `docs/06-technical-logic/04-rules-orchestration-technical-logic.md` — technical constraints
- `docs/13-technology-stack-and-platform-decisions/10-model-routing-profiles-with-litellm.md` — `rules.judge` routing
- `docs/10-gap-analysis/03-technical-implementation-gaps.md` — GAP-T05
