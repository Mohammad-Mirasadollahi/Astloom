from __future__ import annotations

from typing import Any

from . import _paths  # noqa: F401 — side effect: service path bootstrap
from . import backup, code_graph, context, docs, guidance, quality, writes
from core_data_service.core import Kind

from .platform import PlatformBackends


def dispatch_capability(
    backends: PlatformBackends,
    maps_to: str,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    usage_profile: str,
    correlation_id: str,
) -> dict[str, Any]:
    base = {
        "maps_to": maps_to,
        "usage_profile": usage_profile,
        "scope": scope,
        "correlation_id": correlation_id,
        "backend": "in_process",
        "store_mode": backends.store_mode,
        "graph_mode": backends.graph_mode,
    }
    if maps_to == "platform.ping":
        from astloom_cli.upgrade.versions import server_version_payload

        return {**base, "ok": True, **server_version_payload()}
    if maps_to == "profile.effective":
        return {**base, "ok": True}

    if maps_to == "memory.retrieve":
        return _memory_retrieve(backends, arguments, scope=scope, correlation_id=correlation_id, base=base)

    if maps_to == "context.compress":
        return context.context_compress(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )
    if maps_to == "context.retrieve":
        return context.context_retrieve(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )
    if maps_to == "context.stats":
        return context.context_stats(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )

    if maps_to == "code_graph.search":
        return code_graph.search(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.get_symbol":
        return code_graph.get_symbol(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.neighbors":
        return code_graph.neighbors(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.impact":
        return code_graph.impact(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.callers":
        return code_graph.callers(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.community":
        return code_graph.community(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.call_path":
        return code_graph.call_path(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.unused_candidates":
        return code_graph.unused_candidates(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.explore":
        return code_graph.explore(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.detect_changes":
        return code_graph.detect_changes(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.architecture_overview":
        return code_graph.architecture_overview(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.path":
        return code_graph.symbol_path(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.hybrid_search":
        return code_graph.hybrid_search(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.freshness":
        return code_graph.freshness(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.generation_context":
        return code_graph.generation_context(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.ingest_file":
        return code_graph.ingest_file(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )
    if maps_to == "code_graph.ingest_repo":
        return code_graph.ingest_repo(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )
    if maps_to == "code_graph.sync":
        return code_graph.sync_repo(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )
    if maps_to == "code_graph.purge":
        return code_graph.purge_scope(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.language_profile":
        return code_graph.language_profile(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.ide_references":
        return code_graph.ide_references(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.ide_definition":
        return code_graph.ide_definition(backends, arguments, scope=scope, base=base)
    if maps_to == "code_graph.ide_rename":
        return code_graph.ide_rename(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )
    if maps_to == "code_graph.reconcile_after_edit":
        return code_graph.reconcile_after_edit(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )

    if maps_to == "core_data.create_task":
        return _create_task(backends, arguments, scope=scope, correlation_id=correlation_id, base=base)

    if maps_to == "platform.write":
        return writes.write_resource(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )

    if maps_to == "docs_sync.drift_check":
        return docs.docs_drift_check(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )

    if maps_to == "docs_sync.write":
        return docs.docs_write(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )

    if maps_to == "docs_sync.status":
        return docs.docs_status(backends, scope=scope, base=base)

    if maps_to == "docs.stale_candidates" or maps_to == "docs_sync.stale_candidates":
        return docs.docs_stale_candidates(backends, arguments, scope=scope, base=base)

    if maps_to == "docs_sync.authoring_standards":
        return docs.docs_authoring_standards(base=base)
    if maps_to == "docs_sync.catalog":
        return docs.docs_catalog(arguments, base=base)

    if maps_to == "quality.audit":
        return quality.quality_audit(
            backends,
            arguments,
            scope=scope,
            correlation_id=correlation_id,
            base=base,
        )

    if maps_to == "guidance.resolve":
        return guidance.guidance_resolve(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )

    if maps_to == "guidance.list_skills":
        return guidance.guidance_list_skills(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )

    if maps_to == "guidance.get_skill":
        return guidance.guidance_get_skill(
            backends, arguments, scope=scope, correlation_id=correlation_id, base=base
        )

    if maps_to == "backup.status":
        return backup.backup_status(base=base)

    if maps_to == "backup.dry_run":
        return backup.backup_dry_run(arguments, base=base)

    raise ValueError(f"unmapped capability: {maps_to}")


def _memory_retrieve(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    query = str(arguments.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    backends.ensure_memory_seed(scope, query)
    bundle = backends.memory.retrieve_context(
        backends.memory_scope(scope),
        backends.actor_id,
        correlation_id,
        query,
    )
    public = bundle.public()
    return {
        **base,
        "query": query,
        "include_history": bool(arguments.get("include_history", False)),
        "bundle_id": public.get("bundle_id"),
        "items": public.get("items") or [],
        "excluded": public.get("excluded") or [],
    }


def _create_task(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    title = str(arguments.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    instructions = str(arguments.get("instructions") or "Implement via Astloom MCP task").strip()
    record = backends.core.create(
        Kind.TASK,
        backends.core_scope(scope),
        backends.actor_id,
        correlation_id,
        f"mcp-task:{correlation_id}",
        {
            "title": title,
            "assignee_type": "backend",
            "instructions": instructions,
            "acceptance_criteria": ["Implemented", "Tests pass"],
        },
    )
    return {**base, "task": record.public()}
