"""Repository tree walk ingest.

Role: discover sources, classify new/changed/stable, parallel ``ingest_file``.
SoT: FILE ``hash_value`` + persisted ``language``; durable graph store.
Invariants: prefer unindexed then changed; enqueue hash-stable when
``language`` is missing (legacy backfill) or FILE lacks CONTAINS children
(edge repair). Hash-stable files still participate in embedding self-healing.
Allowed failure: per-file errors collected; walk continues.
Forbidden: permanently skipping edgeless files or missing embedding rows.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from .parallel_files import run_parallel_file_jobs

from ...domain.enums import RelType, SymbolKind
from ...domain.errors import ValidationError
from ...domain.hashing import content_hash
from ...domain.models import (
    RepoIngestFileOutcome,
    RepoIngestResult,
    Scope,
)
from ...domain.package_manifests import load_package_aliases
from ...domain.ports import list_file_symbols_for_paths, list_symbols_compact
from ...domain.structural_integrity import file_needs_contains_repair
from ...domain.repo_discovery import (
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_FILES,
    discover_source_files,
)
from ...locked_store import sync_max_file_workers


class RepoIngestMixin:
    """Bulk ingest via discover_source_files + ingest_file."""

    def ingest_repo(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> RepoIngestResult:
        """Walk a repository root and ingest every supported source file.

        Reuses ``ingest_file`` per file. Failures are collected; the walk continues.
        Files are processed with a bounded worker pool; store mutations must be
        serialized by the caller (LockedStore in bootstrap).
        """
        root_path = str(payload.get("root_path") or "").strip()
        if not root_path:
            raise ValidationError("root_path is required")

        include_extensions = payload.get("include_extensions")
        exclude_dirs = payload.get("exclude_dirs")
        exclude_globs = payload.get("exclude_globs")
        reinclude_globs = payload.get("reinclude_globs")
        include_path_prefixes = payload.get("include_path_prefixes") or payload.get("include_paths")
        max_files = int(payload.get("max_files") or DEFAULT_MAX_FILES)
        max_file_bytes = int(payload.get("max_file_bytes") or DEFAULT_MAX_FILE_BYTES)
        include_outcomes = bool(payload.get("include_outcomes", True))
        on_progress_early = payload.get("on_progress")
        self._force_prune_removed_sources = bool(
            payload.get("force_prune_removed_sources", False)
        )

        def _emit_prep(detail: str, *, status: str = "preparing") -> None:
            if not callable(on_progress_early):
                return
            try:
                on_progress_early(
                    {
                        "phase": "ingest",
                        "done": 0,
                        "total": 0,
                        "status": status,
                        "file": detail,
                    }
                )
            except Exception:  # noqa: BLE001 — progress must never break ingest
                return

        _emit_prep("discovering source files", status="discovering")
        # Small explicit batches (MCP tool budgets): stop walking once we have a pool.
        # Full CLI sync keeps uncapped discovery for accurate truncate/prune signals.
        import time

        discovery_limit = None
        discovery_deadline = None
        if max_files < DEFAULT_MAX_FILES:
            discovery_limit = max(max_files * 25, max_files)
            # Leave headroom under typical MCP HTTP tool budgets (~25s).
            discovery_deadline = time.monotonic() + 8.0
        discovered = discover_source_files(
            root_path,
            include_extensions=include_extensions,
            exclude_dirs=exclude_dirs,
            exclude_globs=exclude_globs,
            reinclude_globs=reinclude_globs,
            include_path_prefixes=include_path_prefixes,
            max_files=discovery_limit,
            max_file_bytes=max_file_bytes,
            deadline_monotonic=discovery_deadline,
        )

        discovered_paths = {
            item.relative_path.replace("\\", "/") for item in discovered
        }
        _emit_prep("loading indexed symbols for change detection")
        preloaded = payload.get("preloaded_symbols")
        if preloaded is not None:
            stored_symbols = list(preloaded)
        elif discovery_limit is not None:
            # MCP small batches: only fetch FILE nodes for discovered paths.
            # Full list_symbols_index on large graphs exceeds the HTTP tool budget.
            stored_symbols = list_file_symbols_for_paths(
                self.store,
                scope,
                [item.relative_path.replace("\\", "/") for item in discovered],
            )
        else:
            stored_symbols = list_symbols_compact(self.store, scope)
        # Never prune against a capped discovery walk — that would delete real files.
        if discovered_paths and not include_path_prefixes and discovery_limit is None:
            stored_symbols = self._prune_removed_source_symbols(
                scope,
                stored_symbols=stored_symbols,
                discovered_paths=discovered_paths,
            )
        indexed_files = {
            s.file_path.replace("\\", "/"): s
            for s in stored_symbols
            if s.kind == SymbolKind.FILE and s.file_path and not s.file_path.startswith("__astloom__/")
        }
        indexed_paths = set(indexed_files)
        unindexed = [d for d in discovered if d.relative_path.replace("\\", "/") not in indexed_paths]
        known = [d for d in discovered if d.relative_path.replace("\\", "/") in indexed_paths]

        def _known_changed(item: Any) -> bool:
            previous = indexed_files[item.relative_path.replace("\\", "/")]
            try:
                source = Path(item.absolute_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return True
            current = content_hash(source, item.language)
            return (
                current["hash"] != previous.hash_value
                or current["hash_version"] != previous.hash_version
                or current["parser_version"] != previous.parser_version
            )

        def _needs_edge_repair(item: Any) -> bool:
            rel = item.relative_path.replace("\\", "/")
            previous = indexed_files[rel]
            return file_needs_contains_repair(
                self.store,
                scope,
                file_id=previous.id,
                file_path=rel,
            )

        # Prefer never-indexed; then changed; then lang backfill / edge repair.
        # Early-exit once the worker queue is full — full-tree hash/CONTAINS scans
        # previously made MCP ``sync`` with small max_files exceed the tool budget.
        selected: list = []
        changed_known: list = []
        language_backfill: list = []
        edge_repair: list = []
        hash_stable_skip: list = []
        selected.extend(unindexed[:max_files])
        known_exhausted = True
        if len(selected) < max_files and known:
            _emit_prep("checking changed / repair queue")
            for item in known:
                if len(selected) >= max_files:
                    known_exhausted = False
                    break
                rel = item.relative_path.replace("\\", "/")
                previous = indexed_files[rel]
                if _known_changed(item):
                    changed_known.append(item)
                    selected.append(item)
                    continue
                # Small MCP batches: skip language/edge-repair scans (each can be
                # multi-second Neo4j round-trips). Full CLI sync still heals them.
                if discovery_limit is not None:
                    hash_stable_skip.append(item)
                    continue
                if not str(previous.language or "").strip():
                    language_backfill.append(item)
                    selected.append(item)
                    continue
                if _needs_edge_repair(item):
                    edge_repair.append(item)
                    selected.append(item)
                    continue
                hash_stable_skip.append(item)

        changed_known_paths = {item.relative_path.replace("\\", "/") for item in changed_known}
        backfill_paths = {item.relative_path.replace("\\", "/") for item in language_backfill}
        selected_paths = {item.relative_path.replace("\\", "/") for item in selected}
        pending_paths = {
            item.relative_path.replace("\\", "/") for item in [*unindexed, *changed_known]
        }
        truncated = (
            len(unindexed) > max_files
            or not known_exhausted
            or not pending_paths.issubset(selected_paths)
            or (
                discovery_limit is not None
                and len(discovered_paths) >= discovery_limit
            )
        )
        discovered = selected
        queue_new = sum(
            1
            for item in selected
            if item.relative_path.replace("\\", "/") not in indexed_paths
        )
        queue_changed = sum(
            1
            for item in selected
            if item.relative_path.replace("\\", "/") in changed_known_paths
        )
        queue_unchanged = max(0, len(selected) - queue_new - queue_changed)
        prior_indexed = len(known)
        queue_meta = {
            "prior_indexed": prior_indexed,
            "queue_new": queue_new,
            "queue_changed": queue_changed,
            "queue_unchanged": queue_unchanged,
        }

        package_aliases = load_package_aliases(root_path)

        outcomes: list[RepoIngestFileOutcome] = []
        totals = {
            "ingested": 0,
            "failed": 0,
            # Count hash-stable skips without visiting workers (still "up to date").
            "skipped": len(hash_stable_skip),
            "symbols_indexed": 0,
            "symbols_changed": 0,
            "symbols_documented": 0,
            "edges_written": 0,
            "chars_read": 0,
        }
        on_progress = payload.get("on_progress")
        total_files = len(discovered)
        # done/total = files this run actually visits (new/changed/lang_backfill).
        progress_total = total_files
        state_lock = threading.Lock()
        progress_done = 0
        active_files: set[str] = set()
        workers = min(sync_max_file_workers(), max(1, total_files or 1))
        # Small MCP-style batches: skip whole-graph index build / finalize (tool budget).
        # Must pass empty indexes (not None): file_ingest rebuilds full indexes when
        # shared_resolution.indexes is None, which blew the 25s MCP tool budget.
        skip_heavy_graph_pass = discovery_limit is not None
        if callable(on_progress):
            try:
                on_progress(
                    {
                        "phase": "ingest",
                        "done": 0,
                        "total": 0,
                        "status": "preparing",
                        "file": (
                            "skipping resolution indexes (small batch)"
                            if skip_heavy_graph_pass
                            else "building resolution indexes"
                        ),
                    }
                )
            except Exception:  # noqa: BLE001 — progress must never break ingest
                pass
        if skip_heavy_graph_pass:
            from ...domain.cross_language import build_symbol_indexes

            shared_resolution = {
                "indexes": build_symbol_indexes([]),
                "by_qualified": {},
                "short_names": {},
                "routes_by_path": {},
            }
        else:
            shared_resolution = {
                "indexes": None,
                "by_qualified": {},
                "short_names": {},
            }
            try:
                indexes, by_qualified, short_names, routes_by_path = self._resolution_indexes(scope)
                shared_resolution = {
                    "indexes": indexes,
                    "by_qualified": by_qualified,
                    "short_names": short_names,
                    "routes_by_path": routes_by_path,
                }
            except Exception:  # noqa: BLE001 — empty graph / store ok on cold start
                pass

        def _rpm_progress_fields() -> dict[str, Any]:
            llm = getattr(self, "llm", None)
            snap_fn = getattr(llm, "rpm_sessions_snapshot", None) if llm is not None else None
            if not callable(snap_fn):
                return {}
            try:
                snap = snap_fn()
            except Exception:  # noqa: BLE001
                return {}
            return {
                "rpm": int(snap.get("rpm") or 0),
                "rpm_inflight_cap": int(snap.get("inflight_cap") or 0),
                "rpm_inflight": int(snap.get("inflight_count") or 0),
                "rpm_starts_in_window": int(snap.get("starts_in_window") or 0),
            }

        def _bump_progress(_rel: str) -> int:
            nonlocal progress_done
            progress_done += 1
            return progress_done

        def _emit(done: int, *, file: str = "", status: str = "") -> None:
            if not callable(on_progress):
                return
            try:
                with state_lock:
                    snap_totals = dict(totals)
                    in_flight_paths = sorted(active_files)
                event = {
                    "phase": "ingest",
                    "done": done,
                    "total": progress_total,
                    "file": file,
                    "status": status,
                    # done/total = visited files; queue_unchanged = language backfill only.
                    "prior_indexed": int(queue_meta["prior_indexed"]),
                    "queue_new": int(queue_meta["queue_new"]),
                    "queue_changed": int(queue_meta["queue_changed"]),
                    "queue_unchanged": int(queue_meta["queue_unchanged"]),
                    "files_ingested": snap_totals["ingested"],
                    "files_failed": snap_totals["failed"],
                    "files_skipped": snap_totals["skipped"],
                    "symbols_indexed": snap_totals["symbols_indexed"],
                    "symbols_changed": snap_totals["symbols_changed"],
                    "edges_written": snap_totals["edges_written"],
                    "chars_read": snap_totals["chars_read"],
                    "approx_tokens": snap_totals["chars_read"] // 4,
                    "files_in_flight": len(in_flight_paths),
                    "files_in_flight_paths": in_flight_paths[:8],
                    "file_workers": workers,
                }
                event.update(_rpm_progress_fields())
                on_progress(event)
            except Exception:  # noqa: BLE001 — progress must never break ingest
                return

        def _process_one(_index: int, item: Any) -> None:
            rel = item.relative_path
            with state_lock:
                active_files.add(rel)
                done_now = progress_done
            _emit(done_now, file=rel, status="active")
            try:
                text = Path(item.absolute_path).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                with state_lock:
                    totals["skipped"] += 1
                    done = _bump_progress(rel)
                    active_files.discard(rel)
                    if include_outcomes:
                        outcomes.append(
                            RepoIngestFileOutcome(
                                relative_path=rel,
                                language=item.language,
                                status="skipped",
                                detail="not_utf8",
                            )
                        )
                _emit(done, file=rel, status="skipped")
                return
            except OSError as exc:
                with state_lock:
                    totals["failed"] += 1
                    done = _bump_progress(rel)
                    active_files.discard(rel)
                    if include_outcomes:
                        outcomes.append(
                            RepoIngestFileOutcome(
                                relative_path=rel,
                                language=item.language,
                                status="failed",
                                detail=f"read_error:{exc}",
                            )
                        )
                _emit(done, file=rel, status="failed")
                return

            hashed = content_hash(text, item.language)
            file_key = (
                f"{idempotency_key}:{rel}:{hashed['hash']}:"
                f"{hashed['hash_version']}:{hashed['parser_version']}"
            )

            def _on_symbol_progress(event: dict[str, Any], *, _rel: str = rel) -> None:
                # Mid-file heartbeat so the bar/symbols move while LLM/embed runs.
                if not callable(on_progress):
                    return
                try:
                    with state_lock:
                        # Provisional: count documented symbols before file completes.
                        delta = int(event.get("symbols_done") or 0)
                        snap_totals = dict(totals)
                        # Show at least this file's in-progress symbols without
                        # double-counting completed files (totals already include them).
                        provisional_symbols = snap_totals["symbols_indexed"] + delta
                        in_flight_paths = sorted(active_files)
                        done_now = progress_done
                    on_progress(
                        {
                            "phase": "ingest",
                            "done": done_now,
                            "total": progress_total,
                            "file": _rel,
                            "status": str(event.get("status") or "active"),
                            "prior_indexed": int(queue_meta["prior_indexed"]),
                            "queue_new": int(queue_meta["queue_new"]),
                            "queue_changed": int(queue_meta["queue_changed"]),
                            "queue_unchanged": int(queue_meta["queue_unchanged"]),
                            "files_ingested": snap_totals["ingested"],
                            "files_failed": snap_totals["failed"],
                            "files_skipped": snap_totals["skipped"],
                            "symbols_indexed": provisional_symbols,
                            "symbols_changed": snap_totals["symbols_changed"] + delta,
                            "edges_written": snap_totals["edges_written"],
                            "chars_read": snap_totals["chars_read"] + len(text),
                            "approx_tokens": (snap_totals["chars_read"] + len(text)) // 4,
                            "files_in_flight": len(in_flight_paths),
                            "files_in_flight_paths": in_flight_paths[:8],
                            "file_workers": workers,
                            **_rpm_progress_fields(),
                        }
                    )
                except Exception:  # noqa: BLE001
                    return

            try:
                result = self.ingest_file(
                    scope,
                    actor_id,
                    correlation_id,
                    file_key,
                    {
                        "file_path": rel,
                        "source": text,
                        "language": item.language,
                        "package_aliases": package_aliases,
                        "defer_cross_file_pass": True,
                        "language_backfill_only": rel in backfill_paths,
                        "reuse_unchanged_embeddings": True,
                        # Small batches: heuristic docs only (LLM would exceed MCP budgets).
                        "prefer_heuristic_docs": skip_heavy_graph_pass,
                        # Heal embeddings later via embedding_refresh / sync heal.
                        "skip_embeddings": skip_heavy_graph_pass
                        or str(payload.get("embedding_refresh_mode") or "").strip().lower()
                        in {"off", "skip", "none", "disabled"},
                        "shared_resolution": shared_resolution,
                        "on_symbol_progress": _on_symbol_progress,
                    },
                )
            except Exception as exc:  # noqa: BLE001 — soft-fail per file for bulk jobs
                with state_lock:
                    totals["failed"] += 1
                    done = _bump_progress(rel)
                    active_files.discard(rel)
                    if include_outcomes:
                        outcomes.append(
                            RepoIngestFileOutcome(
                                relative_path=rel,
                                language=item.language,
                                status="failed",
                                detail=str(exc)[:500],
                            )
                        )
                _emit(done, file=rel, status="failed")
                return

            unchanged = (
                result.symbols_indexed == 0
                and result.symbols_changed == 0
                and result.edges_written == 0
            )
            with state_lock:
                if unchanged:
                    totals["skipped"] += 1
                else:
                    totals["ingested"] += 1
                totals["chars_read"] += len(text)
                totals["symbols_indexed"] += result.symbols_indexed
                totals["symbols_changed"] += result.symbols_changed
                totals["symbols_documented"] += result.symbols_documented
                totals["edges_written"] += result.edges_written
                done = _bump_progress(rel)
                active_files.discard(rel)
                if include_outcomes:
                    outcomes.append(
                        RepoIngestFileOutcome(
                            relative_path=rel,
                            language=item.language,
                            status="unchanged" if unchanged else "ok",
                            file_id=result.file_id,
                            symbols_indexed=result.symbols_indexed,
                            symbols_changed=result.symbols_changed,
                            symbols_documented=result.symbols_documented,
                            edges_written=result.edges_written,
                        )
                    )
            _emit(done, file=rel, status="unchanged" if unchanged else "ok")

        _emit(0, status="started")
        if total_files:
            run_parallel_file_jobs(workers=workers, items=discovered, fn=_process_one)
            if not skip_heavy_graph_pass:
                _emit(progress_total, status="finalizing", file="cross-file resolution")
                try:
                    finals = self.finalize_cross_file_resolution(
                        scope,
                        package_aliases=package_aliases,
                        on_progress=lambda ev: _emit(
                            progress_total,
                            file=str(ev.get("file") or "cross-file resolution"),
                            status=str(ev.get("status") or "finalizing"),
                        ),
                    )
                    with state_lock:
                        totals["edges_written"] += int(finals or 0)
                except Exception:  # noqa: BLE001 — finalize must not fail the ingest walk
                    pass

        resolved_root = str(Path(root_path).expanduser().resolve())
        # Package README maps only when this run visited files (avoid noop graph walks).
        if total_files and not skip_heavy_graph_pass:
            try:
                readme_edges = self._ingest_package_readme_maps(scope, resolved_root)
                totals["edges_written"] += readme_edges
            except Exception:  # noqa: BLE001 — package README ingest must not fail the repo walk
                pass
        # Emit ingest finished before embedding heal (heal uses phase=embeddings).
        _emit(progress_done if total_files else 0, status="finished")
        # Heal embeddings for files this run visited — not the whole project backlog
        # unless embedding_refresh_mode=full (astloom sync heal).
        touched_paths = [item.relative_path for item in discovered]
        embedding_refresh = self.refresh_embeddings_after_ingest(
            scope,
            file_paths=touched_paths,
            mode=str(payload.get("embedding_refresh_mode") or "touched"),
            on_progress=on_progress if callable(on_progress) else None,
        ).public()

        return RepoIngestResult(
            root_path=resolved_root,
            files_discovered=len(discovered),
            files_ingested=totals["ingested"],
            files_failed=totals["failed"],
            files_skipped=totals["skipped"],
            symbols_indexed=totals["symbols_indexed"],
            symbols_changed=totals["symbols_changed"],
            symbols_documented=totals["symbols_documented"],
            edges_written=totals["edges_written"],
            truncated=truncated,
            outcomes=outcomes,
            embedding_refresh=embedding_refresh,
        )

    def _prune_removed_source_symbols(
        self,
        scope: Scope,
        *,
        stored_symbols: list[Any],
        discovered_paths: set[str],
    ) -> list[Any]:
        indexed_paths = {
            str(symbol.file_path or "").replace("\\", "/")
            for symbol in stored_symbols
            if symbol.kind == SymbolKind.FILE and symbol.file_path
        }
        stale_paths = indexed_paths - discovered_paths
        # Circuit breaker: a huge prune usually means discovery/excludes drifted,
        # not that half the repo was deleted. Refuse rather than wipe the graph.
        if indexed_paths and stale_paths:
            force_prune = bool(getattr(self, "_force_prune_removed_sources", False))
            threshold = max(50, int(0.2 * len(indexed_paths)))
            if not force_prune and len(stale_paths) > threshold:
                sample = ", ".join(sorted(stale_paths)[:8])
                if len(stale_paths) > 8:
                    sample += ", …"
                raise RuntimeError(
                    "refusing to prune "
                    f"{len(stale_paths)}/{len(indexed_paths)} indexed files "
                    f"(threshold {threshold}); check sync discovery/excludes "
                    f"or set force_prune_removed_sources. sample: {sample}"
                )
        live_ids = {symbol.id for symbol in stored_symbols}
        owned_kinds = {
            SymbolKind.FILE,
            SymbolKind.CLASS,
            SymbolKind.FUNCTION,
            SymbolKind.METHOD,
            SymbolKind.DOCUMENTATION,
            SymbolKind.ROUTE,
            SymbolKind.RATIONALE,
        }
        stale_ids = {
            symbol.id
            for symbol in stored_symbols
            if symbol.kind in owned_kinds
            and str(symbol.file_path or "").replace("\\", "/") in stale_paths
        }
        generated_prefix = f"doc:{scope.project_id}:"
        human_prefix = f"doc:human:{scope.project_id}:"
        for symbol in stored_symbols:
            if symbol.kind != SymbolKind.DOCUMENTATION:
                continue
            if not symbol.id.startswith(generated_prefix) or symbol.id.startswith(
                human_prefix
            ):
                continue
            code_id = f"sym:{scope.project_id}:{symbol.id.removeprefix(generated_prefix)}"
            if code_id not in live_ids:
                stale_ids.add(symbol.id)
        if not stale_ids:
            return stored_symbols

        ids = sorted(stale_ids)
        if self.embedding_index is not None:
            delete_many = getattr(self.embedding_index, "delete_many", None)
            if callable(delete_many):
                delete_many(scope, ids)
                for symbol_id in ids:
                    self._sync_vector_replica_delete(symbol_id)
            else:
                for symbol_id in ids:
                    self._delete_embedding(scope, symbol_id)
        delete_symbols = getattr(self.store, "delete_symbols", None)
        if callable(delete_symbols):
            delete_symbols(ids, scope)
        else:
            for symbol_id in ids:
                self.store.delete_symbol(symbol_id, scope)
        return [symbol for symbol in stored_symbols if symbol.id not in stale_ids]

    def _ingest_package_readme_maps(self, scope: Scope, root_path: str) -> int:
        """Index near-code package README maps as human DOCUMENTATION + DOCUMENTED_BY from FILEs."""
        root = Path(root_path)
        if not root.is_dir():
            return 0
        skip_parts = {
            ".git",
            "node_modules",
            ".venv",
            "venv",
            "__pycache__",
            "dist",
            "build",
            "vendor",
            ".tox",
        }
        upsert = getattr(self, "upsert_human_documentation", None)
        put_edge = getattr(self, "_put_edge", None)
        if not callable(upsert) or not callable(put_edge):
            return 0

        files_by_parent: dict[str, list[Any]] = {}
        for symbol in list_symbols_compact(self.store, scope):
            if symbol.kind != SymbolKind.FILE:
                continue
            parent_dir = str(Path((symbol.file_path or "").replace("\\", "/")).parent)
            if parent_dir in {".", ""}:
                parent_dir = ""
            files_by_parent.setdefault(parent_dir, []).append(symbol)

        edges = 0
        for readme in root.rglob("README.md"):
            try:
                rel = readme.relative_to(root).as_posix()
            except ValueError:
                continue
            if set(rel.split("/")) & skip_parts:
                continue
            parent = readme.parent
            dir_prefix = str(Path(rel).parent).replace("\\", "/")
            if dir_prefix in {".", ""}:
                dir_prefix = ""
            file_symbols = files_by_parent.get(dir_prefix, ())
            if not file_symbols:
                continue
            try:
                body = readme.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if len(body.strip()) < 40:
                continue
            doc_id = f"package-readme:{rel}"
            result = upsert(
                scope,
                doc_id=doc_id,
                relative_path=rel,
                body=body[:8000],
                title=f"Package map: {parent.name}",
                linked_symbol_tokens=[],
                metadata={"origin": "package_readme", "provenance": "package_folder_readme"},
            )
            doc_sid = str(result.get("doc_symbol_id") or "")
            if not doc_sid:
                continue
            for sym in file_symbols:
                fp = (sym.file_path or "").replace("\\", "/")
                edges += put_edge(
                    scope,
                    RelType.DOCUMENTED_BY.value,
                    sym.id,
                    doc_sid,
                    file_path=fp,
                    metadata={"doc_id": doc_id, "origin": "package_readme"},
                    link_key=f"package_readme:{doc_id}:{sym.id}",
                )
        return edges
