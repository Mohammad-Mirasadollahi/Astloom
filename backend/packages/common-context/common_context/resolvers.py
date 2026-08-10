from __future__ import annotations

from typing import Any, Mapping


def score_item(weights: Mapping[str, float], scores: Mapping[str, float]) -> float:
    """Deterministic weighted sum used by common-context bundle resolution."""
    total = 0.0
    for key, weight in weights.items():
        total += float(scores.get(key, 0.0)) * float(weight)
    return total


def select_within_budget(
    items: list[dict[str, Any]],
    *,
    token_budget: int,
    score_key: str = "score",
    token_key: str = "token_estimate",
) -> list[dict[str, Any]]:
    """Greedy select highest-scoring items until the token budget is exhausted."""
    if token_budget < 1:
        return []
    ranked = sorted(items, key=lambda item: float(item.get(score_key) or 0.0), reverse=True)
    selected: list[dict[str, Any]] = []
    used = 0
    for item in ranked:
        cost = int(item.get(token_key) or 0)
        if cost < 0:
            continue
        if used + cost > token_budget:
            continue
        selected.append(item)
        used += cost
    return selected
