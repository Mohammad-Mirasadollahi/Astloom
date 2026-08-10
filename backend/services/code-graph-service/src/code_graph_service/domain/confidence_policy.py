"""Call-edge confidence caps and boosts (GAP-T02).

Role: Map evidence class / resolution path (``via``) to ``CallConfidence`` bounds
and impact eligibility; hydrate store/API confidence tokens safely.
Source of truth: ``CallConfidence`` plus ``via`` / ``provenance`` on CODE_REL metadata.
Allowed: cap or boost confidence without inventing edges; coerce null/blank/unknown
store values via ``parse_call_confidence``. Forbidden: claiming ``exact`` for
reflection/monkeypatch, or silently ignoring ``runtime_trace`` boosts.
"""

from __future__ import annotations

from .enums import CallConfidence

# Cross-language edges never claim EXACT — parsers disagree on identity.
_CROSS_LANGUAGE_CAP = {
    CallConfidence.EXACT: CallConfidence.PROBABLE,
    CallConfidence.PROBABLE: CallConfidence.PROBABLE,
    CallConfidence.AMBIGUOUS: CallConfidence.AMBIGUOUS,
    CallConfidence.UNRESOLVED: CallConfidence.UNRESOLVED,
    CallConfidence.EXTERNAL: CallConfidence.EXTERNAL,
}

# Package-manifest rewrites are probable unless already weaker.
_VIA_PACKAGE_MANIFEST_CAP = {
    CallConfidence.EXACT: CallConfidence.PROBABLE,
    CallConfidence.PROBABLE: CallConfidence.PROBABLE,
    CallConfidence.AMBIGUOUS: CallConfidence.AMBIGUOUS,
    CallConfidence.UNRESOLVED: CallConfidence.UNRESOLVED,
    CallConfidence.EXTERNAL: CallConfidence.EXTERNAL,
}

# DI / framework / dynamic-dispatch heuristics stay at probable max.
_VIA_DI_CAP = {
    CallConfidence.EXACT: CallConfidence.PROBABLE,
    CallConfidence.PROBABLE: CallConfidence.PROBABLE,
    CallConfidence.AMBIGUOUS: CallConfidence.AMBIGUOUS,
    CallConfidence.UNRESOLVED: CallConfidence.UNRESOLVED,
    CallConfidence.EXTERNAL: CallConfidence.EXTERNAL,
}

# Reflection / monkeypatch never rise above ambiguous.
_VIA_REFLECTION_CAP = {
    CallConfidence.EXACT: CallConfidence.AMBIGUOUS,
    CallConfidence.PROBABLE: CallConfidence.AMBIGUOUS,
    CallConfidence.AMBIGUOUS: CallConfidence.AMBIGUOUS,
    CallConfidence.UNRESOLVED: CallConfidence.UNRESOLVED,
    CallConfidence.EXTERNAL: CallConfidence.EXTERNAL,
}

_RANK: dict[CallConfidence, int] = {
    CallConfidence.UNRESOLVED: 0,
    CallConfidence.EXTERNAL: 1,
    CallConfidence.AMBIGUOUS: 2,
    CallConfidence.PROBABLE: 3,
    CallConfidence.EXACT: 4,
}

# Ladder for runtime boost / contradiction demote (EXTERNAL handled separately).
_LADDER: tuple[CallConfidence, ...] = (
    CallConfidence.UNRESOLVED,
    CallConfidence.AMBIGUOUS,
    CallConfidence.PROBABLE,
    CallConfidence.EXACT,
)

# Evidence classes → maximum confidence after static resolution (before runtime boost).
EVIDENCE_CONFIDENCE_CAP: dict[str, CallConfidence] = {
    "exact": CallConfidence.EXACT,
    "ambiguous": CallConfidence.AMBIGUOUS,
    "di": CallConfidence.PROBABLE,
    "dynamic": CallConfidence.PROBABLE,
    "reflection": CallConfidence.AMBIGUOUS,
    "monkeypatch": CallConfidence.AMBIGUOUS,
    "monkey_patch": CallConfidence.AMBIGUOUS,
    "unresolved": CallConfidence.UNRESOLVED,
    "runtime_trace": CallConfidence.EXACT,
}

# Default impact floor: probable+ (exact / probable / runtime-boosted).
DEFAULT_IMPACT_MIN_CONFIDENCE = CallConfidence.PROBABLE.value

_PACKAGE_VIA = frozenset(
    {"package_manifest", "package_alias", "tsconfig_paths", "cargo", "go_replace"}
)
_DI_VIA = frozenset({"di_injection", "framework_route", "dynamic_dispatch", "di", "dynamic"})
_REFLECTION_VIA = frozenset({"reflection", "monkeypatch", "monkey_patch"})
_RUNTIME_VIA = frozenset({"runtime_trace", "runtime_observed"})


def parse_call_confidence(
    value: CallConfidence | str | None,
    *,
    default: CallConfidence = CallConfidence.EXACT,
) -> CallConfidence:
    """Hydrate store/API confidence into ``CallConfidence``.

    Missing/null/blank → ``default`` (``GraphEdge`` default is exact).
    Unknown tokens → ``probable`` (same as Neo4j pathfinder fallback).
    """
    if isinstance(value, CallConfidence):
        return value
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return CallConfidence(text)
    except ValueError:
        return CallConfidence.PROBABLE


def confidence_rank(value: CallConfidence | str | None) -> int:
    if isinstance(value, CallConfidence):
        return _RANK.get(value, 0)
    if value is None:
        return 0
    try:
        return _RANK.get(CallConfidence(str(value)), 0)
    except ValueError:
        return 0


def boost_confidence(confidence: CallConfidence) -> CallConfidence:
    """Raise confidence one step toward EXACT (runtime confirmation)."""
    if confidence == CallConfidence.EXTERNAL:
        # Observed external keep external identity but gain probable weight for ranking.
        return CallConfidence.PROBABLE
    try:
        idx = _LADDER.index(confidence)
    except ValueError:
        return confidence
    if idx >= len(_LADDER) - 1:
        return CallConfidence.EXACT
    return _LADDER[idx + 1]


def demote_confidence(confidence: CallConfidence) -> CallConfidence:
    """Lower confidence one step (static edge contradicted by runtime)."""
    if confidence == CallConfidence.EXTERNAL:
        return CallConfidence.EXTERNAL
    try:
        idx = _LADDER.index(confidence)
    except ValueError:
        return CallConfidence.UNRESOLVED
    if idx <= 0:
        return CallConfidence.UNRESOLVED
    return _LADDER[idx - 1]


def clamp_confidence(
    confidence: CallConfidence,
    *,
    source_language: str = "",
    target_language: str = "",
    via: str = "",
) -> CallConfidence:
    """Apply language / resolution-path caps; ``runtime_trace`` boosts instead of capping."""
    result = confidence
    src = (source_language or "").strip().lower()
    tgt = (target_language or "").strip().lower()
    if src and tgt and src != tgt:
        result = _CROSS_LANGUAGE_CAP.get(result, result)
    via_key = (via or "").strip().lower().replace("-", "_")
    if via_key in _PACKAGE_VIA:
        result = _VIA_PACKAGE_MANIFEST_CAP.get(result, result)
    if via_key in _DI_VIA:
        result = _VIA_DI_CAP.get(result, result)
    if via_key in _REFLECTION_VIA:
        result = _VIA_REFLECTION_CAP.get(result, result)
    if via_key in _RUNTIME_VIA:
        result = boost_confidence(result)
    return result


def confidence_for_evidence(evidence_class: str) -> CallConfidence:
    """Return the policy cap for a named evidence class (see operating standard)."""
    key = (evidence_class or "").strip().lower().replace("-", "_")
    return EVIDENCE_CONFIDENCE_CAP.get(key, CallConfidence.UNRESOLVED)


def impact_eligible(
    confidence: CallConfidence | str,
    *,
    min_confidence: str | CallConfidence | None = DEFAULT_IMPACT_MIN_CONFIDENCE,
) -> bool:
    """Whether an edge may participate in directed impact / caller ranking."""
    if min_confidence is None:
        return True
    floor = (
        min_confidence.value
        if isinstance(min_confidence, CallConfidence)
        else str(min_confidence)
    )
    return confidence_rank(confidence) >= confidence_rank(floor)
