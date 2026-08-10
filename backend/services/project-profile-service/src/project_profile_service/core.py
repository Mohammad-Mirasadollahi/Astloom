from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any, Protocol
from uuid import uuid4

_PACKAGES = Path(__file__).resolve().parents[4] / "packages"
if str(_PACKAGES) not in sys.path:
    sys.path.insert(0, str(_PACKAGES))

from usage_profile import (  # noqa: E402
    UsageProfileError,
    list_profile_ids,
    load_usage_profile,
    materialize_cursor_mcp_config,
    resolve_effective_profile,
)
from usage_profile.mcp_tokens import mint_connect_token  # noqa: E402


class ProjectProfileError(Exception):
    def __init__(self, code: str, category: str, message: str):
        super().__init__(message)
        self.code, self.category, self.message = code, category, message


class ValidationError(ProjectProfileError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class ConflictError(ProjectProfileError):
    def __init__(self, message: str):
        super().__init__("conflict_error", "conflict_error", message)


class NotFoundError(ProjectProfileError):
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
    def put_project(self, project: dict[str, Any]) -> None: ...
    def get_project(self, project_id: str, scope: Scope) -> dict[str, Any]: ...
    def put_group(self, group: dict[str, Any]) -> None: ...
    def get_group(self, group_id: str, tenant_id: str, workspace_id: str) -> dict[str, Any]: ...


class ProjectProfileService:
    def __init__(self, store: Store):
        self.store = store

    def register_project(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        domain_pack = str(payload.get("domain_pack") or "default").strip()
        feature_profile = str(payload.get("feature_profile") or "default").strip()
        usage_profile = str(payload.get("usage_profile") or "programming-cursor-mcp").strip()
        if not name:
            raise ValidationError("name is required")
        role_list = [str(r) for r in (payload.get("actor_roles") or [])]
        perm_list = [str(p) for p in (payload.get("actor_permissions") or [])]
        enforce = str(__import__("os").environ.get("ASTLOOM_ENFORCE_ADMIN_MATRIX", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if enforce or role_list or perm_list:
            try:
                from architecture_governance import admin_action_allowed

                if not admin_action_allowed(
                    "project.create",
                    roles=role_list,
                    permissions=perm_list,
                ):
                    raise ValidationError("project.create denied by admin permission matrix")
            except ImportError as exc:
                raise ValidationError(
                    "project.create requires architecture_governance when "
                    "ASTLOOM_ENFORCE_ADMIN_MATRIX is enabled or actor roles/permissions "
                    "are supplied"
                ) from exc
        try:
            catalog = load_usage_profile(usage_profile)
        except UsageProfileError as exc:
            raise ValidationError(str(exc)) from exc
        if not payload.get("domain_pack"):
            domain_pack = str(catalog["domain_pack"])
        if not payload.get("feature_profile"):
            feature_profile = str(catalog["feature_profile"])
        existing = self.store.begin_idempotency(scope, idempotency_key, "project")
        if existing:
            return self.store.get_project(existing, scope)
        project = {
            "id": scope.project_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "name": name,
            "domain_pack": domain_pack,
            "feature_profile": feature_profile,
            "usage_profile": usage_profile,
            "project_group_id": payload.get("project_group_id"),
            "isolation": "strict",
            "created_by": actor_id,
            "correlation_id": correlation_id,
            "created_at": _now(),
            "status": "active",
        }
        self.store.put_project(project)
        self.store.complete_idempotency(scope, idempotency_key, "project", scope.project_id)
        self.store.append_event({"event_type": "project.registered", "project_id": scope.project_id})
        return project

    def create_project_group(
        self,
        tenant_id: str,
        workspace_id: str,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        if not name or not tenant_id.strip() or not workspace_id.strip():
            raise ValidationError("name, tenant_id, and workspace_id are required")
        scope = Scope(tenant_id, workspace_id, "_groups")
        existing = self.store.begin_idempotency(scope, idempotency_key, "project_group")
        if existing:
            return self.store.get_group(existing, tenant_id, workspace_id)
        group_id = _new_id("pg")
        group = {
            "id": group_id,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "name": name,
            "share_policy": str(payload.get("share_policy") or "explicit_opt_in"),
            "member_project_ids": [str(p) for p in (payload.get("member_project_ids") or [])],
            "created_by": actor_id,
            "correlation_id": correlation_id,
            "created_at": _now(),
        }
        self.store.put_group(group)
        self.store.complete_idempotency(scope, idempotency_key, "project_group", group_id)
        self.store.append_event({"event_type": "project_group.created", "group_id": group_id})
        return group

    def get_project(self, scope: Scope) -> dict[str, Any]:
        return self.store.get_project(scope.project_id, scope)

    def update_feature_profile(
        self,
        scope: Scope,
        actor_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        project = self.store.get_project(scope.project_id, scope)
        domain_pack = payload.get("domain_pack")
        feature_profile = payload.get("feature_profile")
        usage_profile = payload.get("usage_profile")
        if domain_pack is None and feature_profile is None and usage_profile is None:
            raise ValidationError("domain_pack, feature_profile, or usage_profile is required")
        if domain_pack is not None:
            value = str(domain_pack).strip()
            if not value:
                raise ValidationError("domain_pack cannot be empty")
            project["domain_pack"] = value
        if feature_profile is not None:
            value = str(feature_profile).strip()
            if not value:
                raise ValidationError("feature_profile cannot be empty")
            project["feature_profile"] = value
        if usage_profile is not None:
            value = str(usage_profile).strip()
            if not value:
                raise ValidationError("usage_profile cannot be empty")
            try:
                catalog = load_usage_profile(value)
            except UsageProfileError as exc:
                raise ValidationError(str(exc)) from exc
            project["usage_profile"] = value
            if domain_pack is None:
                project["domain_pack"] = str(catalog["domain_pack"])
            if feature_profile is None:
                project["feature_profile"] = str(catalog["feature_profile"])
        project["updated_by"] = actor_id
        project["updated_at"] = _now()
        self.store.put_project(project)
        self.store.append_event(
            {
                "event_type": "project.profile_updated",
                "project_id": scope.project_id,
                "domain_pack": project["domain_pack"],
                "feature_profile": project["feature_profile"],
                "usage_profile": project.get("usage_profile"),
            }
        )
        return project

    def activate_usage_profile(
        self,
        scope: Scope,
        actor_id: str,
        usage_profile_id: str,
        *,
        apply_catalog_defaults: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"usage_profile": usage_profile_id}
        if not apply_catalog_defaults:
            project = self.store.get_project(scope.project_id, scope)
            payload["domain_pack"] = project["domain_pack"]
            payload["feature_profile"] = project["feature_profile"]
        return self.update_feature_profile(scope, actor_id, payload)

    def list_usage_profiles(self) -> list[str]:
        return list_profile_ids()

    def get_effective_usage_profile(self, scope: Scope) -> dict[str, Any]:
        project = self.store.get_project(scope.project_id, scope)
        profile_id = str(project.get("usage_profile") or "programming-cursor-mcp")
        try:
            return resolve_effective_profile(
                profile_id,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
                overrides={
                    "domain_pack": project.get("domain_pack"),
                    "feature_profile": project.get("feature_profile"),
                },
            )
        except UsageProfileError as exc:
            raise ValidationError(str(exc)) from exc

    def export_cursor_mcp_connection(self, scope: Scope) -> dict[str, Any]:
        effective = self.get_effective_usage_profile(scope)
        fragment = materialize_cursor_mcp_config(effective)
        return {
            "usage_profile": effective["profile_id"],
            "effective": effective,
            "cursor_mcp": fragment,
            "instructions": [
                "Merge cursor_mcp.mcpServers into your Cursor MCP settings (mcp.json).",
                "Ensure PYTHONPATH includes backend/services/mcp-gateway-service/src and backend/packages.",
                "Reload Cursor MCP / window after saving.",
            ],
        }

    def register_code_source(self, scope: Scope, actor_id: str, body: dict[str, Any]) -> dict[str, Any]:
        project = self.get_project(scope)
        server_path = str(body.get("server_path") or "").strip() or None
        git = body.get("git") if isinstance(body.get("git"), dict) else None
        if not server_path and not git:
            raise ValidationError("server_path or git is required")
        code_source: dict[str, Any] = {"updated_by": actor_id, "updated_at": _now()}
        if server_path:
            code_source["server_path"] = server_path
        if git:
            remote = str(git.get("remote") or "").strip()
            branch = str(git.get("branch") or "main").strip()
            if not remote:
                raise ValidationError("git.remote is required")
            code_source["git"] = {"remote": remote, "branch": branch}
        project["code_source"] = code_source
        self.store.put_project(project)
        self.store.append_event(
            {"event_type": "project.code_source.registered", "project_id": scope.project_id}
        )
        return project

    def connect_status(self, scope: Scope) -> dict[str, Any]:
        project = self.get_project(scope)
        effective = self.get_effective_usage_profile(scope)
        return {
            "scope": {
                "tenant_id": scope.tenant_id,
                "workspace_id": scope.workspace_id,
                "project_id": scope.project_id,
            },
            "usage_profile": effective["profile_id"],
            "code_source": project.get("code_source"),
            "ingest": project.get("ingest") or {"status": "unknown"},
        }

    def request_ingest(self, scope: Scope, actor_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Mark ingest requested; optionally run local graph ingest when ASTLOOM_ROOT is set."""
        import os
        import subprocess

        project = self.get_project(scope)
        body = body or {}
        source_path = str(body.get("source_path") or "").strip()
        if not source_path:
            code_source = project.get("code_source") or {}
            source_path = str(code_source.get("server_path") or "").strip()
        if not source_path:
            raise ValidationError("source_path or registered code_source.server_path is required")
        ingest: dict[str, Any] = {
            "status": "deferred",
            "source_path": source_path,
            "requested_by": actor_id,
            "requested_at": _now(),
        }
        root = os.environ.get("ASTLOOM_ROOT", "").strip()
        astloom = Path(root) / ".venv" / "bin" / "astloom" if root else None
        if astloom and astloom.is_file():
            proc = subprocess.run(
                [
                    str(astloom),
                    "graph",
                    "ingest",
                    "--tenant",
                    scope.tenant_id,
                    "--workspace",
                    scope.workspace_id,
                    "--project",
                    scope.project_id,
                    "--path",
                    source_path,
                ],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            ingest["status"] = "ok" if proc.returncode == 0 else "failed"
            ingest["exit_code"] = proc.returncode
            if proc.returncode != 0:
                ingest["stderr"] = (proc.stderr or "")[:2000]
        else:
            ingest["hint"] = "Run astloom graph ingest on the Astloom host for this path."
        project["ingest"] = ingest
        self.store.put_project(project)
        self.store.append_event({"event_type": "project.ingest.requested", "project_id": scope.project_id})
        return {"project": project, "ingest": ingest}

    def connect_bootstrap(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        import os

        usage_profile = str(body.get("usage_profile") or "programming-cursor-mcp").strip()
        name = str(body.get("name") or scope.project_id).strip()
        source_path = str(body.get("source_path") or "").strip() or None
        git = body.get("git") if isinstance(body.get("git"), dict) else None
        try:
            self.get_project(scope)
        except NotFoundError:
            self.register_project(
                scope,
                actor_id,
                correlation_id,
                idempotency_key,
                {"name": name, "usage_profile": usage_profile},
            )
        project = self.activate_usage_profile(scope, actor_id, usage_profile)
        if source_path or git:
            project = self.register_code_source(
                scope,
                actor_id,
                {"server_path": source_path, "git": git} if git else {"server_path": source_path},
            )
        exported = self.export_cursor_mcp_connection(scope)
        mcp_http_url = (
            str(body.get("mcp_http_url") or "").strip()
            or os.environ.get("ASTLOOM_MCP_HTTP_PUBLIC_URL", "").strip()
        )
        mcp_block: dict[str, Any] = {
            "transport": "stdio",
            "url": None,
            "headers": {},
            "note": "Set server.mcp_http_url for Streamable HTTP MCP; stdio has no remote fallback.",
        }
        if mcp_http_url:
            mcp_block["transport"] = "streamable_http"
            mcp_block["url"] = mcp_http_url.rstrip("/") + (
                "" if mcp_http_url.rstrip("/").endswith("/mcp") else "/mcp"
            )
            token = ""
            try:
                token = mint_connect_token(
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                )
            except ValueError:
                token = os.environ.get("ASTLOOM_MCP_HTTP_TOKEN", "").strip()
            if token:
                mcp_block["headers"] = {
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-Id": scope.tenant_id,
                    "X-Workspace-Id": scope.workspace_id,
                    "X-Project-Id": scope.project_id,
                    "X-Usage-Profile": usage_profile,
                }
            mcp_block["note"] = "Prefer HTTP MCP; stdio fallback is for agents without HTTP support."
        ingest: dict[str, Any] = {"status": "skipped", "source_path": source_path}
        if source_path:
            ingest = {
                "status": "registered",
                "source_path": source_path,
                "hint": "POST .../connect/ingest or astloom connect with ingest enabled.",
            }
        return {
            "scope": {
                "tenant_id": scope.tenant_id,
                "workspace_id": scope.workspace_id,
                "project_id": scope.project_id,
            },
            "usage_profile": exported["usage_profile"],
            "project": project,
            "mcp": mcp_block,
            "mcp_stdio_fallback": exported["cursor_mcp"],
            "ingest": ingest,
        }
