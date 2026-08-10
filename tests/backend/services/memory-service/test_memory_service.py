from memory_service.api import app
from memory_service.core import MemoryService, Scope
from memory_service.testing import InMemoryStore


SCOPE = Scope("t", "w", "p")


def memory(kind="semantic", title="Current architecture rule", body="Use dependency injection for memory retrieval.", **extra):
    return {
        "kind": kind,
        "title": title,
        "body": body,
        "tags": extra.pop("tags", ["architecture", "memory"]),
        "evidence_refs": extra.pop("evidence_refs", ["decision-1"]),
        "source_refs": extra.pop("source_refs", ["worklog-1"]),
        "confidence": extra.pop("confidence", 0.9),
        **extra,
    }


def test_consolidation_retrieval_scope_and_restricted_boundary():
    store = InMemoryStore()
    service = MemoryService(store)

    created = service.create_memory(SCOPE, "agent", "corr", "one", memory())
    assert service.create_memory(SCOPE, "agent", "corr", "one", memory()).id == created.id

    restricted = service.create_memory(
        SCOPE,
        "agent",
        "corr",
        "restricted",
        memory("restricted", "Secret token rule", "token=hidden must never enter prompts."),
    )
    assert "hidden" not in restricted.public()["body"]

    consolidated = service.consolidate_memory(SCOPE, "agent", "corr", "consolidate", [created.id], "phase boundary")
    assert consolidated[0].state.value == "active"

    bundle = service.retrieve_context(SCOPE, "agent", "corr", "memory dependency injection architecture", token_budget=80).public()
    assert [item["memory"]["id"] for item in bundle["items"]] == [created.id]
    assert {item["reason"] for item in bundle["excluded"]} >= {"restricted_memory_boundary"}

    other_tenant = service.retrieve_context(Scope("other", "w", "p"), "agent", "corr", "memory dependency injection architecture").public()
    assert other_tenant["items"] == []
    assert store.outbox()[-1]["event_type"] == "ContextBundleBuilt"


def test_repeated_question_normalization_and_faq_promotion_requires_evidence():
    service = MemoryService(InMemoryStore())

    first = service.observe_question(SCOPE, "agent", "corr", "q1", "How do we build context bundles?", ["doc-1"])
    second = service.observe_question(SCOPE, "agent", "corr", "q2", "how do we build context bundles", ["doc-2"])
    assert first.id == second.id
    assert second.observations == 2

    repeated = service.list_repeated_questions(SCOPE)
    assert repeated[0].normalized_question == "how do we build context bundles"

    promoted = service.promote_faq(SCOPE, "agent", "corr", "faq", second.id, "Use scoped retrieval, evidence, weights, and token budgets.")
    assert promoted.state.value == "approved_faq"


def test_work_batch_ready_state_and_event_contract():
    store = InMemoryStore()
    service = MemoryService(store)

    item = service.create_memory(SCOPE, "agent", "corr", "one", memory())
    batch = service.open_batch(SCOPE, "agent", "corr", "batch", "phase boundary", [item.id], ["memory_consolidation"])

    ready = service.mark_batch_ready(SCOPE, "agent", "corr", "ready", batch.id, "meaningful work boundary")
    assert ready.state.value == "ready_for_consolidation"
    assert store.get_batch(batch.id, SCOPE).state.value == "ready_for_consolidation"

    event = store.outbox()[-1]
    assert event["event_type"] == "BatchReadyForConsolidation"
    assert event["event_version"] == 1
    assert event["producer"] == "memory-service"
    assert event["tenant_id"] == "t"
    assert event["project_id"] == "p"


def test_api_contract_routes_are_registered():
    routes = {route.path for route in app(MemoryService(InMemoryStore())).routes}
    assert "/api/v1/projects/{project_id}/memory-items" in routes
    assert "/api/v1/projects/{project_id}/memory-items/{memory_item_id}" in routes
    assert "/api/v1/projects/{project_id}/memory-items/{memory_item_id}:promote" in routes
    assert "/api/v1/projects/{project_id}/memory-items/{memory_item_id}:deprecate" in routes
    assert "/api/v1/projects/{project_id}/memory-promotions" in routes
    assert "/api/v1/projects/{project_id}/context-bundles" in routes
    assert "/api/v1/projects/{project_id}/question-memories/{question_id}:promote-faq" in routes
    assert "/api/v1/projects/{project_id}/memory-decays" in routes
    assert "/api/v1/projects/{project_id}/question-memories/{question_id}:resolve-documentation" in routes
    assert "/api/v1/projects/{project_id}/curious-questions" in routes


def test_current_state_default_excludes_episodic_and_stale():
    service = MemoryService(InMemoryStore())
    semantic = service.create_memory(SCOPE, "agent", "corr", "sem", memory())
    service.consolidate_memory(SCOPE, "agent", "corr", "c1", [semantic.id], "activate current")
    episodic = service.create_memory(
        SCOPE,
        "agent",
        "corr",
        "epi",
        memory("episodic", "Past migration note", "memory dependency injection history from last quarter."),
    )
    service.consolidate_memory(SCOPE, "agent", "corr", "c2", [episodic.id], "activate episodic")
    stale = service.create_memory(
        SCOPE,
        "agent",
        "corr",
        "stale",
        memory("semantic", "Old memory rule", "memory dependency injection obsolete guidance."),
    )
    service.consolidate_memory(SCOPE, "agent", "corr", "c3", [stale.id], "activate stale candidate")
    decayed = service.decay_memory(SCOPE, "agent", "corr", "decay", [stale.id], "superseded guidance")
    assert decayed[0].state.value == "stale"

    bundle = service.retrieve_context(SCOPE, "agent", "corr", "memory dependency injection architecture", token_budget=200).public()
    selected_ids = [item["memory"]["id"] for item in bundle["items"]]
    assert selected_ids == [semantic.id]
    assert bundle["prompt_cache"]["version"] == 1
    reasons = {item["id"]: item["reason"] for item in bundle["excluded"]}
    assert reasons[episodic.id] == "historical_fact_not_requested"
    assert reasons[stale.id] == "stale_memory_excluded"

    history = service.retrieve_context(SCOPE, "agent", "corr", "memory dependency injection history audit", token_budget=200).public()
    assert episodic.id in [item["memory"]["id"] for item in history["items"]]
    assert service.list_stale_memory(SCOPE)[0].id == stale.id


def test_curiosity_and_missing_documentation_outcomes():
    service = MemoryService(InMemoryStore())
    first = service.observe_question(SCOPE, "agent", "corr", "q1", "Where is auth documented?", ["sym-1"])
    second = service.observe_question(SCOPE, "agent", "corr", "q2", "where is auth documented", ["sym-2"])
    assert first.id == second.id
    curious = service.list_curious_questions(SCOPE)
    assert curious[0]["curiosity_score"] >= 2.0

    draft = service.resolve_missing_documentation(
        SCOPE,
        "agent",
        "corr",
        "doc-high",
        second.id,
        0.9,
        "Auth lives in docs/security/auth.md.",
    )
    assert draft["outcome"] == "documentation_draft"
    assert draft["question_memory"]["state"] == "draft_generated"

    gap_q = service.observe_question(SCOPE, "agent", "corr", "q3", "How does billing retry work?", ["bill-1"])
    service.observe_question(SCOPE, "agent", "corr", "q4", "how does billing retry work", ["bill-2"])
    gap = service.resolve_missing_documentation(SCOPE, "agent", "corr", "doc-low", gap_q.id, 0.1, None)
    assert gap["outcome"] == "knowledge_gap"
    assert gap["question_memory"]["state"] == "blocked_by_gap"

    task_q = service.observe_question(SCOPE, "agent", "corr", "q5", "How do we version APIs?", ["api-1"])
    service.observe_question(SCOPE, "agent", "corr", "q6", "how do we version apis", ["api-2"])
    task = service.resolve_missing_documentation(SCOPE, "agent", "corr", "doc-mid", task_q.id, 0.5, None)
    assert task["outcome"] == "task"
    assert task["question_memory"]["state"] == "searching"


def test_promote_working_to_long_term_and_browse_filters():
    from datetime import UTC, datetime, timedelta

    from fastapi.testclient import TestClient

    store = InMemoryStore()
    service = MemoryService(store)
    working = service.create_memory(
        SCOPE,
        "agent",
        "corr",
        "work-1",
        memory(
            "working",
            "Temp auth note",
            "working memory dependency injection note",
            state="active",
            expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        ),
    )
    assert working.kind.value == "working"
    promoted = service.promote_memory(SCOPE, "human", "corr", "promote-1", [working.id], "keep as project truth")
    assert promoted[0].kind.value == "semantic"
    assert promoted[0].state.value == "active"
    assert promoted[0].expires_at is None
    assert any(event["event_type"] == "MemoryPromotedToLongTerm" for event in store.outbox())

    listed = service.list_memories(SCOPE, kind="semantic", q="dependency injection")
    assert [item.id for item in listed] == [working.id]
    pinned = service.update_memory(
        SCOPE,
        "human",
        "corr",
        "pin-1",
        working.id,
        {"pinned": True, "expected_version": promoted[0].version},
    )
    assert pinned.pinned is True
    assert service.list_memories(SCOPE, pinned=True)[0].id == working.id

    with TestClient(app(service)) as client:
        response = client.get(
            f"/api/v1/projects/p/memory-items/{working.id}",
            headers={"X-Tenant-Id": "t", "X-Workspace-Id": "w"},
        )
    assert response.status_code == 200
    assert response.json()["memory"]["kind"] == "semantic"
    assert response.json()["memory"]["pinned"] is True


def test_deprecate_excludes_from_default_retrieve():
    store = InMemoryStore()
    service = MemoryService(store)
    item = service.create_memory(SCOPE, "agent", "corr", "sem-1", memory(state="active"))
    forgotten = service.deprecate_memory(SCOPE, "human", "corr", "forget-1", [item.id], "no longer true")
    assert forgotten[0].state.value == "deprecated"
    bundle = service.retrieve_context(SCOPE, "agent", "corr", "memory dependency injection architecture").public()
    assert bundle["items"] == []
    assert any(entry["id"] == item.id and entry["reason"] == "inactive_memory_state" for entry in bundle["excluded"])
    stale = service.list_stale_memory(SCOPE)
    assert stale[0].id == item.id


def test_working_memory_ttl_expires_lazily():
    from datetime import UTC, datetime, timedelta

    service = MemoryService(InMemoryStore())
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    working = service.create_memory(
        SCOPE,
        "agent",
        "corr",
        "ttl-1",
        memory(
            "working",
            "Session scratch",
            "memory dependency injection scratchpad",
            state="active",
            expires_at=past,
        ),
    )
    listed = service.list_memories(SCOPE, kind="working")
    assert listed[0].id == working.id
    assert listed[0].state.value == "stale"
    bundle = service.retrieve_context(SCOPE, "agent", "corr", "memory dependency injection architecture").public()
    assert all(entry["memory"]["id"] != working.id for entry in bundle["items"])
    assert any(entry["id"] == working.id for entry in bundle["excluded"])
