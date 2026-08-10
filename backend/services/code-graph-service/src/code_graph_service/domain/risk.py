"""Change / symbol risk scoring (Wave 1 — code-review-graph-inspired)."""

from __future__ import annotations

from dataclasses import dataclass

from .flows import SECURITY_KEYWORDS


@dataclass(frozen=True)
class RiskFactors:
    flow_criticalities: tuple[float, ...] = ()
    flow_membership_count: int = 0
    cross_community_callers: int = 0
    test_count: int = 0
    caller_count: int = 0
    name: str = ""
    qualified_name: str = ""
    churn_commits: int = 0


def compute_risk_score(factors: RiskFactors) -> float:
    """Return risk in [0.0, 1.0].

    Weights (aligned with code-review-graph):
      - flow criticality / membership: cap 0.25
      - cross-community callers: 0.05 each, cap 0.15
      - test coverage gap: 0.30 untested → 0.05 at 5+ tests
      - security name: +0.20
      - caller count: /20, cap 0.10
      - churn: /10, cap 0.15
    """
    score = 0.0
    if factors.flow_criticalities:
        score += min(sum(factors.flow_criticalities), 0.25)
    else:
        score += min(factors.flow_membership_count * 0.05, 0.25)

    score += min(factors.cross_community_callers * 0.05, 0.15)
    score += 0.30 - (min(factors.test_count / 5.0, 1.0) * 0.25)

    blob = f"{factors.name} {factors.qualified_name}".lower()
    if any(kw in blob for kw in SECURITY_KEYWORDS):
        score += 0.20

    score += min(factors.caller_count / 20.0, 0.10)
    if factors.churn_commits:
        score += min(factors.churn_commits / 10.0, 1.0) * 0.15

    return round(min(max(score, 0.0), 1.0), 4)


def risk_level(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.5:
        return "high"
    if score >= 0.3:
        return "medium"
    return "low"
