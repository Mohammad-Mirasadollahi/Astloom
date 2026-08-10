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
        discovered = discover_source_files(
            root_path,
            include_extensions=include_extensions,
            exclude_dirs=exclude_dirs,
            exclude_globs=exclude_globs,
            reinclude_globs=reinclude_globs,
            include_path_prefixes=include_path_prefixes,
            max_files=None,
            max_file_bytes=max_file_bytes,
        )

        discovered_paths = {
            item.relative_path.replace("\\", "/") for item in discovered
        }
        _emit_prep("loading indexed symbols for change detection")
        stored_symbols = list(self.store.list_symbols(scope))
        if discovered_paths and not include_path_prefixes:
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

        changed_known = [item for item in known if _known_changed(item)]
        changed_known_paths = {item.relative_path.replace("\\", "/") for item in changed_known}
        unchanged_known = [
            item
            for item in known
            if item.relative_path.replace("\\", "/") not in changed_known_paths
        ]
        # Hash-stable + language already set → skip workers unless CONTAINS missing.
        # Hash-stable + empty language → enqueue for legacy language backfill.
        # Hash-stable + edgeless FILE → enqueue for structural edge repair.
        language_backfill = [
            item
            for item in unchanged_known
            if not str(
                indexed_files[item.relative_path.replace("\\", "/")].language or ""
            ).strip()
        ]
        backfill_paths = {
            item.relative_path.replace("\\", "/") for item in language_backfill
        }

        def _needs_edge_repair(item: Any) -> bool:
            rel = item.relative_path.replace("\\", "/")
            previous = indexed_files[rel]
            return file_needs_contains_repair(
                self.store,
                scope,
                file_id=previous.id,
                file_path=rel,
            )

        _emit_prep("checking structural edge repair queue")
        edge_repair = [
            item
            for item in unchanged_known
            if item.relative_path.replace("\\", "/") not in backfill_paths
            and _needs_edge_repair(item)
        ]
        repair_paths = {
            item.relative_path.replace("\\", "/") for item in edge_repair
        }
        hash_stable_skip = [
            item
            for item in unchanged_known
            if item.relative_path.replace("\\", "/") not in backfill_paths
            and item.relative_path.replace("\\", "/") not in repair_paths
        ]
        # Prefer never-indexed files; then changed; then lang backfill / edge repair.
        selected: list = []
        selected.extend(unindexed[:max_files])
        remaining = max_files - len(selected)
        if remaining > 0:
            selected.extend(changed_known[:remaining])
        remaining = max_files - len(selected)
        if remaining > 0:
            selected.extend(language_backfill[:remaining])
        remaining = max_files - len(selected)
        if remaining > 0:
            selected.extend(edge_repair[:remaining])
        selected_paths = {item.relative_path.replace("\\", "/") for item in selected}
        pending_paths = {
            item.relative_path.replace("\\", "/") for item in [*unindexed, *changed_known]
        }
        truncated = not pending_paths.issubset(selected_paths)
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
        shared_resolution = {
            "indexes": None,
            "by_qualified": {},
            "short_names": {},
        }
        if callable(on_progress):
            try:
                on_progress(
                    {
                        "phase": "ingest",
                        "done": 0,
                        "total": 0,
                        "status": "preparing",
                        "file": "building resolution indexes",
                    }
                )
            except Exception:  # noqa: BLE001 — progress must never break ingest
                pass
        try:
            indexes, by_qualified, short_names = self._resolution_indexes(scope)
            shared_resolution = {
                "indexes": indexes,
                "by_qualified": by_qualified,
                "short_names": short_names,
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
                        "shared_resolution": shared_resolution,
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
            _emit(progress_total, status="finalizing")
            try:
                finals = self.finalize_cross_file_resolution(
                    scope,
                    package_aliases=package_aliases,
                )
                with state_lock:
                    totals["edges_written"] += int(finals or 0)
            except Exception:  # noqa: BLE001 — finalize must not fail the ingest walk
                pass

        resolved_root = str(Path(root_path).expanduser().resolve())
        # Package README maps only when this run visited files (avoid noop graph walks).
        if total_files:
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
        for symbol in self.store.list_symbols(scope):
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
