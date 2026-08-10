from __future__ import annotations

from common_context import load_profile, score_item, select_within_budget, validate_profile


def test_common_context_profile_loads_and_validates():
    profile = load_profile()
    assert profile["profile_id"] == "default"
    assert validate_profile(profile) == []


def test_score_and_budget_selection():
    profile = load_profile()
    score = score_item(
        profile["weights"],
        {
            "frequency": 1.0,
            "recency": 1.0,
            "confidence": 1.0,
            "user_pinning": 0.0,
            "task_similarity": 0.5,
            "project_relevance": 0.5,
            "effectiveness": 0.5,
        },
    )
    assert 0.0 < score < 1.0
    selected = select_within_budget(
        [
            {"id": "a", "score": 0.9, "token_estimate": 100},
            {"id": "b", "score": 0.8, "token_estimate": 100},
            {"id": "c", "score": 0.7, "token_estimate": 100},
        ],
        token_budget=200,
    )
    assert [item["id"] for item in selected] == ["a", "b"]
