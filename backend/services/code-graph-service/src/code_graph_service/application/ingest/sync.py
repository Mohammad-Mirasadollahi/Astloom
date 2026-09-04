"""Auto sync policy and purge.

Role: choose full / pending / incremental / noop and orchestrate ingest.
SoT: graph symbols + freshness pending list; ingest hash/language for skip.
Invariants: callers never pick mode; noop when nothing to visit or only
hash-stable skips; truncated sync must be re-runnable.
Allowed failure: per-file ingest failures bubble via ingest result counts.
Forbidden: forcing full re-index when symbols already exist and content is stable.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from ...domain.fs_paths import require_directory
from ...domain.hashing import content_hash
from ...domain.package_manifests import load_package_aliases
from ...domain.errors import ValidationError
from ...domain.languages import detect_language_from_path
from ...domain.models import (
    RepoIngestFileOutcome,
    RepoIngestResult,
    Scope,
    SyncRepoResult,
)
from ...domain.ports import list_symbols_compact
from ...locked_store import sync_max_file_workers
from .parallel_files import run_parallel_file_jobs


class SyncMixin:
    """Operator-facing sync_repo / purge_scope."""

    def sync_repo(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> SyncRepoResult:
        """Auto-choose full vs incremental file sync; callers never pick file mode.

        Optional payload ``embedding_refresh_mode``: ``touched`` (default) or ``full``
        (``astloom sync heal`` — whole-scope missing/mismatch + orphans, uncapped).
        """
        root_path = str(payload.get("root_path") or "").strip()
        if not root_path:
            raise ValidationError("root_path is required")
        resolved_root = require_directory(root_path)

        on_progress = payload.get("on_progress")

        def _emit_prep(detail: str, *, status: str = "preparing") -> None:
            if not callable(on_progress):
                return
            try:
                on_progress(
                    {
                        "phase": "ingest",
                        "done": 0,
                        "total": 0,
                        "status": status,
                        "file": detail,
                    }
                )
            except Exception:  # noqa: BLE001 — progress must never break sync
                return

        # list_symbols / freshness can take minutes on a large Neo4j graph with no
        # file-queue progress yet — emit a heartbeat so the CLI is not silent.
        _emit_prep("loading graph symbols")
        symbols = list_symbols_compact(self.store, scope)
        _emit_prep("checking freshness / pending files")
        freshness = (
            self.freshness_status(scope) if hasattr(self, "freshness_status") else {"pending_files": []}
        )
        pending = [str(p) for p in (freshness.get("pending_files") or []) if str(p).strip()]

        ingest_payload = dict(payload)
        ingest_payload["root_path"] = str(resolved_root)

        if not symbols:
            ingest = self.ingest_repo(scope, actor_id, correlation_id, idempotency_key, ingest_payload)
            hint = ""
            if ingest.truncated:
                hint = "truncated: run sync again to continue indexing more files"
            if hasattr(self, "record_sync_stamp"):
                self.record_sync_stamp(scope)
            return SyncRepoResult.from_ingest(
                mode="full",
                ingest=ingest,
                freshness=self.freshness_status(scope) if hasattr(self, "freshness_status") else freshness,
                hint=hint,
            )

        if pending:
            ingest = self._ingest_pending_paths(
                scope,
                actor_id,
                correlation_id,
                idempotency_key,
                root=resolved_root,
                pending_paths=pending,
                include_outcomes=bool(payload.get("include_outcomes", True)),
                on_progress=payload.get("on_progress"),
                embedding_refresh_mode=str(payload.get("embedding_refresh_mode") or "touched"),
            )
            hint = ""
            if hasattr(self, "record_sync_stamp"):
                self.record_sync_stamp(scope)
            if ingest.files_ingested == 0 and ingest.files_failed == 0:
                if ingest.files_skipped > 0:
                    hint = "up to date (pending files unchanged)"
                else:
                    hint = "no pending files could be resolved under root_path"
                return SyncRepoResult.from_ingest(
                    mode="noop",
                    ingest=ingest,
                    freshness=self.freshness_status(scope) if hasattr(self, "freshness_status") else freshness,
                    hint=hint,
                )
            return SyncRepoResult.from_ingest(
                mode="incremental",
                ingest=ingest,
                freshness=self.freshness_status(scope) if hasattr(self, "freshness_status") else freshness,
                hint=hint,
            )

        ingest = self.ingest_repo(scope, actor_id, correlation_id, idempotency_key, ingest_payload)
        mode = "incremental"
        hint = ""
        if ingest.truncated:
            hint = "truncated: run sync again to continue indexing more files"
        elif ingest.files_ingested == 0 and ingest.files_skipped > 0:
            # Hash-stable files may be counted skipped without a worker visit.
            mode = "noop"
            hint = "up to date (no content changes)"
        elif ingest.files_discovered == 0:
            mode = "noop"
            hint = "up to date (no source files discovered)"
        if hasattr(self, "record_sync_stamp"):
            self.record_sync_stamp(scope)
        return SyncRepoResult.from_ingest(
            mode=mode,
            ingest=ingest,
            freshness=self.freshness_status(scope) if hasattr(self, "freshness_status") else freshness,
            hint=hint,
        )

    def _ingest_pending_paths(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        *,
        root: Path,
        pending_paths: list[str],
        include_outcomes: bool,
        on_progress: Any = None,
        embedding_refresh_mode: str = "touched",
    ) -> RepoIngestResult:
        package_aliases = load_package_aliases(root)
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
        total_files = len(pending_paths)
        state_lock = threading.Lock()
        done_count = 0
        shared_resolution: dict[str, Any] = {
            "indexes": None,
            "by_qualified": {},
            "short_names": {},
        }
        if callable(on_progress):
            try:
                on_progress(
                    {
                        "phase": "incremental",
                        "done": 0,
                        "total": 0,
                        "status": "preparing",
                        "file": "building resolution indexes",
                    }
                )
            except Exception:  # noqa: BLE001
                pass
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

        def _emit(done: int, *, file: str = "", status: str = "") -> None:
            if not callable(on_progress):
                return
            try:
                with state_lock:
                    snap_totals = dict(totals)
                on_progress(
                    {
                        "phase": "incremental",
                        "done": done,
                        "total": total_files,
                        "file": file,
                        "status": status,
                        "files_ingested": snap_totals["ingested"],
                        "files_failed": snap_totals["failed"],
                        "files_skipped": snap_totals["skipped"],
                        "symbols_indexed": snap_totals["symbols_indexed"],
                        "symbols_changed": snap_totals["symbols_changed"],
                        "edges_written": snap_totals["edges_written"],
                        "chars_read": snap_totals["chars_read"],
                        "approx_tokens": snap_totals["chars_read"] // 4,
                    }
                )
            except Exception:  # noqa: BLE001
                return

        def _process_one(_index: int, raw: str) -> None:
            nonlocal done_count
            rel, abs_path = self._resolve_pending_path(root, raw)
            if abs_path is None or not abs_path.is_file():
                with state_lock:
                    totals["skipped"] += 1
                    done_count += 1
                    done = done_count
                    if include_outcomes:
                        outcomes.append(
                            RepoIngestFileOutcome(
                                relative_path=rel or raw,
                                language="",
                                status="skipped",
                                detail="not_found_under_root",
                            )
                        )
                _emit(done, file=rel or raw, status="skipped")
                return
            try:
                language = detect_language_from_path(str(abs_path)) or ""
            except Exception:
                language = ""
            if not language:
                with state_lock:
                    totals["skipped"] += 1
                    done_count += 1
                    done = done_count
                    if include_outcomes:
                        outcomes.append(
                            RepoIngestFileOutcome(
                                relative_path=rel,
                                language="",
                                status="skipped",
                                detail="unsupported_language",
                            )
                        )
                if hasattr(self, "clear_pending_sync"):
                    self.clear_pending_sync(raw)
                _emit(done, file=rel, status="skipped")
                return
            try:
                text_body = abs_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                with state_lock:
                    totals["failed"] += 1
                    done_count += 1
                    done = done_count
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
            hashed = content_hash(text_body, language)
            file_key = (
                f"{idempotency_key}:pending:{rel}:{hashed['hash']}:"
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
                        "source": text_body,
                        "language": language,
                        "package_aliases": package_aliases,
                        "defer_cross_file_pass": True,
                        "shared_resolution": shared_resolution,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                with state_lock:
                    totals["failed"] += 1
                    done_count += 1
                    done = done_count
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
                totals["chars_read"] += len(text_body)
                totals["symbols_indexed"] += result.symbols_indexed
                totals["symbols_changed"] += result.symbols_changed
                totals["symbols_documented"] += result.symbols_documented
                totals["edges_written"] += result.edges_written
                done_count += 1
                done = done_count
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

        _emit(0, status="started")
        workers = min(sync_max_file_workers(), max(1, total_files))
        if total_files:
            run_parallel_file_jobs(workers=workers, items=pending_paths, fn=_process_one)
            _emit(total_files, status="finalizing", file="cross-file resolution")
        try:
            finals = self.finalize_cross_file_resolution(
                scope,
                package_aliases=package_aliases,
                on_progress=lambda ev: _emit(
                    total_files,
                    file=str(ev.get("file") or "cross-file resolution"),
                    status=str(ev.get("status") or "finalizing"),
                ),
            )
            with state_lock:
                totals["edges_written"] += int(finals or 0)
        except Exception:  # noqa: BLE001
            pass
        # Embeddings are keyed by normalized relative paths (same as ingest_file).
        # Raw pending entries may be absolute or ./prefixed — never pass those through.
        embed_paths = self._normalized_pending_rel_paths(root, pending_paths)
        embedding_refresh = self.refresh_embeddings_after_ingest(
            scope,
            file_paths=embed_paths,
            mode=str(embedding_refresh_mode or "touched"),
            on_progress=on_progress if callable(on_progress) else None,
        ).public()
        return RepoIngestResult(
            root_path=str(root),
            files_discovered=len(pending_paths),
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

    @staticmethod
    def _resolve_pending_path(root: Path, raw: str) -> tuple[str, Path | None]:
        cleaned = (raw or "").strip().replace("\\", "/")
        if not cleaned:
            return "", None
        candidate = Path(cleaned)
        if candidate.is_absolute():
            try:
                rel = str(candidate.resolve().relative_to(root)).replace("\\", "/")
            except ValueError:
                return cleaned, None
            return rel, (root / rel)
        rel = cleaned.lstrip("./")
        return rel, (root / rel)

    @classmethod
    def _normalized_pending_rel_paths(cls, root: Path, pending_paths: list[str]) -> list[str]:
        """Relative paths for embedding scope — matches ingest_file ``file_path`` keys."""
        out: list[str] = []
        seen: set[str] = set()
        for raw in pending_paths:
            rel, _abs = cls._resolve_pending_path(root, raw)
            key = str(rel or "").strip().replace("\\", "/")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    def purge_scope(self, scope: Scope) -> dict[str, Any]:
        """Wipe all graph data for the project scope (embeddings + store + pending)."""
        before = len(self.store.list_symbols(scope))
        edges_before = len(self.store.list_edges(scope))
        for symbol in self.store.list_symbols(scope):
            self._delete_embedding(scope, symbol.id)
        wipe = getattr(self.store, "wipe_scope", None)
        if not callable(wipe):
            raise ValidationError("store does not support wipe_scope")
        deleted = wipe(scope)
        index_wipe = getattr(self.embedding_index, "wipe_scope", None) if self.embedding_index else None
        embeddings_deleted = 0
        if callable(index_wipe):
            embeddings_deleted = int(index_wipe(scope) or 0)
        if hasattr(self, "clear_pending_sync"):
            self.clear_pending_sync()
        return {
            "ok": True,
            "symbols_before": before,
            "edges_before": edges_before,
            "deleted": deleted,
            "embeddings_deleted": embeddings_deleted,
            "symbols_after": len(self.store.list_symbols(scope)),
            "edges_after": len(self.store.list_edges(scope)),
        }
