from __future__ import annotations

from change_society.domain.models import NotFoundError, Scope
from change_society.infrastructure.evidence_catalog import DEMO_SCENARIO_IDS, ScenarioEvidenceProvider


SCOPE = Scope("tenant", "workspace", "project")


def test_retrieve_excludes_restricted_and_deprecated_evidence():
    provider = ScenarioEvidenceProvider()
    included, excluded = provider.retrieve(SCOPE, "pricing-refactor", "checkout tax refactor base_price", 5000)
    ids = {item.evidence_id for item in included}
    assert "ev_diff_price" in ids
    assert "ev_secret" not in ids
    assert "ev_old_refactor" not in ids
    reasons = {item["reason"] for item in excluded}
    assert "restricted_memory_boundary" in reasons
    assert "not_current" in reasons


def test_remember_decision_is_scoped_per_scenario_and_project():
    provider = ScenarioEvidenceProvider()
    provider.remember_decision(SCOPE, "pricing-refactor", "Approved", "pricing payload", ["ev_diff_price"])
    provider.remember_decision(SCOPE, "password-migration", "Approved", "password payload", ["ev_auth_change"])
    other_scope = Scope("tenant", "workspace", "other-project")
    provider.remember_decision(other_scope, "pricing-refactor", "Approved", "other project", ["ev_diff_price"])
    included_pricing, _ = provider.retrieve(SCOPE, "pricing-refactor", "pricing checkout", 5000)
    included_password, _ = provider.retrieve(SCOPE, "password-migration", "password auth", 5000)
    pricing_memory = [item for item in included_pricing if item.kind == "decision" and item.title == "Approved"]
    password_memory = [item for item in included_password if item.kind == "decision" and item.title == "Approved"]
    assert any("pricing payload" in item.content for item in pricing_memory)
    assert all("password payload" not in item.content for item in included_pricing)
    assert any("password payload" in item.content for item in password_memory)
    included_other, _ = provider.retrieve(other_scope, "pricing-refactor", "pricing", 5000)
    assert all("pricing payload" not in item.content and "password payload" not in item.content for item in included_other if item.kind == "decision")
    assert any("other project" in item.content for item in included_other if item.kind == "decision")


def test_get_scenario_raises_not_found_for_unknown_id():
    provider = ScenarioEvidenceProvider()
    try:
        provider.get_scenario("missing")
        raise AssertionError("expected not found")
    except NotFoundError:
        pass


def test_list_scenarios_returns_all_versioned_benchmarks():
    provider = ScenarioEvidenceProvider()
    assert {item.scenario_id for item in provider.list_scenarios()} == set(DEMO_SCENARIO_IDS)
