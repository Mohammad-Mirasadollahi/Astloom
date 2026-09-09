"""MCP read/query handlers for the code-knowledge graph."""

from __future__ import annotations

import os
import time
from typing import Any

from code_graph_service.domain.confidence_policy import DEFAULT_IMPACT_MIN_CONFIDENCE
from code_graph_service.domain.errors import CodeGraphError, NotFoundError

from ..platform import PlatformBackends
from ._resolve import resolve_symbol_id


def _unused_candidates_budget_seconds() -> float:
    """Soft collect budget — leave headroom under the HTTP MCP tool timeout."""
    raw = str(os.environ.get("ASTLOOM_MCP_UNUSED_CANDIDATES_BUDGET_SECONDS", "18")).strip()
    try:
        value = float(raw)
    except ValueError:
        value = 18.0
    if value <= 0:
        value = 18.0
    tool_raw = str(os.environ.get("ASTLOOM_MCP_TOOL_TIMEOUT_SECONDS", "25")).strip()
    try:
        tool_timeout = float(tool_raw)
    except ValueError:
        tool_timeout = 25.0
    if tool_timeout <= 0:
        tool_timeout = 25.0
    return max(3.0, min(value, max(3.0, tool_timeout - 6.0)))


def search(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    query = str(arguments.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    top_k = int(arguments.get("top_k") or 5)
    backends.ensure_graph_seed(scope)
    hits = backends.graph.semantic_search(backends.graph_scope(scope), query, top_k=top_k)
    payload = {
        **base,
        "query": query,
        "top_k": top_k,
        "graph_mode": backends.graph_mode,
        "symbols": hits,
    }
    if hits and hits[0].get("semantic_error"):
        payload["semantic_error"] = hits[0]["semantic_error"]
        payload["degraded"] = True
    return payload


def get_symbol(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    backends.ensure_graph_seed(scope)
    symbol_id = resolve_symbol_id(backends, scope, arguments)
    try:
        symbol = backends.graph.get_symbol(backends.graph_scope(scope), symbol_id)
    except NotFoundError as exc:
        raise ValueError(str(exc.message)) from exc
    view = backends.graph._symbol_view(symbol)  # noqa: SLF001 — shared public view helper
    return {**base, "graph_mode": backends.graph_mode, "symbol": view}


def neighbors(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    backends.ensure_graph_seed(scope)
    symbol_id = resolve_symbol_id(backends, scope, arguments)
    rel_type = str(arguments.get("rel_type") or "").strip() or None
    max_depth = int(arguments.get("max_depth") or 1)
    max_depth = max(1, min(max_depth, 8))
    try:
        payload = backends.graph.structural_query(
            backends.graph_scope(scope),
            symbol_id,
            rel_type,
            max_depth=max_depth,
        )
    except NotFoundError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}


def impact(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    """Directed impact / blast radius around a seed symbol (Codebase-Memory hybrid)."""
    backends.ensure_graph_seed(scope)
    symbol_id = resolve_symbol_id(backends, scope, arguments)
    rel_type = str(arguments.get("rel_type") or "").strip() or None
    rel_types = arguments.get("rel_types")
    if rel_types is not None and not isinstance(rel_types, list):
        raise ValueError("rel_types must be an array of strings")
    if rel_type and not rel_types:
        rel_types = [rel_type]
    max_depth = int(arguments.get("max_depth") or 3)
    max_depth = max(1, min(max_depth, 8))
    direction = str(arguments.get("direction") or "both").strip() or "both"
    min_confidence = (
        str(arguments.get("min_confidence") or "").strip()
        or DEFAULT_IMPACT_MIN_CONFIDENCE
    )
    top_k = int(arguments.get("top_k") or 50)
    try:
        payload = backends.graph.impact_analysis(
            backends.graph_scope(scope),
            symbol_id,
            direction=direction,
            max_depth=max_depth,
            min_confidence=min_confidence,
            rel_types=[str(x) for x in (rel_types or [])] or None,
            top_k=top_k,
        )
    except NotFoundError as exc:
        raise ValueError(str(exc.message)) from exc
    return {
        **base,
        "graph_mode": backends.graph_mode,
        "impact_of": symbol_id,
        "min_confidence": min_confidence,
        **payload,
    }


def callers(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    """Ranked inbound callers (fan-in) for a seed symbol."""
    backends.ensure_graph_seed(scope)
    symbol_id = resolve_symbol_id(backends, scope, arguments)
    top_k = int(arguments.get("top_k") or 20)
    max_depth = max(1, min(int(arguments.get("max_depth") or 1), 8))
    min_confidence = (
        str(arguments.get("min_confidence") or "").strip()
        or DEFAULT_IMPACT_MIN_CONFIDENCE
    )
    rel_types = arguments.get("rel_types")
    if rel_types is not None and not isinstance(rel_types, list):
        raise ValueError("rel_types must be an array of strings")
    try:
        payload = backends.graph.callers(
            backends.graph_scope(scope),
            symbol_id,
            top_k=top_k,
            max_depth=max_depth,
            min_confidence=min_confidence,
            rel_types=[str(x) for x in (rel_types or [])] or None,
        )
    except NotFoundError as exc:
        raise ValueError(str(exc.message)) from exc
    return {
        **base,
        "graph_mode": backends.graph_mode,
        "callers_of": symbol_id,
        "min_confidence": min_confidence,
        **payload,
    }


def community(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    """Community membership for one symbol (Leiden/Louvain)."""
    backends.ensure_graph_seed(scope)
    symbol_id = resolve_symbol_id(backends, scope, arguments)
    member_limit = max(1, min(int(arguments.get("member_limit") or 30), 200))
    try:
        payload = backends.graph.community_of_symbol(
            backends.graph_scope(scope),
            symbol_id,
            member_limit=member_limit,
        )
    except NotFoundError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}


def call_path(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    """Compact outbound call-path pack from a seed symbol."""
    backends.ensure_graph_seed(scope)
    symbol_id = resolve_symbol_id(backends, scope, arguments)
    max_depth = max(1, min(int(arguments.get("max_depth") or 4), 8))
    max_nodes = max(2, min(int(arguments.get("max_nodes") or 40), 200))
    try:
        payload = backends.graph.call_path_pack(
            backends.graph_scope(scope),
            symbol_id,
            max_depth=max_depth,
            max_nodes=max_nodes,
        )
    except NotFoundError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}


def unused_candidates(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    """Scored unused-symbol candidates (Astloom does not delete files).

    Default modes are task-scoped (anchors required). ``project_scan`` is opt-in
    ranked discovery. Optional ``triage`` runs local advisory rules (or an injected
    LLM judge) and cannot raise ``safe_to_delete``.
    """
    scope_mode = str(arguments.get("scope_mode") or "task_neighborhood").strip()
    anchors = arguments.get("anchor_symbols")
    paths = arguments.get("anchor_paths")
    if anchors is not None and not isinstance(anchors, list):
        raise ValueError("anchor_symbols must be an array of strings")
    if paths is not None and not isinstance(paths, list):
        raise ValueError("anchor_paths must be an array of strings")
    max_results = int(arguments.get("max_results") or 50)
    include_uncertain = bool(arguments.get("include_uncertain") or False)
    triage = bool(arguments.get("triage") or False)
    disk_search = bool(arguments.get("disk_search") or False)
    coverage_raw = arguments.get("coverage_hits")
    coverage_hits: dict[str, int] | None = None
    if isinstance(coverage_raw, dict):
        coverage_hits = {}
        for key, val in coverage_raw.items():
            try:
                coverage_hits[str(key)] = int(val)
            except (TypeError, ValueError):
                continue
    flag_raw = arguments.get("flag_states")
    flag_states = flag_raw if isinstance(flag_raw, dict) else None
    repo_root = str(arguments.get("repo_root") or "").strip() or None
    verify_disk_presence = bool(arguments.get("verify_disk_presence") or False)
    if not repo_root:
        import os

        repo_root = (
            str(os.environ.get("ASTLOOM_MCP_WORKSPACE_ROOT") or "").strip()
            or str(os.environ.get("ASTLOOM_ROOT") or "").strip()
            or None
        )
    if not verify_disk_presence:
        try:
            from astloom_cli.software_paths import software_paths_for_project

            pinned = software_paths_for_project(
                str(scope.get("tenant_id") or ""),
                str(scope.get("workspace_id") or ""),
                str(scope.get("project_id") or ""),
                must_exist=True,
            )
            if pinned:
                # Project pin is the indexed tree — enable disk demotion against it.
                verify_disk_presence = True
                if not str(arguments.get("repo_root") or "").strip():
                    repo_root = pinned[0]
        except Exception:  # noqa: BLE001 — disk demotion is best-effort
            pass
    if arguments.get("verify_disk_presence") is False:
        verify_disk_presence = False
    path_prefix = str(arguments.get("path_prefix") or "").strip() or None
    # Normative: project_scan requires a floor; discovery default is 0.50 when omitted.
    if "min_confidence" not in arguments or arguments.get("min_confidence") is None:
        min_confidence: float | None = None  # domain applies project_scan default
    else:
        min_confidence = float(arguments.get("min_confidence"))
    # project_id from session scope; optional arg must match when provided
    requested = str(arguments.get("project_id") or "").strip()
    if requested and requested != scope.get("project_id"):
        raise ValueError("project_id does not match the active MCP project scope")
    backends.ensure_graph_seed(scope)
    deadline = time.monotonic() + _unused_candidates_budget_seconds()
    try:
        payload = backends.graph.unused_candidates(
            backends.graph_scope(scope),
            scope_mode=scope_mode,
            anchor_symbols=[str(x) for x in (anchors or [])],
            anchor_paths=[str(x) for x in (paths or [])],
            max_results=max_results,
            include_uncertain=include_uncertain,
            min_confidence=min_confidence,
            coverage_hits=coverage_hits,
            flag_states=flag_states,
            repo_root=repo_root,
            disk_search=disk_search,
            verify_disk_presence=verify_disk_presence,
            path_prefix=path_prefix,
            deadline_monotonic=deadline,
        )
    except CodeGraphError as exc:
        raise ValueError(str(getattr(exc, "message", exc))) from exc
    except TypeError as exc:
        # Only fall back when this build rejects deadline_monotonic — not any TypeError.
        if "deadline_monotonic" not in str(exc):
            raise
        try:
            payload = backends.graph.unused_candidates(
                backends.graph_scope(scope),
                scope_mode=scope_mode,
                anchor_symbols=[str(x) for x in (anchors or [])],
                anchor_paths=[str(x) for x in (paths or [])],
                max_results=max_results,
                include_uncertain=include_uncertain,
                min_confidence=min_confidence,
                coverage_hits=coverage_hits,
                flag_states=flag_states,
                repo_root=repo_root,
                disk_search=disk_search,
                verify_disk_presence=verify_disk_presence,
                path_prefix=path_prefix,
            )
        except CodeGraphError as exc2:
            raise ValueError(str(getattr(exc2, "message", exc2))) from exc2
    if triage:
        try:
            from code_graph_service.domain.dead_code_scoring import llm_triage_port
        except Exception:  # noqa: BLE001 — gateway must stay resilient
            llm_triage_port = None  # type: ignore[assignment]
        for row in list(payload.get("skipped_uncertain") or []):
            if not isinstance(row, dict):
                continue
            if llm_triage_port is not None:
                verdict = llm_triage_port(row, enabled=True)
                row["triage"] = verdict or {
                    "safe_to_delete": False,
                    "note": "triage_cannot_raise_safe_to_delete",
                }
            else:
                row["triage"] = {
                    "safe_to_delete": False,
                    "note": "triage_cannot_raise_safe_to_delete",
                    "status": "port_unavailable",
                }
        payload["triage_enabled"] = True
        payload["triage_note"] = "triage_cannot_raise_safe_to_delete"
        payload["triage_engine"] = "local_rules"
    return {**base, "graph_mode": backends.graph_mode, "project_id": scope.get("project_id"), **payload}


def explore(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    """Primary surgical context tool: query → seeds + call path + budgeted bodies."""
    query = str(arguments.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    top_k = int(arguments.get("top_k") or 12)
    max_depth = int(arguments.get("max_depth") or 2)
    budget = arguments.get("budget_chars")
    budget_chars = int(budget) if budget is not None else None
    backends.ensure_graph_seed(scope)
    try:
        payload = backends.graph.explore(
            backends.graph_scope(scope),
            query,
            top_k=top_k,
            max_depth=max_depth,
            budget_chars=budget_chars,
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    payload = _apply_disk_freshness_to_explore(backends, scope, payload)
    return {**base, "graph_mode": backends.graph_mode, **payload}


def _apply_disk_freshness_to_explore(
    backends: PlatformBackends,
    scope: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Refuse stale/missing-on-disk bodies so agents cannot treat Neo4j as current law."""
    from pathlib import Path

    from astloom_cli.commands.inventory.edited import disk_content_hash
    from astloom_cli.software_paths import software_paths_for_project
    from code_graph_service.domain.ports import list_file_symbols_for_paths

    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        return payload

    pinned = software_paths_for_project(
        str(scope.get("tenant_id") or ""),
        str(scope.get("workspace_id") or ""),
        str(scope.get("project_id") or ""),
        must_exist=False,
    )
    if not pinned:
        return payload
    root = Path(pinned[0]).expanduser()
    try:
        if not root.is_dir():
            return payload
    except OSError:
        return payload

    paths = sorted(
        {
            str(sec.get("file_path") or "").replace("\\", "/").strip()
            for sec in sections
            if isinstance(sec, dict) and str(sec.get("file_path") or "").strip()
        }
    )
    if not paths:
        return payload

    graph_scope = backends.graph_scope(scope)
    try:
        file_syms = list_file_symbols_for_paths(backends.graph.store, graph_scope, paths)
    except Exception:  # noqa: BLE001 — freshness is best-effort overlay
        return payload
    hash_by_path = {
        str(sym.file_path or "").replace("\\", "/"): str(getattr(sym, "hash_value", "") or "").strip()
        for sym in file_syms
        if sym.file_path
    }

    stale_paths: list[str] = []
    missing_paths: list[str] = []
    for rel in paths:
        abs_path = root / rel
        if not abs_path.is_file():
            missing_paths.append(rel)
            continue
        stored = hash_by_path.get(rel) or ""
        if not stored:
            continue
        disk = disk_content_hash(abs_path, "")
        if disk and disk != stored:
            stale_paths.append(rel)

    bad = set(stale_paths) | set(missing_paths)
    if not bad:
        return payload

    # Redact bodies for stale/missing paths — keep structure, force Read/sync.
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        rel = str(sec.get("file_path") or "").replace("\\", "/").strip()
        if rel not in bad:
            continue
        symbols = sec.get("symbols")
        if isinstance(symbols, list):
            redacted = []
            for row in symbols:
                if not isinstance(row, dict):
                    redacted.append(row)
                    continue
                clone = dict(row)
                clone["body"] = ""
                clone["body_redacted"] = True
                clone["freshness_status"] = (
                    "MISSING_ON_DISK" if rel in missing_paths else "STALE"
                )
                redacted.append(clone)
            sec["symbols"] = redacted
        sec["skeletonized"] = True
        sec["disk_freshness"] = (
            "missing_on_disk" if rel in missing_paths else "content_changed"
        )

    freshness = dict(payload.get("freshness") or {})
    parts = []
    if missing_paths:
        parts.append("missing on disk: " + ", ".join(missing_paths[:8]))
    if stale_paths:
        parts.append("content changed since ingest: " + ", ".join(stale_paths[:8]))
    banner = (
        "⚠️ Graph stale vs disk — "
        + "; ".join(parts)
        + ". Bodies redacted; run scoped sync / Read the file before editing."
    )
    freshness.update(
        {
            "status": "stale_content" if stale_paths else "missing_on_disk",
            "is_stale": True,
            "must_sync": True,
            "banner": banner,
            "stale_files": stale_paths[:50],
            "missing_files": missing_paths[:50],
            "bodies_redacted": True,
        }
    )
    payload["freshness"] = freshness
    notes = list(payload.get("notes") or [])
    notes.insert(0, banner)
    payload["notes"] = notes
    return payload


def detect_changes(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    """Risk-scored review context for a set of changed files."""
    raw = arguments.get("changed_files") or arguments.get("files") or []
    if isinstance(raw, str):
        changed_files = [p.strip() for p in raw.split(",") if p.strip()]
    else:
        changed_files = [str(p).strip() for p in raw if str(p).strip()]
    if not changed_files:
        raise ValueError("changed_files is required")
    include_flows = bool(arguments.get("include_flows", True))
    backends.ensure_graph_seed(scope)
    try:
        payload = backends.graph.detect_changes(
            backends.graph_scope(scope),
            changed_files,
            include_flows=include_flows,
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}


def architecture_overview(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    top_n = int(arguments.get("top_n") or 10)
    backends.ensure_graph_seed(scope)
    try:
        payload = backends.graph.architecture_overview(
            backends.graph_scope(scope), top_n=top_n
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}


def symbol_path(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    start_id = str(arguments.get("start_id") or arguments.get("from") or "").strip()
    end_id = str(arguments.get("end_id") or arguments.get("to") or "").strip()
    max_depth = int(arguments.get("max_depth") or 12)
    backends.ensure_graph_seed(scope)
    try:
        payload = backends.graph.symbol_path(
            backends.graph_scope(scope),
            start_id,
            end_id,
            max_depth=max_depth,
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}


def hybrid_search(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    query = str(arguments.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    top_k = int(arguments.get("top_k") or 10)
    backends.ensure_graph_seed(scope)
    try:
        payload = backends.graph.hybrid_search(
            backends.graph_scope(scope), query, top_k=top_k
        )
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}


def freshness(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    backends.ensure_graph_seed(scope)
    file_path = str(arguments.get("file_path") or "").strip()
    if file_path:
        payload = backends.graph.mark_file_pending(file_path)
    else:
        payload = backends.graph.freshness_status(backends.graph_scope(scope))
    return {**base, "graph_mode": backends.graph_mode, **payload}


def generation_context(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    backends.ensure_graph_seed(scope)
    symbol_id = resolve_symbol_id(backends, scope, arguments)
    max_symbols = int(arguments.get("max_symbols") or 12)
    max_symbols = max(1, min(max_symbols, 64))
    try:
        payload = backends.graph.build_generation_context(
            backends.graph_scope(scope),
            symbol_id,
            max_symbols=max_symbols,
        )
    except NotFoundError as exc:
        raise ValueError(str(exc.message)) from exc
    except CodeGraphError as exc:
        raise ValueError(str(exc.message)) from exc
    return {**base, "graph_mode": backends.graph_mode, **payload}


def language_profile(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    backends.ensure_graph_seed(scope)
    profile = backends.graph.get_polyglot_profile(backends.graph_scope(scope))
    payload = profile.to_dict() if hasattr(profile, "to_dict") else dict(profile)
    return {**base, "graph_mode": backends.graph_mode, "language_profile": payload}
