from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


class IdentityAccessError(Exception):
    def __init__(self, code: str, category: str, message: str):
        super().__init__(message)
        self.code, self.category, self.message = code, category, message


class ValidationError(IdentityAccessError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class ConflictError(IdentityAccessError):
    def __init__(self, message: str):
        super().__init__("conflict_error", "conflict_error", message)


class NotFoundError(IdentityAccessError):
    def __init__(self, message: str):
        super().__init__("not_found", "not_found_error", message)


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    workspace_id: str
    project_id: str

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.workspace_id.strip(), self.project_id.strip())):
            raise ValidationError("tenant_id, workspace_id, and project_id are required")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"

class Store(Protocol):
    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None: ...
    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None: ...
    def append_event(self, event: dict[str, Any]) -> None: ...
    def put_principal(self, principal: dict[str, Any]) -> None: ...
    def get_principal(self, principal_id: str, scope: Scope) -> dict[str, Any]: ...
    def list_principals(self, scope: Scope) -> list[dict[str, Any]]: ...


class IdentityAccessService:
    def __init__(self, store: Store):
        self.store = store

    def upsert_principal(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        subject = str(payload.get("subject") or "").strip()
        roles = payload.get("roles") or []
        if not subject:
            raise ValidationError("subject is required")
        if not isinstance(roles, list) or not roles:
            raise ValidationError("roles must be a non-empty list")
        existing = self.store.begin_idempotency(scope, idempotency_key, "principal")
        if existing:
            return self.store.get_principal(existing, scope)
        principal_id = _new_id("prn")
        principal = {
            "id": principal_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "subject": subject,
            "roles": [str(r) for r in roles],
            "permissions": [str(p) for p in (payload.get("permissions") or [])],
            "created_by": actor_id,
            "correlation_id": correlation_id,
            "created_at": _now(),
            "status": "active",
        }
        self.store.put_principal(principal)
        self.store.complete_idempotency(scope, idempotency_key, "principal", principal_id)
        self.store.append_event({"event_type": "principal.upserted", "principal_id": principal_id})
        return principal

    def authorize(self, scope: Scope, subject: str, action: str, resource: str) -> dict[str, Any]:
        if not all((subject.strip(), action.strip(), resource.strip())):
            raise ValidationError("subject, action, and resource are required")
        admin_actions = {
            "tenant.create",
            "project.create",
            "policy.approve",
            "weight_profile.change",
            "adapter.install",
        }

        def _audit(allowed: bool, principal_id: str | None) -> None:
            if action not in admin_actions:
                return
            self.store.append_event(
                {
                    "event_type": "admin.authorize",
                    "allowed": allowed,
                    "subject": subject,
                    "action": action,
                    "resource": resource,
                    "principal_id": principal_id,
                    "scope": {
                        "tenant_id": scope.tenant_id,
                        "workspace_id": scope.workspace_id,
                        "project_id": scope.project_id,
                    },
                }
            )

        for principal in self.store.list_principals(scope):
            if principal["subject"] != subject or principal.get("status") != "active":
                continue
            roles = set(principal.get("roles") or [])
            perms = set(principal.get("permissions") or [])
            allowed = "admin" in roles or action in perms or f"{action}:{resource}" in perms
            if not allowed and action in admin_actions:
                try:
                    from architecture_governance import admin_action_allowed

                    allowed = admin_action_allowed(
                        action,
                        roles=sorted(roles),
                        permissions=sorted(perms),
                    )
                except Exception:
                    allowed = False
            _audit(allowed, principal["id"])
            return {
                "allowed": allowed,
                "subject": subject,
                "action": action,
                "resource": resource,
                "principal_id": principal["id"],
                "matched_roles": sorted(roles),
            }
        _audit(False, None)
        return {
            "allowed": False,
            "subject": subject,
            "action": action,
            "resource": resource,
            "principal_id": None,
            "matched_roles": [],
        }

    def revoke_principal(self, scope: Scope, principal_id: str, actor_id: str) -> dict[str, Any]:
        principal = self.store.get_principal(principal_id, scope)
        if principal.get("status") == "revoked":
            return principal
        principal["status"] = "revoked"
        principal["revoked_by"] = actor_id
        principal["revoked_at"] = _now()
        self.store.put_principal(principal)
        self.store.append_event({"event_type": "principal.revoked", "principal_id": principal_id})
        return principal

    def list_principals(self, scope: Scope) -> list[dict[str, Any]]:
        return self.store.list_principals(scope)
