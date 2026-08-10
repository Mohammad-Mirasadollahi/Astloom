from __future__ import annotations

from typing import Any

from . import _paths  # noqa: F401 — side effect: service path bootstrap
from core_data_service.core import Kind

from .platform import PlatformBackends


def write_resource(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    resource = str(arguments.get("resource") or "").strip().lower()
    if resource not in {"memory", "task", "activity", "decision"}:
        raise ValueError("resource must be one of: memory, task, activity, decision")

    hint = None
    if not backends.guidance_was_resolved(scope):
        try:
            from architecture_governance import guidance_resolve_required

            if guidance_resolve_required():
                raise ValueError(
                    "astloom_guidance_resolve is required before durable writes "
                    "(ASTLOOM_GUIDANCE_RESOLVE_REQUIRED=1)"
                )
        except ImportError:
            pass
        hint = (
            "Prefer astloom_guidance_resolve (MCP-first) before durable writes "
            "so always-on rules and skills are loaded for this project."
        )

    if resource == "memory":
        result = _write_memory(backends, arguments, scope=scope, correlation_id=correlation_id, base=base)
    elif resource == "task":
        result = _write_task(backends, arguments, scope=scope, correlation_id=correlation_id, base=base)
    elif resource == "activity":
        result = _write_activity(backends, arguments, scope=scope, correlation_id=correlation_id, base=base)
    else:
        result = _write_decision(backends, arguments, scope=scope, correlation_id=correlation_id, base=base)
    if hint:
        result = {**result, "guidance_hint": hint}
    return result


def _write_memory(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    title = str(arguments.get("title") or "").strip()
    body = str(arguments.get("body") or "").strip()
    if not title or not body:
        raise ValueError("memory write requires title and body")
    tags = arguments.get("tags") if isinstance(arguments.get("tags"), list) else ["cursor", "mcp"]
    confidence = float(arguments.get("confidence") if arguments.get("confidence") is not None else 0.9)
    item = backends.memory.create_memory(
        backends.memory_scope(scope),
        backends.actor_id,
        correlation_id,
        f"mcp-write-memory:{correlation_id}",
        {
            "kind": "semantic",
            "state": "active",
            "title": title,
            "body": body,
            "tags": [str(tag) for tag in tags],
            "evidence_refs": [f"mcp:{correlation_id}"],
            "source_refs": ["cursor-mcp"],
            "confidence": confidence,
        },
    )
    return {**base, "written": "memory", "memory": item.public()}


def _write_task(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    title = str(arguments.get("title") or "").strip()
    if not title:
        raise ValueError("task write requires title")
    instructions = str(arguments.get("instructions") or arguments.get("body") or title).strip()
    record = backends.core.create(
        Kind.TASK,
        backends.core_scope(scope),
        backends.actor_id,
        correlation_id,
        f"mcp-write-task:{correlation_id}",
        {
            "title": title,
            "assignee_type": "backend",
            "instructions": instructions,
            "acceptance_criteria": ["Implemented", "Tests pass"],
        },
    )
    return {**base, "written": "task", "task": record.public()}


def _write_activity(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    summary = str(arguments.get("summary") or arguments.get("body") or arguments.get("title") or "").strip()
    if not summary:
        raise ValueError("activity write requires summary, body, or title")
    action_type = str(arguments.get("action_type") or "cursor_note").strip() or "cursor_note"
    record = backends.core.create(
        Kind.ACTIVITY,
        backends.core_scope(scope),
        backends.actor_id,
        correlation_id,
        f"mcp-write-activity:{correlation_id}",
        {
            "action_type": action_type,
            "action_summary": summary,
        },
    )
    return {**base, "written": "activity", "activity": record.public()}


def _write_decision(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    title = str(arguments.get("title") or "").strip()
    body = str(arguments.get("body") or "").strip()
    if not title or not body:
        raise ValueError("decision write requires title and body")
    record = backends.core.create(
        Kind.DECISION,
        backends.core_scope(scope),
        backends.actor_id,
        correlation_id,
        f"mcp-write-decision:{correlation_id}",
        {
            "title": title,
            "context": body,
            "options_considered": ["adopt", "defer"],
            "chosen_option": "adopt",
            "consequences": body,
            "owner": backends.actor_id,
        },
    )
    return {**base, "written": "decision", "decision": record.public()}
