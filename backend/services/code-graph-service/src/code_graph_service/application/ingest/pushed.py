"""Ingest file bodies supplied by a client (no on-server tree walk).

Role: index pushed ``{file_path, source}`` records into the graph.
SoT: same FILE hash + symbols as ``ingest_file``; prune only when
  ``inventory_complete=true`` with ``present_paths`` (explicit full inventory).
Invariants: only safe repo-relative paths; enforce max_files / max_file_bytes;
  never log full source bodies; ``present_paths`` alone never deletes.
Allowed: soft-fail per oversize/empty file; empty ``files`` with prune-only is valid.
Forbidden: path traversal / absolute paths; requiring ``root_path`` on disk;
  writing durable checkout mirrors; pruning on partial/scoped inventories.
"""

from __future__ import annotations

import threading
from typing import Any

from .parallel_files import run_parallel_file_jobs
from ...domain.enums import SymbolKind
from ...domain.errors import ClientDisconnected, ValidationError
from ...domain.hashing import content_hash
from ...domain.languages import detect_language_from_path
from ...domain.models import RepoIngestFileOutcome, RepoIngestResult
from ...domain.path_safety import safe_repo_rel_path
from ...domain.repo_discovery import DEFAULT_MAX_FILE_BYTES, DEFAULT_MAX_FILES
from ...locked_store import sync_max_file_workers


class PushedIngestMixin:
    """Bulk ingest from in-memory file payloads (client push / HTTP)."""

    def ingest_pushed_sources(
        self,
        scope: Any,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
        *,
        should_cancel: Any = None,
    ) -> RepoIngestResult:
        raw_files = payload.get("files")
        if raw_files is None:
            raise ValidationError("files is required (use [] for prune-only)")
        if not isinstance(raw_files, list):
            raise ValidationError("files must be a list")

        max_files = int(payload.get("max_files") or DEFAULT_MAX_FILES)
        if max_files < 1 or max_files > 20_000:
            raise ValidationError("max_files out of range")
        max_file_bytes = int(payload.get("max_file_bytes") or DEFAULT_MAX_FILE_BYTES)
        if max_file_bytes < 1024 or max_file_bytes > 20_000_000:
            raise ValidationError("max_file_bytes out of range")
        if len(raw_files) > max_files:
            raise ValidationError(
                f"files list exceeds max_files={max_files} (got {len(raw_files)})"
            )

        present_raw = payload.get("present_paths")
        present_paths: set[str] | None = None
        if present_raw is not None:
            if not isinstance(present_raw, list):
                raise ValidationError("present_paths must be a list when set")
            if len(present_raw) > max_files:
                raise ValidationError(
                    f"present_paths exceeds max_files={max_files} (got {len(present_raw)})"
                )
            present_paths = set()
            for raw in present_raw:
                if not str(raw).strip():
                    continue
                present_paths.add(safe_repo_rel_path(str(raw)))

        # Fail-closed: present_paths without inventory_complete must not prune.
        # Partial/scoped client syncs often send a subset; deleting the rest wiped
        # previously ingested files (root cause of "reprocessed / missing graph").
        inventory_complete = bool(payload.get("inventory_complete"))
        if present_paths is not None and not inventory_complete:
            present_paths = None

        include_outcomes = bool(payload.get("include_outcomes", True))
        on_progress = payload.get("on_progress")
        package_aliases: dict[str, Any] = dict(payload.get("package_aliases") or {})
        if callable(on_progress):
            try:
                on_progress(
                    {
                        "phase": "ingest",
                        "done": 0,
                        "total": 0,
                        "status": "preparing",
                        "file": "building resolution indexes",
                        "file_workers": sync_max_file_workers(),
                    }
                )
            except Exception:  # noqa: BLE001
                pass

        # Full symbol dump is only required for inventory-complete prune.
        if present_paths is not None:
            prune_lister = getattr(self.store, "list_symbols_index", None)
            if not callable(prune_lister):
                prune_lister = self.store.list_symbols
            stored_symbols = list(prune_lister(scope))
            self._prune_removed_source_symbols(
                scope,
                stored_symbols=stored_symbols,
                discovered_paths=present_paths,
            )

        outcomes: list[RepoIngestFileOutcome] = []
        totals = {
            "ingested": 0,
            "failed": 0,
            "skipped": 0,
            "symbols_indexed": 0,
            "symbols_changed": 0,
            "symbols_documented": 0,
            "edges_written": 0,
            "chars_read": 0,
        }

        items: list[tuple[str, str, str]] = []
        for entry in raw_files:
            if not isinstance(entry, dict):
                raise ValidationError("each files[] entry must be an object")
            rel = safe_repo_rel_path(str(entry.get("file_path") or ""))
            source = entry.get("source")
            if not isinstance(source, str):
                source = "" if source is None else str(source)
            language = str(entry.get("language") or "").strip() or (
                detect_language_from_path(rel) or "python"
            )
            if len(source.encode("utf-8", errors="replace")) > max_file_bytes:
                totals["failed"] += 1
                if include_outcomes:
                    outcomes.append(
                        RepoIngestFileOutcome(
                            relative_path=rel,
                            language=language,
                            status="failed",
                            detail=f"exceeds_max_file_bytes:{max_file_bytes}",
                        )
                    )
                continue
            items.append((rel, source, language))

        workers = min(sync_max_file_workers(), max(1, len(items) or 1))
        state_lock = threading.Lock()
        progress_done = 0
        progress_total = len(items)
        active_files: set[str] = set()
        shared_resolution: dict[str, Any] = {
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
        except Exception:  # noqa: BLE001
            pass

        def _bump() -> int:
            nonlocal progress_done
            progress_done += 1
            return progress_done

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

        def _emit(done: int, *, file: str = "", status: str = "") -> None:
            if not callable(on_progress):
                return
            try:
                with state_lock:
                    snap = dict(totals)
                    in_flight_paths = sorted(active_files)
                event = {
                    "phase": "ingest",
                    "done": done,
                    "total": progress_total,
                    "file": file,
                    "status": status,
                    "files_ingested": snap["ingested"],
                    "files_failed": snap["failed"],
                    "files_skipped": snap["skipped"],
                    "symbols_indexed": snap["symbols_indexed"],
                    "symbols_changed": snap["symbols_changed"],
                    "edges_written": snap["edges_written"],
                    "chars_read": snap["chars_read"],
                    "approx_tokens": snap["chars_read"] // 4,
                    "files_in_flight": len(in_flight_paths),
                    "files_in_flight_paths": in_flight_paths[:8],
                    "file_workers": workers,
                }
                event.update(_rpm_progress_fields())
                on_progress(event)
            except Exception:  # noqa: BLE001
                return

        def _process_one(_index: int, item: tuple[str, str, str]) -> None:
            rel, text, language = item
            with state_lock:
                active_files.add(rel)
            _emit(progress_done, file=rel, status="active")
            if not text.strip():
                with state_lock:
                    totals["skipped"] += 1
                    done = _bump()
                    active_files.discard(rel)
                    if include_outcomes:
                        outcomes.append(
                            RepoIngestFileOutcome(
                                relative_path=rel,
                                language=language,
                                status="skipped",
                                detail="empty_source",
                            )
                        )
                _emit(done, file=rel, status="skipped")
                return
            hashed = content_hash(text, language)
            file_key = (
                f"{idempotency_key}:{rel}:{hashed['hash']}:"
                f"{hashed['hash_version']}:{hashed['parser_version']}"
            )

            def _on_symbol_progress(event: dict[str, Any], *, _rel: str = rel) -> None:
                if not callable(on_progress):
                    return
                try:
                    with state_lock:
                        delta = int(event.get("symbols_done") or 0)
                        snap = dict(totals)
                        provisional_symbols = snap["symbols_indexed"] + delta
                        in_flight_paths = sorted(active_files)
                        done_now = progress_done
                    on_progress(
                        {
                            "phase": "ingest",
                            "done": done_now,
                            "total": progress_total,
                            "file": _rel,
                            "status": str(event.get("status") or "active"),
                            "files_ingested": snap["ingested"],
                            "files_failed": snap["failed"],
                            "files_skipped": snap["skipped"],
                            "symbols_indexed": provisional_symbols,
                            "symbols_changed": snap["symbols_changed"] + delta,
                            "edges_written": snap["edges_written"],
                            "chars_read": snap["chars_read"] + len(text),
                            "approx_tokens": (snap["chars_read"] + len(text)) // 4,
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
                        "language": language,
                        "package_aliases": package_aliases,
                        "defer_cross_file_pass": True,
                        "reuse_unchanged_embeddings": True,
                        "shared_resolution": shared_resolution,
                        "on_symbol_progress": _on_symbol_progress,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                with state_lock:
                    totals["failed"] += 1
                    done = _bump()
                    active_files.discard(rel)
                    if include_outcomes:
                        outcomes.append(
                            RepoIngestFileOutcome(
                                relative_path=rel,
                                language=language,
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
                done = _bump()
                active_files.discard(rel)
                if include_outcomes:
                    outcomes.append(
                        RepoIngestFileOutcome(
                            relative_path=rel,
                            language=language,
                            status="unchanged" if unchanged else "ok",
                            file_id=result.file_id,
                            symbols_indexed=result.symbols_indexed,
                            symbols_changed=result.symbols_changed,
                            symbols_documented=result.symbols_documented,
                            edges_written=result.edges_written,
                        )
                    )
            _emit(done, file=rel, status="unchanged" if unchanged else "ok")

        def _cancelled() -> bool:
            return callable(should_cancel) and bool(should_cancel())

        _emit(0, status="started")
        if items:
            run_parallel_file_jobs(
                workers=workers,
                items=items,
                fn=_process_one,
                should_cancel=_cancelled if should_cancel is not None else None,
            )
            if _cancelled():
                raise ClientDisconnected()
            # Multi-batch content-push: only the last batch should finalize the
            # whole project graph (intermediate finalize was N× Neo4j relink cost).
            do_finalize = bool(payload.get("finalize_cross_file", True))
            if do_finalize:
                _emit(
                    progress_total if items else 0,
                    status="finalizing",
                    file="cross-file resolution",
                )
                try:
                    finals = self.finalize_cross_file_resolution(
                        scope,
                        package_aliases=package_aliases,
                        on_progress=lambda ev: _emit(
                            progress_total if items else 0,
                            file=str(ev.get("file") or "cross-file resolution"),
                            status=str(ev.get("status") or "finalizing"),
                        ),
                    )
                    with state_lock:
                        totals["edges_written"] += int(finals or 0)
                except Exception:  # noqa: BLE001
                    pass

        if _cancelled():
            raise ClientDisconnected()

        refresh_mode = str(payload.get("embedding_refresh_mode") or "touched").strip().lower()
        if refresh_mode in {"", "none", "off", "skip"}:
            embedding_refresh = {"mode": "skipped", "refreshed": 0}
        else:
            embedding_refresh = self.refresh_embeddings_after_ingest(
                scope,
                file_paths=[rel for rel, _, _ in items],
                mode=refresh_mode,
                on_progress=on_progress if callable(on_progress) else None,
            ).public()

        return RepoIngestResult(
            root_path="",
            files_discovered=len(present_paths) if present_paths is not None else len(items),
            files_ingested=totals["ingested"],
            files_failed=totals["failed"],
            files_skipped=totals["skipped"],
            symbols_indexed=totals["symbols_indexed"],
            symbols_changed=totals["symbols_changed"],
            symbols_documented=totals["symbols_documented"],
            edges_written=totals["edges_written"],
            truncated=False,
            outcomes=outcomes,
            embedding_refresh=embedding_refresh,
        )

    def file_content_hashes(self, scope: Any) -> dict[str, str]:
        """Map relative FILE paths → stored content ``hash_value`` for client skip."""
        files, _docs = self.content_hash_maps(scope)
        return files

    def content_hash_maps(self, scope: Any) -> tuple[dict[str, str], dict[str, str]]:
        """Return ``(file_hashes, human_doc_hashes)`` for unchanged-content skip.

        FILE hashes publish when the file has code children, or when ingest
        stamped ``metadata.ingest_complete`` (constants-only modules).
        Prefer a store-native map (Neo4j Cypher) over a full ``list_symbols`` dump.
        """
        from ...domain.structural_integrity import file_content_hash_publishable

        native = getattr(self.store, "content_hash_maps", None)
        if callable(native):
            try:
                return native(scope)
            except TypeError:
                pass
        files: dict[str, Any] = {}
        children: set[str] = set()
        docs: dict[str, str] = {}
        child_kinds = {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS}
        lister = getattr(self.store, "list_symbols_index", None)
        if not callable(lister):
            lister = self.store.list_symbols
        for symbol in lister(scope):
            kind = getattr(symbol, "kind", None)
            path = str(getattr(symbol, "file_path", "") or "").replace("\\", "/")
            digest = str(getattr(symbol, "hash_value", "") or "").strip()
            if not path:
                continue
            if kind == SymbolKind.FILE:
                files[path] = symbol
            elif kind in child_kinds:
                children.add(path)
            elif (
                kind == SymbolKind.DOCUMENTATION
                and str(getattr(symbol, "id", "")).startswith("doc:human:")
                and digest
            ):
                docs[path] = digest
        out: dict[str, str] = {}
        for path, symbol in files.items():
            digest = str(getattr(symbol, "hash_value", "") or "").strip()
            if file_content_hash_publishable(
                digest=digest,
                has_code_children=path in children,
                metadata=getattr(symbol, "metadata", None),
            ):
                out[path] = digest
        return out, docs
