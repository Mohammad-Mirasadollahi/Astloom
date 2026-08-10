"""Phase-2 human documentation sync: docs-sync SoT + code-graph DOCUMENTED_BY.

Role: discover Markdown, index into docs-sync, project ``DOCUMENTED_BY`` for
resolved ``linked_symbols`` (catalog orders the queue; evidence may merge tokens).
Source of truth: docs-sync Document/DocAnchor; Neo4j human ``doc:human:…`` nodes.
Parallelism: bounded by the database store-slot budget; docs-sync stores are
thread-safe (Postgres per-thread connections; in-memory ``RLock``).
Allowed: soft-fail per doc; skip unchanged bodies on re-sync (optional link
refresh after code ingest); concurrent docs-sync writes under workers.
Forbidden: invent edges for unresolved tokens; store graph FILE hashes as
docs-sync body hashes; treat duplicate ``doc:human`` rows as content changes.
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from astloom_cli.markdown_frontmatter import parse_markdown_frontmatter, provisional_frontmatter
from astloom_cli.util import repo_root

ProgressCallback = Callable[[dict[str, Any]], None]


def _env_truthy(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "off")


@dataclass
class DocsLinkSyncResult:
    docs_discovered: int = 0
    docs_indexed: int = 0
    anchors_registered: int = 0
    links_created: int = 0
    unresolved_tokens: list[str] = field(default_factory=list)
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    evidence_enabled: bool = True
    evidence_tokens_new: int = 0
    evidence_frontmatter_applied: int = 0
    catalog_ordered: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "docs_discovered": self.docs_discovered,
            "docs_indexed": self.docs_indexed,
            "anchors_registered": self.anchors_registered,
            "links_created": self.links_created,
            "unresolved_tokens": list(self.unresolved_tokens),
            "skipped": self.skipped,
            "errors": list(self.errors),
            "evidence_enabled": self.evidence_enabled,
            "evidence_tokens_new": self.evidence_tokens_new,
            "evidence_frontmatter_applied": self.evidence_frontmatter_applied,
            "catalog_ordered": self.catalog_ordered,
        }


def _ensure_docs_sync_import() -> None:
    root = repo_root()
    src = root / "backend" / "services" / "docs-sync-service" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def resolve_docs_sync_database_url(environ: dict[str, str] | None = None) -> str:
    """Resolve docs-sync Postgres URL the same way MCP companion stores do.

    Prefer ``ASTLOOM_DOCS_SYNC_DATABASE_URL``, else ``ASTLOOM_DATABASE_URL``,
    else derive the shared URL from compose ``.env.local`` (same path as
    ``local_mcp`` / ``apply_compose_env_to_os``). This keeps Phase 2 sync and
    ``astloom_docs_status`` on one durable SoT instead of process-local memory.
    """
    env = dict(os.environ if environ is None else environ)
    specific = str(env.get("ASTLOOM_DOCS_SYNC_DATABASE_URL") or "").strip()
    if specific:
        return specific
    shared = str(env.get("ASTLOOM_DATABASE_URL") or "").strip()
    if shared:
        return shared
    try:
        from astloom_cli.remote_client import apply_compose_env_to_os
        from astloom_cli.util import repo_root

        apply_compose_env_to_os(env, repo_root())
    except SystemExit:
        return ""
    return str(env.get("ASTLOOM_DATABASE_URL") or "").strip()


def _docs_sync_service():
    """In-process docs-sync (Postgres when URL set; else memory).

    Reuses one composition root per process (Phase D DI).
    """
    from astloom_cli.cli_defaults import load_dotenv_files
    from astloom_cli.process_containers import get_docs_sync_service

    load_dotenv_files()
    _ensure_docs_sync_import()
    url = resolve_docs_sync_database_url()
    backend = (
        "postgres"
        if url.startswith(("postgresql://", "postgresql+psycopg://"))
        else "memory"
    )

    def _factory():
        if backend == "postgres":
            from docs_sync_service.bootstrap import Settings, build_container

            return build_container(Settings(database_url=url))
        from docs_sync_service.core import DocsSyncService
        from docs_sync_service.testing import InMemoryStore

        return DocsSyncService(InMemoryStore())

    return get_docs_sync_service(backend=backend, factory=_factory)


def _indexed_doc_hashes(
    graph_service: Any, graph_scope: Any
) -> tuple[dict[str, set[str]], dict[str, list[str]]]:
    """Map relative doc path → body hashes / symbol ids for human DOCUMENTATION nodes.

    One path can have multiple ``doc:human:…`` symbols when ``doc_id`` changed
    (provisional ``doc-…`` → stable id). Classification must treat the body as
    unchanged if *any* stored hash matches; last-wins single hash falsely marks
    paths as changed forever.
    """
    from code_graph_service.domain.enums import DocStatus, SymbolKind

    hashes: dict[str, set[str]] = {}
    symbol_ids: dict[str, list[str]] = {}
    try:
        symbols = graph_service.store.list_symbols(graph_scope)
    except Exception:  # noqa: BLE001
        return hashes, symbol_ids
    for sym in symbols:
        kind = sym.kind.value if hasattr(sym.kind, "value") else str(sym.kind)
        if kind != SymbolKind.DOCUMENTATION.value:
            continue
        status = sym.doc_status.value if hasattr(sym.doc_status, "value") else str(sym.doc_status)
        if status != DocStatus.HUMAN.value:
            continue
        rel = str(sym.file_path or "").replace("\\", "/").strip()
        if not rel:
            continue
        digest_value = str(getattr(sym, "hash_value", "") or "")
        if digest_value:
            hashes.setdefault(rel, set()).add(digest_value)
        sid = str(getattr(sym, "id", "") or "").strip()
        if sid:
            symbol_ids.setdefault(rel, []).append(sid)
    return hashes, symbol_ids


def _catalog_by_path(root_path: Path) -> dict[str, dict[str, Any]]:
    """Best-effort catalog index for Phase 2 ordering (never invents edges)."""
    from astloom_cli.docs_catalog import load_docs_catalog_cache

    for base in (root_path, repo_root()):
        try:
            cached = load_docs_catalog_cache(base)
        except Exception:  # noqa: BLE001
            cached = None
        if not cached:
            continue
        docs = cached.get("documents") or []
        if not docs:
            continue
        out: dict[str, dict[str, Any]] = {}
        for row in docs:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "").replace("\\", "/").strip()
            if path:
                out[path] = row
        if out:
            return out
    return {}


def _phase2_priority(
    *,
    rel: str,
    body: str,
    frontmatter: dict[str, Any],
    catalog_row: dict[str, Any] | None,
    root_path: Path,
    evidence_enabled: bool,
) -> tuple[int, str]:
    """Lower sort key = earlier. Evidence and current-lifecycle docs first."""
    from astloom_cli.docs_link_suggest import extract_evidence_link_tokens

    score = 0
    entry = catalog_row or {}
    if evidence_enabled:
        evidence = extract_evidence_link_tokens(body, repo=root_path)
        if evidence:
            score += 100
    life = str(
        entry.get("lifecycle_lane") or frontmatter.get("lifecycle_lane") or ""
    ).strip()
    if life == "current":
        score += 10
    if frontmatter.get("linked_symbols"):
        score += 5
    if entry.get("has_linked_symbols"):
        score += 2
    return (-score, rel)


def _merge_evidence_tokens(
    *,
    abs_path: Path,
    rel: str,
    body: str,
    frontmatter: dict[str, Any],
    linked_tokens: list[str],
    root_path: Path,
    apply_frontmatter: bool,
    result: DocsLinkSyncResult,
    result_lock: threading.Lock | None = None,
) -> tuple[str, dict[str, Any], list[str], int]:
    """Merge evidence tokens into linked_symbols; optionally persist frontmatter.

    Returns ``(body, frontmatter, linked_tokens, new_token_count)``.
    """
    from astloom_cli.docs_link_suggest import (
        apply_suggested_links,
        extract_evidence_link_tokens,
    )

    evidence = extract_evidence_link_tokens(body, repo=root_path)
    existing = set(linked_tokens)
    new_tokens = [t for t in evidence if t not in existing]
    if not new_tokens:
        return body, frontmatter, linked_tokens, 0

    def _record(*, fm_applied: bool = False, error: str = "") -> None:
        if result_lock is None:
            result.evidence_tokens_new += len(new_tokens)
            if fm_applied:
                result.evidence_frontmatter_applied += 1
            if error:
                result.errors.append(error)
            return
        with result_lock:
            result.evidence_tokens_new += len(new_tokens)
            if fm_applied:
                result.evidence_frontmatter_applied += 1
            if error:
                result.errors.append(error)

    if apply_frontmatter:
        applied = apply_suggested_links(abs_path, new_tokens)
        if applied.get("status") == "applied":
            try:
                text = abs_path.read_text(encoding="utf-8")
            except OSError as exc:
                _record(error=f"{rel}: evidence apply re-read failed: {exc}")
                merged = list(linked_tokens) + new_tokens
                frontmatter = {**frontmatter, "linked_symbols": merged}
                return body, frontmatter, merged, len(new_tokens)
            _record(fm_applied=True)
            partial, body = parse_markdown_frontmatter(text)
            frontmatter = provisional_frontmatter(rel, body, partial)
            linked_tokens = [
                str(t).strip()
                for t in (frontmatter.get("linked_symbols") or [])
                if str(t).strip()
            ]
            return body, frontmatter, linked_tokens, len(new_tokens)

    _record()
    merged = list(linked_tokens) + new_tokens
    frontmatter = {**frontmatter, "linked_symbols": merged}
    return body, frontmatter, merged, len(new_tokens)


def sync_human_docs(
    *,
    graph_service: Any,
    graph_scope: Any,
    root_path: Path,
    filters: dict[str, Any],
    actor: str = "cli",
    correlation_id: str = "",
    repo_name: str = "repo",
    on_progress: ProgressCallback | None = None,
    refresh_unchanged_links: bool = False,
) -> DocsLinkSyncResult:
    """Discover Markdown via docs.match globs, index in docs-sync, project edges.

    Body-stable docs are skipped on re-sync. Pass ``refresh_unchanged_links=True``
    (e.g. after code files were ingested this run) to re-resolve ``linked_symbols``.
    """
    from code_graph_service.application.ingest.human_docs import human_doc_symbol_id
    from code_graph_service.domain.doc_discovery import discover_documentation_files
    from code_graph_service.domain.hashing import digest

    _ensure_docs_sync_import()
    from docs_sync_service.core import Scope as DocsScope

    result = DocsLinkSyncResult()
    if not filters.get("docs_enabled", True):
        return result
    match_globs = list(filters.get("doc_match_globs") or [])
    if not match_globs:
        return result

    evidence_enabled = _env_truthy("ASTLOOM_SYNC_DOCS_EVIDENCE", "1")
    apply_evidence_fm = _env_truthy("ASTLOOM_SYNC_DOCS_EVIDENCE_APPLY", "1")
    result.evidence_enabled = evidence_enabled

    root_path = root_path.expanduser().resolve()
    discovered = discover_documentation_files(
        root_path,
        match_globs=match_globs,
        exclude_dirs=filters.get("doc_exclude_dirs"),
        exclude_globs=filters.get("doc_exclude_globs"),
        doc_paths=filters.get("doc_paths") or None,
        max_files=int(filters.get("max_files") or 2000),
    )
    result.docs_discovered = len(discovered)
    if not discovered:
        return result

    prior_hashes, prior_symbol_ids = _indexed_doc_hashes(graph_service, graph_scope)
    prior_indexed = len(prior_hashes)
    catalog_index = _catalog_by_path(root_path)
    result.catalog_ordered = bool(catalog_index)
    # Classify against body hash (same digest upsert_human_documentation stores).
    queue_new = 0
    queue_changed = 0
    prepared: list[tuple[Any, str, str, dict[str, Any], str, bool]] = []
    for item in discovered:
        abs_path = Path(item.absolute_path)
        rel = item.relative_path.replace("\\", "/")
        try:
            text = abs_path.read_text(encoding="utf-8")
        except OSError as exc:
            result.skipped += 1
            result.errors.append(f"{rel}: read failed: {exc}")
            continue
        partial, body = parse_markdown_frontmatter(text)
        frontmatter = provisional_frontmatter(rel, body, partial)
        body_hash = digest(body)
        doc_id = str(frontmatter.get("doc_id") or "").strip()
        keep_id = human_doc_symbol_id(graph_scope.project_id, doc_id) if doc_id else ""
        previous_hashes = prior_hashes.get(rel) or set()
        previous_ids = prior_symbol_ids.get(rel) or []
        body_unchanged = False
        if not previous_hashes:
            queue_new += 1
        elif body_hash in previous_hashes and keep_id in previous_ids:
            body_unchanged = True
        else:
            # Content edit, or doc_id remapped (provisional → stable) with same body.
            queue_changed += 1
        prepared.append((item, rel, body, frontmatter, body_hash, body_unchanged))

    prepared.sort(
        key=lambda row: _phase2_priority(
            rel=row[1],
            body=row[2],
            frontmatter=row[3],
            catalog_row=catalog_index.get(row[1]),
            root_path=root_path,
            evidence_enabled=evidence_enabled,
        )
    )

    def _has_linked(frontmatter: dict[str, Any]) -> bool:
        return any(str(t).strip() for t in (frontmatter.get("linked_symbols") or []))

    # Skip body-stable docs unless this run must refresh links after code ingest.
    work: list[tuple[Any, str, str, dict[str, Any], str, bool]] = [
        row
        for row in prepared
        if (not row[5]) or (refresh_unchanged_links and _has_linked(row[3]))
    ]
    queue_unchanged = sum(1 for row in work if row[5])
    prepared = work
    # done/total = files this run actually processes (new/changed/link_refresh).
    progress_total = len(prepared)
    progress_done = 0
    state_lock = threading.Lock()
    active_files: set[str] = set()

    from code_graph_service.application.ingest.parallel_files import run_parallel_file_jobs
    from code_graph_service.locked_store import resolve_sync_cpu_plan, sync_max_file_workers

    workers = min(
        sync_max_file_workers(),
        resolve_sync_cpu_plan().store_concurrency,
        max(1, progress_total or 1),
    )

    def _emit(done: int, *, file: str = "", status: str = "") -> None:
        if not callable(on_progress):
            return
        try:
            with state_lock:
                in_flight_paths = sorted(active_files)
                snap = {
                    "phase": "docs",
                    "done": done,
                    "total": progress_total,
                    "file": file,
                    "status": status,
                    "prior_indexed": prior_indexed,
                    "queue_new": queue_new,
                    "queue_changed": queue_changed,
                    "queue_unchanged": queue_unchanged,
                    "docs_indexed": result.docs_indexed,
                    "links_created": result.links_created,
                    "anchors_registered": result.anchors_registered,
                    "evidence_tokens_new": result.evidence_tokens_new,
                    "files_in_flight": len(in_flight_paths),
                    "files_in_flight_paths": in_flight_paths[:8],
                    "file_workers": workers,
                }
            on_progress(snap)
        except Exception:  # noqa: BLE001 — progress must never break docs sync
            return

    def _bump() -> int:
        nonlocal progress_done
        with state_lock:
            progress_done += 1
            return progress_done

    docs_svc = _docs_sync_service()
    docs_scope = DocsScope(
        graph_scope.tenant_id,
        graph_scope.workspace_id,
        graph_scope.project_id,
    )
    corr = correlation_id or f"docs-link-{graph_scope.project_id}"

    def _process_one(_index: int, row: tuple[Any, str, str, dict[str, Any], str, bool]) -> None:
        item, rel, body, frontmatter, _body_hash, body_unchanged = row
        with state_lock:
            active_files.add(rel)
            done_now = progress_done
        _emit(done_now, file=rel, status="active")
        abs_path = Path(item.absolute_path)
        doc_id = str(frontmatter["doc_id"]).strip()
        linked_tokens = [
            str(t).strip() for t in (frontmatter.get("linked_symbols") or []) if str(t).strip()
        ]
        evidence_added = 0
        if evidence_enabled:
            body, frontmatter, linked_tokens, evidence_added = _merge_evidence_tokens(
                abs_path=abs_path,
                rel=rel,
                body=body,
                frontmatter=frontmatter,
                linked_tokens=linked_tokens,
                root_path=root_path,
                apply_frontmatter=apply_evidence_fm,
                result=result,
                result_lock=state_lock,
            )
            doc_id = str(frontmatter["doc_id"]).strip()

        # Body hash match + no link work: skip heavy index/embed/anchor path.
        # Linked tokens still recheck so newly ingested symbols can resolve.
        if body_unchanged and not linked_tokens and not evidence_added:
            with state_lock:
                active_files.discard(rel)
            done = _bump()
            _emit(done, file=rel, status="unchanged")
            return

        # Include content fingerprint so edits get a new key (same key + new body = ConflictError).
        doc_fp = digest(f"{rel}\n{doc_id}\n{linked_tokens}\n{body}")[:16]

        try:
            document = docs_svc.index_document(
                docs_scope,
                actor,
                corr,
                f"docs-index:{rel}:{doc_id}:{doc_fp}",
                {"path": rel, "frontmatter": frontmatter, "body": body},
            )
            with state_lock:
                result.docs_indexed += 1
        except Exception as exc:
            with state_lock:
                result.skipped += 1
                result.errors.append(f"{rel}: docs-sync index failed: {exc}")
                active_files.discard(rel)
            done = _bump()
            _emit(done, file=rel, status="failed")
            return

        # Graph upsert: embed may run concurrent; store mutations via LockedStore.
        projection = graph_service.upsert_human_documentation(
            graph_scope,
            doc_id=doc_id,
            relative_path=rel,
            body=body,
            title=str(frontmatter.get("title") or doc_id),
            linked_symbol_tokens=linked_tokens,
        )
        keep_id = human_doc_symbol_id(graph_scope.project_id, doc_id)
        for stale_id in prior_symbol_ids.get(rel) or []:
            if stale_id == keep_id:
                continue
            try:
                graph_service.store.delete_symbol(stale_id, graph_scope)
            except Exception as exc:  # noqa: BLE001 — orphan cleanup must not fail sync
                with state_lock:
                    result.errors.append(f"{rel}: stale human doc cleanup failed: {exc}")
        with state_lock:
            result.links_created += int(projection.get("edges_written") or 0)
            for token in projection.get("unresolved_tokens") or []:
                if token not in result.unresolved_tokens:
                    result.unresolved_tokens.append(token)

        for symbol_graph_id in projection.get("linked_symbol_ids") or []:
            try:
                graph_sym = graph_service.store.get_symbol(symbol_graph_id, graph_scope)
            except Exception:
                continue
            try:
                sym_fp = digest(
                    f"{graph_sym.qualified_name}\n{graph_sym.hash_value}\n{graph_sym.body or ''}"
                )[:16]
                ds_symbol = docs_svc.index_symbol(
                    docs_scope,
                    actor,
                    corr,
                    f"docs-sym:{symbol_graph_id}:{sym_fp}",
                    {
                        "repo": repo_name,
                        "file_path": graph_sym.file_path,
                        "symbol_path": graph_sym.qualified_name,
                        "kind": (
                            graph_sym.kind.value
                            if hasattr(graph_sym.kind, "value")
                            else str(graph_sym.kind)
                        ),
                        "body": graph_sym.body or graph_sym.signature or graph_sym.qualified_name,
                        "signature": graph_sym.signature or graph_sym.qualified_name,
                        "doc_required": True,
                        "tags": [],
                    },
                )
                docs_svc.register_anchor(
                    docs_scope,
                    actor,
                    corr,
                    f"docs-anchor:{doc_id}:{ds_symbol.id}:{ds_symbol.body_hash[:16]}",
                    {
                        "doc_id": document.id,
                        "symbol_id": ds_symbol.id,
                        "recorded_hash": ds_symbol.body_hash,
                    },
                )
                with state_lock:
                    result.anchors_registered += 1
            except Exception as exc:
                with state_lock:
                    result.errors.append(f"{rel}: anchor failed for {symbol_graph_id}: {exc}")

        with state_lock:
            active_files.discard(rel)
        done = _bump()
        status = "unchanged" if body_unchanged and not evidence_added else "ok"
        _emit(done, file=rel, status=status)

    _emit(0, status="started")
    try:
        if prepared:
            run_parallel_file_jobs(workers=workers, items=prepared, fn=_process_one)
        _emit(progress_total, status="finished")
        return result
    finally:
        store = getattr(docs_svc, "store", None)
        close = getattr(store, "close", None)
        if callable(close):
            close()
        reset_connections = getattr(graph_service, "reset_database_connections", None)
        if callable(reset_connections):
            reset_connections()
