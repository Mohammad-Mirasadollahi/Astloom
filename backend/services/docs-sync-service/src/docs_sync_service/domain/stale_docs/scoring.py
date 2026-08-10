"""Numeric confidence and evidence for stale-documentation candidates.

Role: Score orphan/ghost/stale-anchor/superseded findings; never invent
safe_to_delete for normative-current docs.
Source of truth: docs/07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md
Allowed: monotonic score decreases via caps; attach evidence; classify tiers.
Forbidden: raising confidence from embeddings alone; Astloom never deletes Markdown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


TIER_HIGH = 0.80
TIER_MEDIUM = 0.50
RECENT_DOC_DAYS = 14


@dataclass(frozen=True)
class Evidence:
    kind: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "detail": self.detail}


@dataclass
class ScoreInput:
    finding_kind: str
    authority: str = ""
    lifecycle_lane: str = ""
    blockers: list[str] = field(default_factory=list)
    freshness: str = "ok"
    days_since_touch: float | None = None
    all_links_missing: bool = False
    ghost_majority: bool = False
    has_stale_anchors: bool = False
    no_documented_by: bool = True


@dataclass(frozen=True)
class ScoreResult:
    score: float
    tier: str
    evidence: tuple[Evidence, ...]
    blockers: tuple[str, ...]
    safe_to_delete: bool
    safe_to_unlink: bool
    safe_to_update: bool


def _tier(score: float) -> str:
    if score >= TIER_HIGH:
        return "high"
    if score >= TIER_MEDIUM:
        return "medium"
    return "low"


def _parse_days_since(updated_at: str | None) -> float | None:
    raw = (updated_at or "").strip()
    if not raw:
        return None
    try:
        # Accept YYYY-MM-DD or ISO timestamps.
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            dt = datetime(int(raw[0:4]), int(raw[5:7]), int(raw[8:10]), tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 86400.0)
    except (TypeError, ValueError):
        return None


def days_since_doc_touch(*, updated_at: str | None = None, frontmatter: dict[str, Any] | None = None) -> float | None:
    fm = frontmatter or {}
    return _parse_days_since(str(fm.get("updated_at") or updated_at or "") or None)


def score_candidate(inp: ScoreInput) -> ScoreResult:
    """Monotonic scorer — scores only decrease via caps (doc 78)."""
    evidence: list[Evidence] = []
    blockers = list(dict.fromkeys(inp.blockers))
    kind = (inp.finding_kind or "").strip()

    # Base scores from normative table.
    if kind == "coverage_gap":
        score = 0.55
        evidence.append(Evidence("coverage_gap", "doc_required without human layer"))
    elif kind == "stale_anchor":
        score = 0.65
        evidence.append(Evidence("anchor_hash_mismatch", "recorded_hash != symbol body_hash"))
    elif kind in {"superseded_retrieval_risk", "duplicate_authority"}:
        score = 0.70
        evidence.append(Evidence(kind, "retrieval or authority conflict"))
    elif kind == "wiki_orphan":
        score = 0.80
        evidence.append(Evidence("wiki_orphan", "wiki page without durable code anchors"))
    elif kind == "ghost_link" and inp.ghost_majority and inp.has_stale_anchors:
        score = 0.80
        evidence.append(Evidence("ghost_link_majority", "majority of linked symbols missing"))
        evidence.append(Evidence("anchor_hash_mismatch", "anchors also hash-stale"))
    elif kind == "ghost_link":
        score = 0.80
        evidence.append(Evidence("ghost_link", "one or more linked symbols unresolved"))
    elif kind == "orphan_doc":
        score = 0.90
        evidence.append(Evidence("orphan_doc", "no DOCUMENTED_BY / resolvable links"))
    else:
        score = 0.50
        evidence.append(Evidence("unknown_finding_kind", kind))

    authority = (inp.authority or "").strip().lower()
    lifecycle = (inp.lifecycle_lane or "").strip().lower()
    normative_current = authority == "normative" and lifecycle == "current"

    # Caps (only decrease).
    if normative_current and kind not in {"orphan_doc", "ghost_link"}:
        if score > 0.55:
            score = 0.55
            blockers = list(dict.fromkeys([*blockers, "normative_current_cap"]))
            evidence.append(Evidence("normative_current_cap", "score capped at 0.55"))
    elif normative_current and kind in {"orphan_doc", "ghost_link"}:
        # Fully proven ghost/orphan may stay high for unlink, but delete still blocked below.
        pass

    if inp.days_since_touch is not None and inp.days_since_touch <= RECENT_DOC_DAYS:
        if score > 0.55:
            score = 0.55
        blockers = list(dict.fromkeys([*blockers, "recent_doc_cap"]))
        evidence.append(Evidence("recent_doc_cap", f"days_since_touch={inp.days_since_touch:.1f}"))

    if inp.freshness in {"stale", "pending_sync"}:
        blockers = list(dict.fromkeys([*blockers, f"freshness_{inp.freshness}"]))
        if score > 0.55:
            score = 0.55

    score = max(0.0, min(1.0, round(score, 4)))

    safe_to_update = kind in {"stale_anchor", "wiki_orphan", "duplicate_authority"} and (
        "freshness_pending_sync" not in blockers
    )
    safe_to_unlink = kind == "ghost_link" and not any(
        b.startswith("freshness_") for b in blockers
    )
    # Delete only when orphan/ghost fully proven and not normative-current.
    # wiki_orphan / duplicate_authority: remediate (link/split), never auto-delete.
    safe_to_delete = (
        kind in {"orphan_doc", "ghost_link"}
        and inp.all_links_missing
        and inp.no_documented_by
        and not normative_current
        and not blockers
        and score >= TIER_HIGH
    )
    if kind in {"wiki_orphan", "duplicate_authority"}:
        safe_to_delete = False
        if kind == "duplicate_authority" and "needs_human_task" not in blockers:
            blockers = list(dict.fromkeys([*blockers, "needs_human_task"]))
    if normative_current:
        safe_to_delete = False
        if "needs_human_task" not in blockers and kind in {
            "orphan_doc",
            "ghost_link",
            "wiki_orphan",
            "duplicate_authority",
        }:
            blockers = list(dict.fromkeys([*blockers, "needs_human_task"]))

    if blockers and safe_to_delete:
        safe_to_delete = False

    return ScoreResult(
        score=score,
        tier=_tier(score),
        evidence=tuple(evidence),
        blockers=tuple(blockers),
        safe_to_delete=safe_to_delete,
        safe_to_unlink=safe_to_unlink and not normative_current,
        safe_to_update=safe_to_update,
    )
