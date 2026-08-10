"""Authoring and resolve scopes for common-context items."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import ORG_PROJECT_SENTINEL, SCOPE_KINDS, USER_PROJECT_PREFIX
from .errors import ValidationError


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    workspace_id: str
    project_id: str
    scope_kind: str = "project"
    user_id: str | None = None

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.workspace_id.strip(), self.project_id.strip())):
            raise ValidationError("tenant_id, workspace_id, and project_id are required")
        kind = (self.scope_kind or "project").strip()
        if kind not in SCOPE_KINDS:
            raise ValidationError(f"scope_kind must be one of: {', '.join(sorted(SCOPE_KINDS))}")
        object.__setattr__(self, "scope_kind", kind)
        if kind == "user" and not (self.user_id or "").strip():
            raise ValidationError("user_id is required when scope_kind is user")


def org_scope(tenant_id: str, workspace_id: str) -> Scope:
    return Scope(tenant_id, workspace_id, ORG_PROJECT_SENTINEL, scope_kind="org")


def user_scope(tenant_id: str, workspace_id: str, user_id: str) -> Scope:
    uid = user_id.strip()
    return Scope(tenant_id, workspace_id, f"{USER_PROJECT_PREFIX}{uid}", scope_kind="user", user_id=uid)


def project_scope(tenant_id: str, workspace_id: str, project_id: str) -> Scope:
    return Scope(tenant_id, workspace_id, project_id, scope_kind="project")


def resolve_authoring_scope(
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    *,
    scope_kind: str = "project",
    user_id: str | None = None,
    actor_id: str | None = None,
) -> Scope:
    kind = (scope_kind or "project").strip() or "project"
    if kind == "org":
        return org_scope(tenant_id, workspace_id)
    if kind == "user":
        uid = (user_id or actor_id or "").strip()
        if not uid:
            raise ValidationError("user_id or actor_id is required for user scope_kind")
        return user_scope(tenant_id, workspace_id, uid)
    return project_scope(tenant_id, workspace_id, project_id)
