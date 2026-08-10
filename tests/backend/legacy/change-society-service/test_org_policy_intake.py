from __future__ import annotations

import asyncio

import httpx

from change_society.application.org_policy_intake import (
    build_candidate_policies,
    candidates_to_activate,
    infer_policy_tags,
)
from change_society.domain.models import Scope, ValidationError
from change_society.infrastructure.evidence_catalog import ScenarioEvidenceProvider


from change_society.interfaces.api import create_api
from test_change_society import HEADERS, SCOPE, make_service

PROVIDER_SCOPE = Scope("tenant", "workspace", "project")

PROJECT = "project-a"
BASE = f"/api/v1/projects/{PROJECT}"
NARRATIVE = (
    "Our checkout workflow requires Platform and Mobile approval before any breaking HTTP API "
    "or mobile contract field such as taxIncluded is removed from responses."
)


def test_infer_gdpr_and_privacy_tags_together():
    text = "Automate GDPR erasure for users while finance invoices stay under retention policy."
    tags = infer_policy_tags(text)
    assert "privacy-sensitive-change" in tags
    assert "gdpr-erasure-required" in tags


def test_candidates_to_activate_skips_catalog_only_resolution():
    session = {
        "challenges": [
            {
                "challenge_id": "challenge_overlap_api-breaking-change",
                "resolution": {"option_id": "catalog_only"},
                "linked_candidate_ids": ["cand_api-breaking-change"],
            }
        ],
        "candidate_policies": [{"candidate_id": "cand_api-breaking-change", "policy_tag": "api-breaking-change"}],
    }
    adopted = candidates_to_activate(session, ["cand_api-breaking-change", "cand_other"])
    assert adopted == []


def test_build_candidate_policies_includes_scenario_required_tags():
    candidates = build_candidate_policies("refactor handler only", "", ("api-breaking-change",))
    tags = {item["policy_tag"] for item in candidates}
    assert "api-breaking-change" in tags


def test_service_analyze_rejects_short_narrative():
    service = make_service()
    try:
        service.analyze_org_policy_intake(SCOPE, "actor", "checkout-api-refactor", "too short", "")
        raise AssertionError("expected validation")
    except ValidationError:
        pass


def test_service_full_intake_flow():
    service = make_service()
    session = service.analyze_org_policy_intake(SCOPE, "lead-1", "checkout-api-refactor", NARRATIVE, "English docs only.")
    assert session["candidate_policies"]
    for challenge in session["challenges"]:
        session = service.resolve_org_policy_challenge(
            SCOPE,
            session["intake_session_id"],
            challenge["challenge_id"],
            challenge["default_recommendation"],
        )
    adopted = [c["candidate_id"] for c in session["candidate_policies"] if c["policy_tag"] == "api-breaking-change"]
    result = service.activate_org_policy_intake(SCOPE, session["intake_session_id"], adopted, "lead-1")
    assert result["activated_policies"]
    listed = service.list_org_policies(SCOPE)
    assert any(item["evidence_id"].startswith("org_policy_") for item in listed)


def test_society_run_succeeds_after_org_policy_activation():
    service = make_service()
    session = service.analyze_org_policy_intake(SCOPE, "lead-1", "checkout-api-refactor", NARRATIVE, "")
    for challenge in session["challenges"]:
        service.resolve_org_policy_challenge(
            SCOPE,
            session["intake_session_id"],
            challenge["challenge_id"],
            challenge["default_recommendation"],
        )
    service.activate_org_policy_intake(
        SCOPE,
        session["intake_session_id"],
        ["cand_api-breaking-change"],
        "lead-1",
    )
    run = service.create_run(SCOPE, "developer-a", "corr-intake", "create-intake-1", "checkout-api-refactor", None)
    assert run.state.value == "awaiting_approval"
    assert run.conflicts


def test_api_org_policy_intake_happy_path():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            analyze = await client.post(
                f"{BASE}/org-policy-intake:analyze",
                headers=HEADERS,
                json={"scenario_id": "checkout-api-refactor", "process_narrative": NARRATIVE, "constraints": ""},
            )
            assert analyze.status_code == 200
            body = analyze.json()
            assert body["correlation_id"]
            session = body["intake_session"]
            session_id = session["intake_session_id"]
            for challenge in session["challenges"]:
                resolved = await client.post(
                    f"{BASE}/org-policy-intake/{session_id}/challenges/{challenge['challenge_id']}:resolve",
                    headers=HEADERS,
                    json={"option_id": challenge["default_recommendation"]},
                )
                assert resolved.status_code == 200
                session = resolved.json()["intake_session"]
            activate = await client.post(
                f"{BASE}/org-policy-intake/{session_id}:activate",
                headers=HEADERS,
                json={"adopted_candidate_ids": [c["candidate_id"] for c in session["candidate_policies"]]},
            )
            assert activate.status_code == 200
            assert activate.json()["activated_policies"]
            listed = await client.get(f"{BASE}/org-policies", headers=HEADERS)
            assert listed.status_code == 200
            assert listed.json()["items"]
            fetched = await client.get(f"{BASE}/org-policy-intake/{session_id}", headers=HEADERS)
            assert fetched.status_code == 200
            assert fetched.json()["intake_session"]["state"] in {"partially_active", "completed"}

    asyncio.run(exercise())


def test_api_analyze_validation_error_for_short_narrative():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"{BASE}/org-policy-intake:analyze",
                headers=HEADERS,
                json={"scenario_id": "checkout-api-refactor", "process_narrative": "short", "constraints": ""},
            )
            assert response.status_code in {400, 422}
            if response.status_code == 400:
                assert response.json()["error"]["category"] == "validation_error"

    asyncio.run(exercise())


def test_api_activate_before_challenges_resolved_returns_validation_error():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            analyze = await client.post(
                f"{BASE}/org-policy-intake:analyze",
                headers=HEADERS,
                json={"scenario_id": "pricing-refactor", "process_narrative": NARRATIVE, "constraints": ""},
            )
            session_id = analyze.json()["intake_session"]["intake_session_id"]
            response = await client.post(
                f"{BASE}/org-policy-intake/{session_id}:activate",
                headers=HEADERS,
                json={"adopted_candidate_ids": ["cand_revenue-impacting-change"]},
            )
            assert response.status_code == 400

    asyncio.run(exercise())


def test_api_resolve_unknown_challenge_returns_not_found():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            analyze = await client.post(
                f"{BASE}/org-policy-intake:analyze",
                headers=HEADERS,
                json={"scenario_id": "checkout-api-refactor", "process_narrative": NARRATIVE, "constraints": ""},
            )
            session_id = analyze.json()["intake_session"]["intake_session_id"]
            response = await client.post(
                f"{BASE}/org-policy-intake/{session_id}/challenges/missing-challenge:resolve",
                headers=HEADERS,
                json={"option_id": "scope_project"},
            )
            assert response.status_code == 404

    asyncio.run(exercise())


def test_api_get_unknown_session_returns_not_found():
    async def exercise():
        transport = httpx.ASGITransport(app=create_api(make_service()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"{BASE}/org-policy-intake/intake_missing", headers=HEADERS)
            assert response.status_code == 404

    asyncio.run(exercise())


def test_org_policies_isolated_per_project():
    provider_scope_a = make_service()
    provider_scope_b = make_service()
    scope_b = SCOPE.__class__("tenant-a", "workspace-a", "project-b")
    session = provider_scope_a.analyze_org_policy_intake(SCOPE, "lead", "checkout-api-refactor", NARRATIVE, "")
    for challenge in session["challenges"]:
        provider_scope_a.resolve_org_policy_challenge(
            SCOPE,
            session["intake_session_id"],
            challenge["challenge_id"],
            challenge["default_recommendation"],
        )
    provider_scope_a.activate_org_policy_intake(SCOPE, session["intake_session_id"], ["cand_api-breaking-change"], "lead")
    assert provider_scope_a.list_org_policies(SCOPE)
    assert provider_scope_b.list_org_policies(scope_b) == []


def test_provider_retrieve_includes_org_policy_after_activation():
    provider = ScenarioEvidenceProvider()
    session = provider.start_org_policy_intake(
        PROVIDER_SCOPE,
        "intake_provider_1",
        "checkout-api-refactor",
        NARRATIVE,
        "",
    )
    for challenge in session["challenges"]:
        provider.resolve_org_policy_challenge(
            PROVIDER_SCOPE,
            session["intake_session_id"],
            challenge["challenge_id"],
            challenge["default_recommendation"],
        )
    provider.activate_org_policy_intake(PROVIDER_SCOPE, session["intake_session_id"], ["cand_api-breaking-change"], "lead-1")
    included, _ = provider.retrieve(PROVIDER_SCOPE, "checkout-api-refactor", "api mobile taxIncluded", 8000)
    assert any(item.evidence_id.startswith("org_policy_") for item in included)


def test_provider_activate_blocks_while_challenges_pending():
    provider = ScenarioEvidenceProvider()
    session = provider.start_org_policy_intake(
        PROVIDER_SCOPE,
        "intake_provider_2",
        "pricing-refactor",
        "All billing and checkout price changes need Product and Finance approval every time.",
        "",
    )
    try:
        provider.activate_org_policy_intake(PROVIDER_SCOPE, session["intake_session_id"], ["cand_revenue-impacting-change"], "lead-1")
        raise AssertionError("expected validation")
    except ValidationError:
        pass
