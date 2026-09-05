"""Embedding refresh orchestration (GAP-T03).

Role: re-embed symbols when model/dims change or rows are missing per refresh-policy.
SoT: PostgreSQL/pgvector EmbeddingIndex rows + refresh-policy.json; turbovec is replica only.
Allowed: skip when model matches; fail-open turbovec sync; dry-run without writes.
Forbidden: treating ANN as SoR; cross-tenant refresh; silent incomplete without failed state.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ..domain.rag import SEARCHABLE_SYMBOL_KINDS

RefreshState = Literal["pending", "running", "failed", "complete"]

_DEFAULT_POLICY = (
    Path(__file__).resolve().parents[5]
    / "configs"
    / "embeddings"
    / "refresh-policy.json"
)


@dataclass
class RefreshReport:
    policy_id: str
    target_model: str
    state: RefreshState = "pending"
    scanned: int = 0
    refreshed: int = 0
    skipped: int = 0
    deleted_orphans: int = 0
    dry_run: bool = False
    error: str | None = None
    reasons: dict[str, int] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "policy_id": self.policy_id,
            "target_model": self.target_model,
            "state": self.state,
            "scanned": self.scanned,
            "refreshed": self.refreshed,
            "skipped": self.skipped,
            "deleted_orphans": self.deleted_orphans,
            "dry_run": self.dry_run,
            "reasons": dict(self.reasons),
        }
        if self.error:
            payload["error"] = self.error
        return payload


def load_refresh_policy(path: Path | None = None) -> dict[str, Any]:
    policy_path = path or _DEFAULT_POLICY
    data = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"refresh policy must be an object: {policy_path}")
    return data


def _require_tenant_scope(scope: Any, policy: dict[str, Any]) -> None:
    isolation = policy.get("tenant_isolation") or {}
    keys = list(isolation.get("scope_keys") or ("tenant_id", "workspace_id", "project_id"))
    missing = [key for key in keys if not str(getattr(scope, key, "") or "").strip()]
    if missing:
        raise ValueError(f"embedding refresh requires scope fields: {', '.join(missing)}")
    if isolation.get("cross_tenant_forbidden", True) is not True:
        raise ValueError("refresh-policy tenant_isolation.cross_tenant_forbidden must be true")


def _env_truthy(name: str) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = str(os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class EmbeddingRefreshMixin:
    """Mixin for CodeGraphService — refresh embeddings under configured policy."""

    def refresh_embeddings_after_ingest(
        self,
        scope: Any,
        *,
        file_paths: list[str] | None = None,
        mode: str = "touched",
        on_progress: Any = None,
        policy_path: Path | None = None,
    ) -> RefreshReport:
        """Post-ingest heal: prefer touched files; otherwise drain a capped backlog.

        ``mode``: ``touched`` (default) or ``full`` (whole-scope missing/mismatch + orphans).
        Env override: ``ASTLOOM_EMBEDDING_REFRESH_FULL=1`` forces ``full``.
        Noop backlog cap: ``ASTLOOM_EMBEDDING_REFRESH_MAX_PENDING`` (default 256).
        """
        paths = [
            str(p or "").strip().replace("\\", "/")
            for p in (file_paths or [])
            if str(p or "").strip()
        ]
        mode_norm = str(mode or "touched").strip().lower()
        if mode_norm in {"off", "skip", "none", "disabled"}:
            return RefreshReport(
                policy_id="off",
                target_model="",
                state="complete",
                scanned=0,
                refreshed=0,
                skipped=len(paths),
                reasons={"mode": 1},
            )
        if mode_norm == "full" or _env_truthy("ASTLOOM_EMBEDDING_REFRESH_FULL"):
            return self.refresh_embeddings(
                scope,
                force=False,
                on_progress=on_progress,
                policy_path=policy_path,
            )
        if paths:
            return self.refresh_embeddings(
                scope,
                file_paths=paths,
                on_progress=on_progress,
                policy_path=policy_path,
            )
        return self.refresh_embeddings(
            scope,
            max_pending=max(0, _env_int("ASTLOOM_EMBEDDING_REFRESH_MAX_PENDING", 256)),
            on_progress=on_progress,
            policy_path=policy_path,
        )

    def refresh_embeddings(
        self,
        scope: Any,
        *,
        force: bool = False,
        dry_run: bool = False,
        policy_path: Path | None = None,
        on_progress: Any = None,
        file_paths: list[str] | None = None,
        max_pending: int | None = None,
    ) -> RefreshReport:
        """Refresh missing/mismatched embeddings.

        ``file_paths``: limit to symbols under those relative paths (incremental sync).
        ``max_pending``: after selection, process at most N (stable by symbol id).
        Full-project heal: omit ``file_paths`` and set ``max_pending=None`` (or force).
        """
        policy = load_refresh_policy(policy_path)
        target_model = str(
            getattr(self.embeddings, "model", None) or policy.get("default_model") or ""
        )
        report = RefreshReport(
            policy_id=str(policy.get("policy_id") or "unknown"),
            target_model=target_model,
            state="pending",
            dry_run=bool(dry_run),
        )

        def _progress(
            *,
            done: int,
            total: int,
            status: str,
            workers: int = 0,
            in_flight: int = 0,
        ) -> None:
            if not callable(on_progress):
                return
            try:
                on_progress(
                    {
                        "phase": "embeddings",
                        "status": status,
                        "done": done,
                        "total": total,
                        "embeddings_refreshed": done,
                        "file": target_model or "embedding",
                        "file_workers": workers,
                        "files_in_flight": in_flight,
                    }
                )
            except Exception:  # noqa: BLE001 — progress must not fail refresh
                pass

        try:
            _require_tenant_scope(scope, policy)
            report.state = "running"
            if self.embedding_index is None:
                # Do not pretend a full heal ran — MCP often has Neo4j without
                # pgvector when only ASTLOOM_DATABASE_URL was missing from Settings.
                report.state = "complete"
                report.error = (
                    "embedding_index_unavailable: set ASTLOOM_CODE_GRAPH_DATABASE_URL "
                    "or ASTLOOM_DATABASE_URL (pgvector SoT)"
                )
                report.reasons["embedding_index_unavailable"] = 1
                _progress(done=0, total=0, status="finished", workers=0)
                return report

            scoped_paths = [
                str(p or "").strip().replace("\\", "/")
                for p in (file_paths or [])
                if str(p or "").strip()
            ]
            if scoped_paths:
                by_id: dict[str, Any] = {}
                for path in scoped_paths:
                    for symbol in self.store.list_symbols_for_file(scope, path):
                        by_id[str(symbol.id)] = symbol
                symbols = list(by_id.values())
            else:
                symbols = list(self.store.list_symbols(scope))

            models: dict[str, str] = {}
            list_models = getattr(self.embedding_index, "list_symbol_models", None)
            if callable(list_models):
                models = dict(list_models(scope))

            # Orphan cleanup is whole-scope only (file-scoped refresh must not
            # delete embeddings for untouched files).
            if not scoped_paths:
                live_ids = {s.id for s in symbols}
                for symbol_id in list(models):
                    if symbol_id not in live_ids:
                        if not dry_run:
                            self._delete_embedding(scope, symbol_id)
                        report.deleted_orphans += 1
                        report.reasons["orphan_cleanup_after_delete"] = (
                            report.reasons.get("orphan_cleanup_after_delete", 0) + 1
                        )

            skip_when_unchanged = bool(policy.get("skip_when_model_unchanged", True)) and not force
            pending: list[tuple[Any, str, str, str]] = []
            for symbol in symbols:
                kind = str(getattr(symbol.kind, "value", symbol.kind) or "unknown")
                if kind not in SEARCHABLE_SYMBOL_KINDS:
                    continue
                report.scanned += 1
                existing_model = models.get(symbol.id, "")
                needs = force or not existing_model or existing_model != target_model
                reason = (
                    "operator_force_refresh"
                    if force
                    else (
                        "missing_embedding_row"
                        if not existing_model
                        else "configured_model_mismatch"
                        if existing_model != target_model
                        else ""
                    )
                )
                if not needs and skip_when_unchanged:
                    report.skipped += 1
                    continue
                text = " ".join(
                    part
                    for part in (
                        getattr(symbol, "qualified_name", "") or getattr(symbol, "name", ""),
                        getattr(symbol, "signature", "") or "",
                        getattr(symbol, "body", "") or "",
                        getattr(symbol, "ai_documentation", "") or "",
                    )
                    if part
                ).strip()
                if not text:
                    report.skipped += 1
                    continue
                if dry_run:
                    report.refreshed += 1
                    if reason:
                        report.reasons[reason] = report.reasons.get(reason, 0) + 1
                    continue
                pending.append((symbol, kind, text, reason))

            if max_pending is not None and max_pending >= 0 and len(pending) > max_pending:
                pending.sort(key=lambda item: str(item[0].id))
                deferred = len(pending) - max_pending
                pending = pending[:max_pending]
                report.reasons["deferred_over_max_pending"] = (
                    report.reasons.get("deferred_over_max_pending", 0) + deferred
                )

            batch = getattr(self.embeddings, "embed_many", None)
            try:
                chunk_size = int(policy.get("batch_size") or 32)
            except (TypeError, ValueError):
                chunk_size = 32
            chunk_size = max(1, min(chunk_size, 64))
            chunks = [
                pending[offset : offset + chunk_size]
                for offset in range(0, len(pending), chunk_size)
            ]

            def _embed_chunk(chunk: list[tuple[Any, str, str, str]]):
                texts = [item[2] for item in chunk]
                results = (
                    list(batch(texts))
                    if callable(batch)
                    else [self.embeddings.embed(text) for text in texts]
                )
                if len(results) != len(chunk):
                    raise RuntimeError(
                        "embedding batch returned "
                        f"{len(results)} results for {len(chunk)} symbols"
                    )
                return chunk, results

            try:
                configured_workers = int(
                    os.environ.get("ASTLOOM_EMBEDDING_REFRESH_WORKERS", "4")
                )
            except ValueError:
                configured_workers = 4
            workers = min(
                max(1, configured_workers),
                16,
                max(1, len(chunks)),
            )
            total_pending = len(pending)
            _progress(
                done=0,
                total=total_pending,
                status="started",
                workers=workers,
                in_flight=min(workers, max(1, len(chunks))) if chunks else 0,
            )
            if not chunks:
                report.state = "complete"
                _progress(done=0, total=0, status="finished", workers=0)
                return report
            with ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="embedding-refresh",
            ) as executor:
                futures = [executor.submit(_embed_chunk, chunk) for chunk in chunks]
                completed = (future.result() for future in as_completed(futures))
                for chunk, results in completed:
                    for (symbol, kind, _text, reason), result in zip(
                        chunk,
                        results,
                        strict=True,
                    ):
                        self._index_embedding(
                            scope,
                            symbol.id,
                            list(result.vector),
                            kind=kind,
                        )
                        report.refreshed += 1
                        if reason:
                            report.reasons[reason] = report.reasons.get(reason, 0) + 1
                    _progress(
                        done=report.refreshed,
                        total=total_pending,
                        status="running",
                        workers=workers,
                        in_flight=max(0, len(futures) - sum(1 for f in futures if f.done())),
                    )
            report.state = "complete"
            _progress(
                done=report.refreshed,
                total=total_pending,
                status="finished",
                workers=workers,
            )
            return report
        except Exception as exc:  # noqa: BLE001 — job state must surface failure
            report.state = "failed"
            report.error = f"{type(exc).__name__}: {exc}"
            return report
