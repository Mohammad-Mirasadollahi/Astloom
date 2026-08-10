from __future__ import annotations

from change_society.application.evaluation import score_output
from change_society.application.ports import Scenario
from change_society.domain.models import Evidence


def scenario() -> Scenario:
    return Scenario(
        "demo",
        "Demo",
        "Do something risky.",
        (Evidence("ev_1", "change", "Diff", "content", tags=("pricing",)),),
        ("customer price",),
        ("revenue-impacting-change",),
        ("add tests",),
    )


def test_score_output_counts_impacts_policies_tasks_and_unsupported_claims():
    scored = score_output(
        scenario(),
        {
            "impacts": ["customer price impact"],
            "policies": ["revenue-impacting-change"],
            "tasks": ["add tests for billing"],
            "findings": ["hidden risk", "another claim"],
            "evidence_refs": ["ev_1"],
        },
    )
    assert scored["critical_impact_recall"] == 1.0
    assert scored["policy_match_recall"] == 1.0
    assert scored["task_completeness"] == 1.0
    assert scored["unsupported_claim_count"] == 0
    unsupported = score_output(scenario(), {"findings": ["a", "b"], "evidence_refs": []})
    assert unsupported["unsupported_claim_count"] == 2
    assert scored["raw"]["impact_found"] == 1


def test_score_output_handles_empty_label_sets():
    empty = Scenario("x", "x", "x", (), (), (), ())
    scored = score_output(empty, {"impacts": [], "policies": [], "tasks": [], "findings": [], "evidence_refs": []})
    assert scored["critical_impact_recall"] == 1.0
    assert scored["unsupported_claim_count"] == 0
