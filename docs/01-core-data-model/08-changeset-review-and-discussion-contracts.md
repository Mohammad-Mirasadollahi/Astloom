---
doc_id: as.doc.core.changeset-review-discussion-contracts
title: 08 - ChangeSet Review And Discussion Contracts
doc_type: contract
status: draft
schema_version: '1.0'
owner: platform-architecture
summary: Entity fields, state machines, commands, queries, and events for ChangeSet, ReviewThread,
  ReviewComment, DiscussionComment, WorkLabel, and WorkMilestone. Backend MVP for ChangeSet review
  surface ships in core-data-service; WorkMilestone and UI queries remain deferred.
tags:
- changeset
- review
- comment
- label
- contracts
- events
phase: 01-core-data-model
canonical_path: docs/01-core-data-model/08-changeset-review-and-discussion-contracts.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/services/core-data-service/src/core_data_service/core.py::Kind
- backend/services/core-data-service/src/core_data_service/core.py::CoreData.create_changeset
related_docs:
- as.doc.core.agent-collaboration-work-surface
- as.doc.core.contracts
doc_version: 1.1.1
audience:
- engineer
- architect
- agent
primary_entities:
- ChangeSet
- ReviewThread
- ReviewComment
- DiscussionComment
- WorkLabel
- WorkMilestone
relations_declared:
- type: depends_on
  target: docs/01-core-data-model/07-agent-collaboration-work-surface.md
- type: complements
  target: docs/01-core-data-model/04-data-contracts-and-events.md
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 08 - ChangeSet Review And Discussion Contracts

## Purpose

Define implementation-grade contracts for the Astloom-native collaboration aggregates introduced in `07-agent-collaboration-work-surface.md`. These contracts extend Phase 1 core data; they do not replace Activity, WorkLog, Decision, Issue, or Task.

Backend MVP (GAP-A08): `core-data-service` implements kinds `changeset`, `review_thread`, `review_comment`, `discussion_comment`, `work_label` with lifecycle transitions, self-approval forbid, review-verdict rollup to `changes_requested`, and HTTP routes. `WorkMilestone`, full field richness, and `ExplainChangeSetGate` remain deferred with UI surfaces.

## Professional Audience

Engineers implementing core-data-service APIs, SDKs, admin UI, and adapter projections.

## Entity Contracts

Common fields on every entity below: `id`, `tenant_id`, `workspace_id`, `project_id`, `created_at`, `updated_at`, `created_by` (actor ref: agent or human), `schema_version`, `source_refs[]`, `correlation_id` (when created in a workflow).

### ChangeSet

```text
ChangeSet(
  id,
  title,
  description,
  status,                         # draft|open|changes_requested|approved|applying|applied|rejected|withdrawn|superseded
  issue_id?,                      # optional link
  task_id?,                       # preferred link when planned work exists
  agent_ticket_id?,               # ticket that produced or owns the proposal
  intent_summary,                 # structured short intent for routers/memory
  risk_class,                     # low|medium|high|critical
  base_descriptor,                # { kind: branch|commit|tag|snapshot, value, repo_ref? }
  head_descriptor,                # same shape; may be "artifact_bundle" when no branch yet
  revision,                       # monotonic int; increments on new patch upload
  patch_artifact_refs[],          # object-storage / artifact ids for diff bundles
  test_evidence_refs[],
  policy_check_refs[],            # references to rule evaluations / required gates
  supersedes_changeset_id?,
  decision_id?,                   # set when applied with recorded rationale
  labels[],                       # WorkLabel ids
  milestone_id?,
  external_projections[]          # [{ system: github|gitlab|..., external_id, url?, synced_at? }]
)
```

Invariants:

- `project_id` immutable after create.
- At least one of `issue_id` or `task_id` required when status leaves `draft` (configurable; default on).
- `revision` increments only with new `patch_artifact_refs`.
- Transition to `applied` requires at least one Activity with apply evidence and matching `correlation_id`.
- `external_projections` are informational; never authoritative for status.

### ReviewThread

```text
ReviewThread(
  id,
  changeset_id,
  changeset_revision,             # revision under review
  kind,                           # general|anchored
  anchor?,                        # { path, start_line?, end_line?, symbol_ref? }
  status,                         # open|resolved|wont_fix|outdated
  created_by
)
```

Invariants:

- `anchored` requires `anchor.path`.
- Mark `outdated` when ChangeSet `revision` advances past `changeset_revision` and policy says anchors invalidate.

### ReviewComment

```text
ReviewComment(
  id,
  thread_id,
  body,                           # markdown subset; redaction rules apply
  verdict?,                       # comment|approve|request_changes|block
  author_actor_ref,
  evidence_refs[],
  created_at
)
```

Invariants:

- `block` / `request_changes` from an authorized reviewer forces ChangeSet toward `changes_requested` unless overridden by EscalationTicket.
- Self-`approve` rejected when `forbid_self_approval` is enabled for the project.

### DiscussionComment

```text
DiscussionComment(
  id,
  parent_type,                    # issue|task|changeset|agent_ticket
  parent_id,
  body,
  author_actor_ref,
  reply_to_comment_id?,
  created_at,
  edited_at?,
  visibility                      # project|restricted
)
```

### WorkLabel

```text
WorkLabel(
  id,
  project_id,
  key,                            # stable slug, unique per project
  display_name,
  description?,
  color_token?,
  allowed_parent_types[],         # subset of issue|task|changeset|agent_ticket
  status                          # active|archived
)

WorkLabelBinding(
  label_id,
  parent_type,
  parent_id,
  bound_at,
  bound_by
)
```

### WorkMilestone (optional)

```text
WorkMilestone(
  id,
  project_id,
  title,
  description?,
  target_date?,
  status                          # open|closed
)
```

## State Machines

### ChangeSet

| From | To | Command / trigger |
| --- | --- | --- |
| (new) | draft | `CreateChangeSet` |
| draft | open | `OpenChangeSet` |
| open | changes_requested | reviewer `request_changes`/`block` or policy |
| changes_requested | open | `UpdateChangeSetRevision` (new patch) |
| open / changes_requested | approved | approvals satisfied + policy |
| approved | applying | `DispatchApplyChangeSet` |
| applying | applied | apply Activity success |
| applying | changes_requested | apply Activity failure |
| open / draft | withdrawn | `WithdrawChangeSet` |
| * | rejected | `RejectChangeSet` (authorized) |
| open / approved | superseded | newer ChangeSet supersedes |

Illegal: `draft → applied`, `rejected → applied`, any transition that sets `applied` without evidence Activity.

### ReviewThread

`open → resolved | wont_fix | outdated`

### Existing entities

Issue, Task, and AgentTicket state machines remain as defined in `03-low-level-design.md` and the control-plane boundary. This document adds **link requirements**, not replacement states:

- Task `review` may require linked ChangeSet in `approved` or `applied` per project policy.
- AgentTicket `:submit-review` may attach `changeset_id` + `changeset_revision`.

## Commands

| Command | Result |
| --- | --- |
| `CreateChangeSet` | ChangeSet `draft` |
| `OpenChangeSet` | `open` |
| `UpdateChangeSetRevision` | new revision + optional auto-outdate threads |
| `WithdrawChangeSet` / `RejectChangeSet` | terminal-ish statuses |
| `DispatchApplyChangeSet` | `applying` + AgentTicket or CI dispatch |
| `MarkChangeSetApplied` | `applied` (idempotent; requires evidence) |
| `CreateReviewThread` | thread on ChangeSet revision |
| `AddReviewComment` | comment; may transition ChangeSet |
| `ResolveReviewThread` | thread resolved |
| `AddDiscussionComment` | discussion on allowed parent |
| `CreateWorkLabel` / `BindWorkLabel` / `UnbindWorkLabel` | taxonomy |
| `CreateWorkMilestone` / `AssignMilestone` | optional planning |

All commands require scope headers (`X-Tenant-Id`, `X-Workspace-Id`, project path), actor identity, and `Idempotency-Key` where side effects create records.

## Queries

| Query | Notes |
| --- | --- |
| `GetChangeSet` | includes latest revision summary, not full diff bytes |
| `ListChangeSets` | filter by status, issue, task, label, milestone |
| `ListReviewThreads` | by changeset_id + revision |
| `ListDiscussionComments` | by parent_type + parent_id |
| `ListWorkLabels` | project taxonomy |
| `ExplainChangeSetGate` | why not approved (missing reviews, policy, self-approval) |

Diff bytes are fetched via artifact service URLs after authz, not embedded in list queries.

## Events

```text
changeset.created
changeset.opened
changeset.revision_updated
changeset.changes_requested
changeset.approved
changeset.applying
changeset.applied
changeset.rejected
changeset.withdrawn
changeset.superseded
review_thread.created
review_thread.resolved
review_thread.outdated
review_comment.added
discussion_comment.added
work_label.created
work_label.bound
work_label.unbound
work_milestone.created
work_milestone.assigned
```

Event envelope rules match `04-data-contracts-and-events.md`: `event_id`, `event_type`, `occurred_at`, `source`, `correlation_id`, `tenant_id` (plus workspace/project as required by platform envelope standard).

## API Shape (illustrative)

Aligned with `../14-api-design-and-naming-standards/`:

```text
POST   /api/v1/projects/{project_id}/change-sets
GET    /api/v1/projects/{project_id}/change-sets
GET    /api/v1/projects/{project_id}/change-sets/{change_set_id}
POST   /api/v1/projects/{project_id}/change-sets/{change_set_id}:open
POST   /api/v1/projects/{project_id}/change-sets/{change_set_id}:update-revision
POST   /api/v1/projects/{project_id}/change-sets/{change_set_id}:withdraw
POST   /api/v1/projects/{project_id}/change-sets/{change_set_id}:reject
POST   /api/v1/projects/{project_id}/change-sets/{change_set_id}:dispatch-apply
POST   /api/v1/projects/{project_id}/change-sets/{change_set_id}:mark-applied
GET    /api/v1/projects/{project_id}/change-sets/{change_set_id}:explain-gate

POST   /api/v1/projects/{project_id}/change-sets/{change_set_id}/review-threads
POST   /api/v1/projects/{project_id}/review-threads/{thread_id}/comments
POST   /api/v1/projects/{project_id}/review-threads/{thread_id}:resolve

POST   /api/v1/projects/{project_id}/{parent_collection}/{parent_id}/discussion-comments
GET    /api/v1/projects/{project_id}/{parent_collection}/{parent_id}/discussion-comments

POST   /api/v1/projects/{project_id}/work-labels
POST   /api/v1/projects/{project_id}/work-label-bindings
```

`parent_collection` ∈ `issues` | `tasks` | `change-sets` | `agent-tickets`.

## Extension To Existing Contracts

Add to the Phase 1 catalog in spirit (canonical detail remains here until `04-data-contracts-and-events.md` is migrated):

| Existing entity | Additive fields |
| --- | --- |
| Task | `changeset_ids[]` (read model) or query-by-task |
| AgentTicket | `changeset_id?`, `changeset_revision?` on submit-review |
| Activity | `changeset_id?`, `changeset_revision?` when action is patch/apply related |
| Decision | may link `changeset_id` when recording apply rationale |

## Security Rules

- Authorization evaluated on parent project + entity ACL class.
- `visibility=restricted` discussion bodies excluded from default ContextBundles.
- Adapter mirrors strip secrets; external ids cannot drive native transitions.

## Acceptance Criteria

- [ ] Contract tests cover every legal and illegal ChangeSet transition listed above.
- [ ] `MarkChangeSetApplied` without evidence Activity fails closed.
- [ ] Review `request_changes` moves ChangeSet to `changes_requested`.
- [ ] DiscussionComment parent types are enforced.
- [ ] WorkLabelBinding rejects disallowed parent types.
- [ ] OpenAPI / API catalog updated when implementation starts (not required for this doc-only change).

## Related Documents

- Product surface: `07-agent-collaboration-work-surface.md`
- Baseline entities: `04-data-contracts-and-events.md`
- External systems: `../05-interoperability-ecosystem/10-external-vcs-and-tracker-mapping.md`
