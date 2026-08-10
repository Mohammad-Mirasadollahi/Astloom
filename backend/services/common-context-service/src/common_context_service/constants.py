"""Shared constants for common-context guidance and scoring."""

from __future__ import annotations

GUIDANCE_KINDS = frozenset({"agents_entry", "always_rule", "skill"})
ITEM_TYPES = GUIDANCE_KINDS | frozenset({"general"})
SCOPE_KINDS = frozenset({"org", "project", "user"})
ORG_PROJECT_SENTINEL = "__org__"
USER_PROJECT_PREFIX = "__user__:"
LAYER_RANK = {"org": 1, "project": 2, "user": 3}

DEFAULT_ENTRY_BUDGET = 2000
DEFAULT_ALWAYS_RULES_BUDGET = 1500
DEFAULT_SKILL_CATALOG_BUDGET = 800
