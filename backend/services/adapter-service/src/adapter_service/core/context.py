from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from .constants import CLEARANCE_RANK, DEPARTMENT_TRIGGERS
from .helpers import now, sanitize
from .errors import ValidationError
from .models import DepartmentTask, Scope


class ContextCommands:
    def list_department_tasks(self, scope: Scope) -> list[DepartmentTask]:
        return self.store.list_department_tasks(scope)
    
    def inject_context(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Build a scoped context package for an external tool, or deny with a reason code."""
        self._require_key(key)
        payload = sanitize(payload)
        tool_ref = str(payload.get("tool_ref") or "").strip()
        if not tool_ref:
            raise ValidationError("tool_ref is required")
        clearance = str(payload.get("sensitivity_clearance") or "public")
        if clearance not in CLEARANCE_RANK:
            raise ValidationError("invalid sensitivity_clearance")
        command_payload = {
            "tool_ref": tool_ref,
            "role": str(payload.get("role") or "tool"),
            "sensitivity_clearance": clearance,
            "task_assigned": bool(payload.get("task_assigned", True)),
            "tenant_id": payload.get("tenant_id"),
            "project_id": payload.get("project_id"),
            "items": payload.get("items") or [],
        }
        prior = self.store.idempotent(scope, "inject_context", key, command_payload)
        if prior:
            return json.loads(prior)
        if command_payload["tenant_id"] and command_payload["tenant_id"] != scope.tenant_id:
            result = {"status": "denied", "reason_code": "tenant_mismatch", "package": None}
            self.store.remember(scope, "inject_context", key, command_payload, json.dumps(result, sort_keys=True))
            return result
        if command_payload["project_id"] and command_payload["project_id"] != scope.project_id:
            result = {"status": "denied", "reason_code": "project_mismatch", "package": None}
            self.store.remember(scope, "inject_context", key, command_payload, json.dumps(result, sort_keys=True))
            return result
        if not command_payload["task_assigned"] and command_payload["role"] != "admin":
            result = {"status": "denied", "reason_code": "task_assignment_required", "package": None}
            self.store.remember(scope, "inject_context", key, command_payload, json.dumps(result, sort_keys=True))
            return result
        package_items: list[dict[str, Any]] = []
        for item in command_payload["items"]:
            if not isinstance(item, dict):
                raise ValidationError("context items must be objects")
            sensitivity = str(item.get("sensitivity") or "public")
            if sensitivity not in CLEARANCE_RANK:
                raise ValidationError("invalid item sensitivity")
            if CLEARANCE_RANK[sensitivity] > CLEARANCE_RANK[clearance]:
                package_items.append(
                    {
                        "title": str(item.get("title") or ""),
                        "body": "[REDACTED]",
                        "sensitivity": sensitivity,
                        "redacted": True,
                    }
                )
            else:
                package_items.append(
                    {
                        "title": str(item.get("title") or ""),
                        "body": str(item.get("body") or ""),
                        "sensitivity": sensitivity,
                        "redacted": False,
                    }
                )
        result = {
            "status": "allowed",
            "reason_code": None,
            "package": {
                "tool_ref": tool_ref,
                "tenant_id": scope.tenant_id,
                "project_id": scope.project_id,
                "actor_id": actor,
                "correlation_id": correlation_id,
                "items": package_items,
            },
        }
        self.store.remember(scope, "inject_context", key, command_payload, json.dumps(result, sort_keys=True))
        return result
    
    def _trigger_department_workflows(self, scope: Scope, message: dict[str, Any], event_id: str) -> list[DepartmentTask]:
        departments = DEPARTMENT_TRIGGERS.get(message["intent"], ())
        tasks: list[DepartmentTask] = []
        for department in departments:
            task = DepartmentTask(
                str(uuid4()),
                scope,
                department,
                f"{department} follow-up for {message['intent']}",
                message["intent"],
                message["message_id"],
                department in {"marketing", "support", "devops"},
                "open",
                now(),
            )
            self.store.put_department_task(task)
            self.emit(
                "DepartmentTaskCreated",
                {**task.public(), "source_event_id": event_id},
                scope,
                "system",
                message.get("correlation_id") or "",
                "",
                task.id,
                message.get("refs") or [],
            )
            tasks.append(task)
        return tasks
