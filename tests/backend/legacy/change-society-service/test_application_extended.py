from __future__ import annotations

import pytest

from change_society.application.evaluation import run_single_agent_baseline, score_output
from change_society.application.judging_engineering_profile import build_judging_engineering_profile
from change_society.application.submission_compliance import build_submission_compliance_report
from change_society.infrastructure.evidence_catalog import ScenarioEvidenceProvider
from change_society.infrastructure.fake_model import DeterministicModelClient
from change_society.infrastructure.repositories import InMemoryRunRepository

from change_society.infrastructure.evidence_catalog import DEMO_SCENARIO_IDS

from conftest import SCOPE, make_service


def test_run_single_agent_baseline_returns_scored_metrics():
    provider = ScenarioEvidenceProvider()
    scenario = provider.get_scenario("pricing-refactor")
    included, _ = provider.retrieve(SCOPE, scenario.scenario_id, scenario.default_request, 1800)
    evidence_text = "\n".join(f"[{e.evidence_id}] {e.title}: {e.content}" for e in included)
    output, metrics = run_single_agent_baseline(
        DeterministicModelClient(), scenario, scenario.default_request, evidence_text,
    )
    assert output["risk_level"] in {"low", "medium", "high", "critical"}
    assert metrics["input_tokens"] > 0
    assert "critical_impact_recall" in metrics


def test_submission_compliance_includes_judging_profile():
    service = make_service()
    report = build_submission_compliance_report(
        model=service.model,
        repository=service.repository,
        model_provider="fake",
        store="memory",
        environment="development",
        alibaba_proof_module="x.py",
        architecture_doc="doc.md",
        evaluation_artifact="ev.json",
    )
    assert "judging_engineering_profile" in report
    assert len(report["judging_engineering_profile"]["criteria"]) == 4


def test_judging_profile_each_criterion_has_implementations():
    profile = build_judging_engineering_profile(model_health={})
    for item in profile["criteria"]:
        assert item["implemented_in_code"], item["id"]
        for entry in item["implemented_in_code"]:
            assert entry["capability"]
            assert entry["modules"]


def test_evaluate_all_scenarios_via_service():
    service = make_service()
    result = service.evaluate_all_scenarios(SCOPE, "actor", "eval-prefix")
    assert result["sample_count"] == len(DEMO_SCENARIO_IDS)
    assert len(result["scenarios"]) == len(DEMO_SCENARIO_IDS)
    for row in result["scenarios"]:
        assert row["run_id"]
        assert "evaluation" in row


def test_repository_health_in_memory():
    repo = InMemoryRunRepository()
    health = repo.health()
    assert health["ready"] is True
    assert health["store"] == "in_memory_test_fake"
