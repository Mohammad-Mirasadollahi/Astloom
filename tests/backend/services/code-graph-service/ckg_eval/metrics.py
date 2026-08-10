"""Ranking metrics for offline retrieval eval."""

from __future__ import annotations

import math


def dcg_at_k(relevances: list[float], k: int) -> float:
    total = 0.0
    for i, rel in enumerate(relevances[:k], start=1):
        total += (2**rel - 1) / math.log2(i + 1)
    return total


def ndcg_at_k(ranked_ids: list[str], relevant: set[str], *, k: int = 10) -> float:
    """Binary relevance nDCG@k; relevant ids are gold documents."""
    if not relevant:
        return 0.0
    rels = [1.0 if sid in relevant else 0.0 for sid in ranked_ids[:k]]
    ideal = [1.0] * min(k, len(relevant))
    ideal_dcg = dcg_at_k(ideal, k)
    if ideal_dcg <= 0:
        return 0.0
    return round(dcg_at_k(rels, k) / ideal_dcg, 4)


def average_ndcg(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)
