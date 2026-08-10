"""Small helpers for ids, token estimates, and layered merges."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .constants import LAYER_RANK
from .errors import ValidationError


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def token_estimate(text: str) -> int:
    return max(20, len(text) // 4)


def item_layer(item: dict[str, Any]) -> str:
    return str(item.get("scope_kind") or "project")


def rule_key(item: dict[str, Any]) -> str:
    slug = str(item.get("slug") or "").strip()
    if slug:
        return f"slug:{slug}"
    return f"id:{item['id']}"


def skill_key(item: dict[str, Any]) -> str:
    return str(item.get("name") or "").strip()


def normalize_task_overrides(raw: dict[str, Any] | None) -> dict[str, set[str]]:
    if raw is None:
        return {"suppress_rule_slugs": set(), "suppress_skill_names": set()}
    if not isinstance(raw, dict):
        raise ValidationError("task_overrides must be an object")
    slugs = raw.get("suppress_rule_slugs") or []
    names = raw.get("suppress_skill_names") or []
    if not isinstance(slugs, list) or not isinstance(names, list):
        raise ValidationError("suppress_rule_slugs and suppress_skill_names must be lists")
    return {
        "suppress_rule_slugs": {str(x).strip() for x in slugs if str(x).strip()},
        "suppress_skill_names": {str(x).strip() for x in names if str(x).strip()},
    }


def merge_by_key(
    layered: list[tuple[str, dict[str, Any]]],
    *,
    key_fn,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge items low→high rank. Higher replaces lower unless lower is mandatory with different body."""
    winners: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    ordered = sorted(layered, key=lambda pair: (LAYER_RANK.get(pair[0], 0), pair[1]["id"]))
    for layer, item in ordered:
        tagged = {**item, "scope_kind": layer}
        key = key_fn(tagged)
        if not key:
            winners[f"anon:{tagged['id']}"] = tagged
            continue
        existing = winners.get(key)
        if existing is None:
            winners[key] = tagged
            continue
        if existing.get("body") == tagged.get("body") and existing.get("id") == tagged.get("id"):
            winners[key] = tagged
            continue
        if bool(existing.get("mandatory")) and existing.get("body") != tagged.get("body"):
            conflicts.append(
                {
                    "reason_code": "mandatory_override_blocked",
                    "key": key,
                    "kept_item_id": existing["id"],
                    "blocked_item_id": tagged["id"],
                    "kept_layer": item_layer(existing),
                    "blocked_layer": layer,
                }
            )
            continue
        winners[key] = tagged
    return list(winners.values()), conflicts
