from __future__ import annotations

from typing import Any
from uuid import uuid4

from . import _paths  # noqa: F401 — side effect: service path bootstrap

from .code_graph._resolve import resolve_symbol_id
from .platform import PlatformBackends


def _human_documented_by_edges(
    backends: PlatformBackends,
    scope: dict[str, str],
    symbol: str,
) -> tuple[str, list[dict[str, Any]]] | None:
    """Return (graph_symbol_id, human DOCUMENTED_BY edge views) when the graph knows the symbol.

    Phase-2 human links live on the code graph (`doc:human:…` / origin=human). docs-sync
    Postgres anchors are a separate store and must not invent Neo4j edges — but MCP drift
    must consult the graph SoT before claiming missing_doc.
    """
    try:
        backends.ensure_graph_seed(scope)
        symbol_id = resolve_symbol_id(backends, scope, {"qualified_name": symbol})
    except ValueError:
        return None
    try:
        from code_graph_service.domain.errors import NotFoundError

        payload = backends.graph.structural_query(
            backends.graph_scope(scope),
            symbol_id,
            "DOCUMENTED_BY",
            max_depth=1,
        )
    except NotFoundError:
        return None
    human: list[dict[str, Any]] = []
    for edge in payload.get("edges") or []:
        if str(edge.get("source_id") or "") != symbol_id:
            continue
        target = str(edge.get("target_id") or "")
        meta = edge.get("metadata") if isinstance(edge.get("metadata"), dict) else {}
        if meta.get("origin") == "human" or target.startswith("doc:human:"):
            human.append(
                {
                    "id": edge.get("id"),
                    "rel_type": edge.get("rel_type"),
                    "source_id": edge.get("source_id"),
                    "target_id": target,
                    "confidence": edge.get("confidence"),
                    "metadata": meta,
                }
            )
    return symbol_id, human


def docs_authoring_standards(
    *,
    base: dict[str, Any],
) -> dict[str, Any]:
    """Return Full-tier documentation authoring law (not Body-tier docs-sync validate)."""
    from common_context_service.documentation_authoring_law import authoring_law_payload

    return {**base, "authoring_standards": authoring_law_payload()}


def docs_catalog(
    arguments: dict[str, Any],
    *,
    base: dict[str, Any],
) -> dict[str, Any]:
    """Cached docs frontmatter catalog (tags/lanes) for retrieval narrowing."""
    from pathlib import Path

    from astloom_cli.docs_catalog import filter_docs_catalog, get_docs_catalog
    from astloom_cli.util import repo_root

    refresh = bool(arguments.get("refresh") or False)
    has_links = arguments.get("has_linked_symbols")
    if has_links is not None:
        has_links = bool(has_links)
    limit = int(arguments.get("limit") or 50)
    roots_raw = arguments.get("roots")
    roots: list[str] | None = None
    if isinstance(roots_raw, list):
        roots = [str(x).strip() for x in roots_raw if str(x).strip()]
    elif isinstance(roots_raw, str) and roots_raw.strip():
        roots = [p.strip() for p in roots_raw.split(",") if p.strip()]
    catalog = get_docs_catalog(
        Path(repo_root()).resolve(),
        refresh=refresh or bool(roots),
        roots=roots,
    )
    report = filter_docs_catalog(
        catalog,
        tag=str(arguments.get("tag") or ""),
        concern_lane=str(arguments.get("concern_lane") or ""),
        lifecycle_lane=str(arguments.get("lifecycle_lane") or ""),
        audience_lane=str(arguments.get("audience_lane") or ""),
        phase=str(arguments.get("phase") or ""),
        doc_type=str(arguments.get("doc_type") or ""),
        query=str(arguments.get("query") or ""),
        has_linked_symbols=has_links,
        limit=limit,
    )
    return {**base, **report}

def docs_status(
    backends: PlatformBackends,
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    docs_scope = backends.docs_scope(scope)
    coverage = backends.docs.get_doc_coverage(docs_scope)
    missing = backends.docs.find_missing_docs(docs_scope)
    return {
        **base,
        "coverage": coverage,
        "missing": missing,
        "missing_count": len(missing),
    }


def docs_stale_candidates(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    base: dict[str, Any],
) -> dict[str, Any]:
    """Scored stale-documentation candidates (Astloom does not delete Markdown).

    Normative: docs/07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md
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
    include_coverage_gaps = bool(arguments.get("include_coverage_gaps") or False)
    path_prefix = str(arguments.get("path_prefix") or "").strip() or None
    if "min_confidence" not in arguments or arguments.get("min_confidence") is None:
        min_confidence: float | None = None
    else:
        min_confidence = float(arguments.get("min_confidence"))
    requested = str(arguments.get("project_id") or "").strip()
    if requested and requested != scope.get("project_id"):
        raise ValueError("project_id does not match the active MCP project scope")

    docs_scope = backends.docs_scope(scope)
    payload = backends.docs.stale_candidates(
        docs_scope,
        scope_mode=scope_mode,
        anchor_symbols=[str(x) for x in (anchors or [])],
        anchor_paths=[str(x) for x in (paths or [])],
        max_results=max_results,
        include_uncertain=include_uncertain,
        min_confidence=min_confidence,
        path_prefix=path_prefix,
        include_coverage_gaps=include_coverage_gaps,
        freshness="ok",
    )
    # index_coverage: absence claims unsafe when docs store empty under non-scan modes handled in domain.
    docs_count = len(backends.docs.store.list_documents(docs_scope))
    safe_absence = docs_count > 0 or scope_mode == "project_scan"
    payload["index_coverage"] = {
        "status": "ok" if safe_absence else "incomplete",
        "pending_count": 0,
        "safe_absence_claims": safe_absence,
        "note": (
            "docs-sync registry present for scoped absence claims"
            if safe_absence
            else "empty docs registry — orphan claims incomplete"
        ),
    }
    if triage:
        for row in list(payload.get("skipped_uncertain") or []):
            if not isinstance(row, dict):
                continue
            row["triage"] = {
                "safe_to_delete": False,
                "safe_to_unlink": False,
                "note": "triage_cannot_raise_act_flags",
            }
        payload["triage_enabled"] = True
        payload["triage_note"] = "triage_cannot_raise_act_flags"
        payload["triage_engine"] = "local_rules"
    return {
        **base,
        "project_id": scope.get("project_id"),
        **payload,
    }


def docs_drift_check(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    symbol = str(arguments.get("symbol") or "").strip()
    if not symbol:
        raise ValueError("symbol is required")
    file_path = arguments.get("file_path")

    graph_hit = _human_documented_by_edges(backends, scope, symbol)
    if graph_hit is not None:
        graph_symbol_id, human_edges = graph_hit
        if human_edges:
            return {
                **base,
                "symbol": symbol,
                "file_path": file_path,
                "symbol_id": graph_symbol_id,
                "drift": False,
                "findings": [],
                "lookup_source": "graph",
                "documented_by": human_edges,
            }

    symbol_id = backends.ensure_docs_symbol(scope, symbol, str(file_path) if file_path else None)
    findings = backends.docs.detect_drift(
        backends.docs_scope(scope),
        backends.actor_id,
        correlation_id,
        f"mcp-drift:{correlation_id}",
        symbol_ids=[symbol_id],
    )
    return {
        **base,
        "symbol": symbol,
        "file_path": file_path,
        "symbol_id": symbol_id,
        "drift": bool(findings),
        "findings": [item.public() for item in findings],
        "lookup_source": "docs_sync",
    }


def docs_write(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    mode = str(arguments.get("mode") or "").strip().lower()
    if mode not in {"validate", "note", "draft", "index"}:
        raise ValueError("mode must be one of: validate, note, draft, index")

    docs_scope = backends.docs_scope(scope)
    title = str(arguments.get("title") or "").strip()
    body = str(arguments.get("body") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip()
    file_path = str(arguments.get("file_path") or "").strip() or None
    owner = str(arguments.get("owner") or backends.actor_id).strip() or backends.actor_id
    status = str(arguments.get("status") or "draft").strip() or "draft"
    path = str(arguments.get("path") or "").strip()
    custom_fm = arguments.get("frontmatter") if isinstance(arguments.get("frontmatter"), dict) else None

    if mode == "validate":
        source = "arguments"
        frontmatter = custom_fm
        if frontmatter is None and path:
            from pathlib import Path

            from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter
            from astloom_cli.util import repo_root

            candidate = Path(path)
            if not candidate.is_absolute():
                candidate = Path(repo_root()) / path
            if candidate.is_file():
                try:
                    text = candidate.read_text(encoding="utf-8")
                except OSError as exc:
                    raise ValueError(f"unable to read path for validate: {exc}") from exc
                loaded, _body = parse_markdown_frontmatter(text)
                if not loaded:
                    raise ValueError(f"no YAML frontmatter found at path: {path}")
                # Full-tier product docs often omit empty list fields; Body-tier
                # validate still requires list keys — normalize before checking.
                frontmatter = dict(loaded)
                if "linked_symbols" not in frontmatter:
                    frontmatter["linked_symbols"] = []
                if "decision_refs" not in frontmatter:
                    frontmatter["decision_refs"] = []
                source = "path"
        if frontmatter is None:
            frontmatter = build_frontmatter(
                title=title or "Untitled",
                owner=owner,
                status=status,
                doc_id=str(arguments.get("doc_id") or "").strip() or None,
                linked_symbols=[symbol] if symbol else [],
            )
            source = "generated"
        errors = backends.docs.validate_frontmatter(frontmatter)
        return {
            **base,
            "mode": "validate",
            "ok": not errors,
            "errors": errors,
            "frontmatter": frontmatter,
            "source": source,
            "path": path or None,
        }

    if mode == "draft":
        if not title or not body:
            raise ValueError("draft mode requires title and body")
        if not symbol:
            raise ValueError("draft mode requires symbol")
        symbol_id = backends.ensure_docs_symbol(scope, symbol, file_path)
        draft = backends.docs.create_draft(
            docs_scope,
            backends.actor_id,
            correlation_id,
            f"mcp-docs-draft:{correlation_id}",
            {
                "symbol_id": symbol_id,
                "title": title,
                "body": body,
            },
        )
        return {
            **base,
            "mode": "draft",
            "written": "draft",
            "symbol": symbol,
            "symbol_id": symbol_id,
            "draft": draft.public(),
        }

    if mode in {"note", "index"}:
        if not title or not body:
            raise ValueError(f"{mode} mode requires title and body")
        linked: list[str] = []
        symbol_id = None
        if symbol:
            symbol_id = backends.ensure_docs_symbol(scope, symbol, file_path)
            linked = [symbol]
        if not path:
            slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in title.lower()).strip("-") or "note"
            path = f"docs/cursor/{slug}.md"
        frontmatter = custom_fm or build_frontmatter(
            title=title,
            owner=owner,
            status=status if mode == "index" else "draft",
            doc_id=str(arguments.get("doc_id") or "").strip() or None,
            linked_symbols=linked,
        )
        errors = backends.docs.validate_frontmatter(frontmatter)
        if errors:
            raise ValueError("frontmatter validation failed: " + "; ".join(errors))
        document = backends.docs.index_document(
            docs_scope,
            backends.actor_id,
            correlation_id,
            f"mcp-docs-{mode}:{correlation_id}",
            {
                "path": path,
                "frontmatter": frontmatter,
                "body": body,
            },
        )
        anchor = None
        if symbol_id:
            symbol_row = backends.docs.store.get_symbol(symbol_id, docs_scope)
            anchor = backends.docs.register_anchor(
                docs_scope,
                backends.actor_id,
                correlation_id,
                f"mcp-docs-anchor:{correlation_id}",
                {
                    "doc_id": document.id,
                    "symbol_id": symbol_id,
                    "recorded_hash": symbol_row.body_hash,
                },
            )
        return {
            **base,
            "mode": mode,
            "written": "document",
            "path": path,
            "symbol": symbol or None,
            "symbol_id": symbol_id,
            "document": document.public(),
            "anchor": anchor.public() if anchor is not None else None,
        }

    raise ValueError(f"unsupported docs write mode: {mode}")


def build_frontmatter(
    *,
    title: str,
    owner: str,
    status: str,
    doc_id: str | None,
    linked_symbols: list[str],
) -> dict[str, Any]:
    return {
        "doc_id": doc_id or f"doc_{uuid4().hex[:12]}",
        "title": title,
        "owner": owner,
        "status": status,
        "schema_version": "1.0",
        "linked_symbols": list(linked_symbols),
        "decision_refs": [],
    }
