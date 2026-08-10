"""Backward-compatible facade for common-context domain and service.

Prefer importing from the focused modules (`errors`, `scope`, `service`, `ports`).
This module re-exports the historical public surface used by API, stores, and tests.
"""

from __future__ import annotations

from .constants import (
    DEFAULT_ALWAYS_RULES_BUDGET,
    DEFAULT_ENTRY_BUDGET,
    DEFAULT_SKILL_CATALOG_BUDGET,
    GUIDANCE_KINDS,
    ITEM_TYPES,
    LAYER_RANK,
    ORG_PROJECT_SENTINEL,
    SCOPE_KINDS,
    USER_PROJECT_PREFIX,
)
from .errors import CommonContextError, ConflictError, NotFoundError, ValidationError
from .ports import Store
from .scope import Scope, org_scope, project_scope, resolve_authoring_scope, user_scope
from .service import CommonContextService
from .util import (
    item_layer,
    merge_by_key,
    new_id,
    normalize_task_overrides,
    now_iso,
    rule_key,
    skill_key,
    token_estimate,
)

# Historical private names kept for any in-tree callers that imported them from core.
_now = now_iso
_new_id = new_id
_token_estimate = token_estimate
_item_layer = item_layer
_rule_key = rule_key
_skill_key = skill_key
_normalize_task_overrides = normalize_task_overrides
_merge_by_key = merge_by_key

__all__ = [
    "CommonContextError",
    "CommonContextService",
    "ConflictError",
    "DEFAULT_ALWAYS_RULES_BUDGET",
    "DEFAULT_ENTRY_BUDGET",
    "DEFAULT_SKILL_CATALOG_BUDGET",
    "GUIDANCE_KINDS",
    "ITEM_TYPES",
    "LAYER_RANK",
    "NotFoundError",
    "ORG_PROJECT_SENTINEL",
    "SCOPE_KINDS",
    "Scope",
    "Store",
    "USER_PROJECT_PREFIX",
    "ValidationError",
    "org_scope",
    "project_scope",
    "resolve_authoring_scope",
    "user_scope",
]
