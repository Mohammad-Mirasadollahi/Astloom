"""Migrate free-text / untyped CommonItems into AWG guidance kinds.

Role: propose (and optionally apply) item_type for guidance-shaped CommonItems.
SoT: explicit item_type when already set; heuristics never invent body content.
Invariants: known guidance kinds left unchanged; proposals are deterministic.
Allowed failure: skip rows that cannot be classified.
Forbidden: silent overwrite of agents_entry/always_rule/skill with a different kind.
"""

from __future__ import annotations

from typing import Any

GUIDANCE_KINDS = frozenset({"agents_entry", "always_rule", "skill"})


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def propose_guidance_kind(item: dict[str, Any]) -> str | None:
    """Return a guidance kind for an untyped item, or None if not guidance-shaped."""
    current = _norm(item.get("item_type") or item.get("kind"))
    if current in GUIDANCE_KINDS:
        return current

    slug = _norm(item.get("slug") or item.get("name") or item.get("title"))
    tags = {_norm(t) for t in (item.get("tags") or []) if str(t).strip()}
    path_hint = _norm(item.get("path") or item.get("export_path") or "")

    if "agents_entry" in tags or slug in {"agents-entry", "agents_entry", "agent-entry"}:
        return "agents_entry"
    if path_hint.endswith("agents.md") or path_hint.endswith("claude.md"):
        return "agents_entry"
    if "always_rule" in tags or "alwaysapply" in tags or slug.startswith("always-") or slug.startswith("always_"):
        return "always_rule"
    if path_hint.endswith(".mdc") or "/rules/" in path_hint:
        return "always_rule"
    if "skill" in tags or slug.startswith("skill-") or "/skills/" in path_hint or path_hint.endswith("skill.md"):
        return "skill"
    # Title heuristics (English product terms)
    title = _norm(item.get("title"))
    if title in {"agent entry", "agents entry"}:
        return "agents_entry"
    if "always-on" in title or title.endswith(" rule"):
        return "always_rule"
    if title.endswith(" skill") or title.startswith("astloom-"):
        return "skill"
    return None


def migrate_untyped_guidance_items(
    items: list[dict[str, Any]],
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Classify untyped items. When apply=True, set item_type on copies that change."""
    proposals: list[dict[str, Any]] = []
    unchanged = 0
    skipped = 0
    applied_items: list[dict[str, Any]] = []
    for raw in items:
        item = dict(raw)
        current = _norm(item.get("item_type") or item.get("kind"))
        if current in GUIDANCE_KINDS:
            unchanged += 1
            applied_items.append(item)
            continue
        kind = propose_guidance_kind(item)
        if kind is None:
            skipped += 1
            applied_items.append(item)
            continue
        proposals.append(
            {
                "id": item.get("id") or item.get("slug") or item.get("name"),
                "from": item.get("item_type") or item.get("kind") or None,
                "to": kind,
                "title": item.get("title"),
            }
        )
        if apply:
            item["item_type"] = kind
            item.pop("kind", None)
        applied_items.append(item)
    return {
        "proposals": proposals,
        "unchanged": unchanged,
        "skipped": skipped,
        "applied": apply,
        "items": applied_items if apply else items,
    }
