"""Ingest and language-profile HTTP routes."""

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from ..core import CodeGraphService
from ..domain.errors import ClientDisconnected, ConflictError
from .auth import ContentPushHttpAuth
from .client_cancel import register_cancel, run_until_client_disconnect, watch_disconnect
from .common import scope_from
from .ingest_push_stream import (
    PROGRESS,
    build_progress_stream,
    ndjson_line,
    run_push_with_progress,
    wants_ndjson_stream,
)
from .job_cancel_registry import cancel_job, unregister_job
from .schemas import (
    IngestFileRequest,
    IngestPushCancelRequest,
    IngestPushRequest,
    IngestRepoRequest,
    IngestRuntimeTracesRequest,
    PurgeRequest,
)


def register(api: FastAPI, service: CodeGraphService) -> None:
    @api.post("/api/v1/projects/{project_id}/graph/ingest-file")
    async def ingest_file(
        project_id: str,
        body: IngestFileRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        result = service.ingest_file(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body.model_dump(),
        )
        return {
            "file_id": result.file_id,
            "symbols_indexed": result.symbols_indexed,
            "symbols_changed": result.symbols_changed,
            "symbols_documented": result.symbols_documented,
            "edges_written": result.edges_written,
            "changed_symbol_ids": result.changed_symbol_ids,
        }

    @api.post("/api/v1/projects/{project_id}/graph/ingest-repo")
    async def ingest_repo(
        project_id: str,
        body: IngestRepoRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        result = service.ingest_repo(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body.model_dump(),
        )
        return result.to_dict()

    @api.post("/api/v1/projects/{project_id}/graph/ingest-push", response_model=None)
    async def ingest_push(
        project_id: str,
        body: IngestPushRequest,
        request: Request,
        _auth: ContentPushHttpAuth,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
        x_project_group_id: str | None = Header(default=None),
        x_sync_job_id: str | None = Header(default=None, alias="X-Sync-Job-Id"),
    ) -> dict[str, Any] | StreamingResponse:
        from code_graph_service.domain.errors import ValidationError
        from code_graph_service.domain.path_safety import safe_repo_rel_path

        scope = scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        dumped = body.model_dump()
        docs = dumped.pop("docs", None)
        correlation_id = x_correlation_id or str(uuid4())
        job_id = str(x_sync_job_id or "").strip() or None

        def _work(should_cancel) -> dict[str, Any]:
            result = service.ingest_pushed_sources(
                scope,
                x_actor_id,
                correlation_id,
                idempotency_key,
                dumped,
                should_cancel=should_cancel,
            )
            out = result.to_dict()
            if docs is None:
                return out
            if should_cancel():
                raise ClientDisconnected()
            on_progress = dumped.get("on_progress")
            total = len(docs)
            if callable(on_progress):
                on_progress({"phase": "docs", "done": 0, "total": total, "status": "started"})
            upserted = 0
            failed = 0
            errors: list[str] = []
            for i, entry in enumerate(docs, start=1):
                if should_cancel():
                    raise ClientDisconnected()
                rel = ""
                doc_status = "ok"
                if not isinstance(entry, dict):
                    failed += 1
                    doc_status = "failed"
                else:
                    try:
                        rel = safe_repo_rel_path(
                            str(entry.get("relative_path") or entry.get("file_path") or "")
                        )
                        doc_id = str(entry.get("doc_id") or "").strip()
                        body_text = entry.get("body")
                        if not isinstance(body_text, str):
                            body_text = "" if body_text is None else str(body_text)
                        if not doc_id:
                            raise ValidationError("doc_id is required")
                        if len(body_text.encode("utf-8", errors="replace")) > 2_000_000:
                            raise ValidationError("doc body exceeds 2_000_000 bytes")
                        tokens = entry.get("linked_symbol_tokens") or []
                        if not isinstance(tokens, list):
                            tokens = []
                        service.upsert_human_documentation(
                            scope,
                            doc_id=doc_id,
                            relative_path=rel,
                            body=body_text,
                            title=str(entry.get("title") or doc_id),
                            linked_symbol_tokens=[str(t) for t in tokens if str(t).strip()],
                        )
                        upserted += 1
                    except ClientDisconnected:
                        raise
                    except Exception as exc:  # noqa: BLE001
                        failed += 1
                        doc_status = "failed"
                        errors.append(str(exc)[:200])
                if callable(on_progress):
                    on_progress(
                        {
                            "phase": "docs",
                            "done": i,
                            "total": total,
                            "file": rel,
                            "status": doc_status,
                        }
                    )
            out["docs"] = {
                "docs_upserted": upserted,
                "docs_failed": failed,
                "errors": errors[:20],
            }
            return out

        if wants_ndjson_stream(
            accept=request.headers.get("accept"),
            stream_query=request.query_params.get("stream"),
        ):
            q, emit = build_progress_stream()
            try:
                cancel, jid = register_cancel(
                    job_id,
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                )
            except ConflictError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(exc.message),
                ) from exc

            if jid:
                from .client_sync_job_snapshots import write_job_snapshot

                write_job_snapshot(
                    jid,
                    {
                        "phase": "ingest",
                        "status": "registered",
                        "done": 0,
                        "total": 0,
                        "active": True,
                    },
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                )

            def _on_progress(event: dict[str, Any]) -> None:
                safe = {k: v for k, v in event.items() if k != "source"}
                emit({"type": PROGRESS, **safe})
                if jid:
                    from .client_sync_job_snapshots import write_job_snapshot

                    write_job_snapshot(
                        jid,
                        {**safe, "active": True},
                        tenant_id=scope.tenant_id,
                        workspace_id=scope.workspace_id,
                        project_id=scope.project_id,
                    )

            dumped["on_progress"] = _on_progress

            async def _gen():
                from .client_sync_job_snapshots import clear_job_snapshot

                watcher = asyncio.create_task(watch_disconnect(request, cancel))
                worker = asyncio.create_task(
                    asyncio.to_thread(run_push_with_progress, emit, lambda: _work(cancel.is_set))
                )
                try:
                    while True:
                        item = await q.get()
                        if item is None:
                            break
                        yield ndjson_line(item)
                finally:
                    cancel.set()
                    if jid:
                        unregister_job(jid, cancel)
                        clear_job_snapshot(jid)
                    watcher.cancel()
                    try:
                        await watcher
                    except asyncio.CancelledError:
                        pass
                    await worker

            return StreamingResponse(_gen(), media_type="application/x-ndjson")

        if job_id:
            from .client_sync_job_snapshots import clear_job_snapshot, write_job_snapshot

            write_job_snapshot(
                job_id,
                {
                    "phase": "ingest",
                    "status": "registered",
                    "done": 0,
                    "total": 0,
                    "active": True,
                },
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
            )

            def _on_progress_plain(event: dict[str, Any]) -> None:
                safe = {k: v for k, v in event.items() if k != "source"}
                write_job_snapshot(
                    job_id,
                    {**safe, "active": True},
                    tenant_id=scope.tenant_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                )

            dumped["on_progress"] = _on_progress_plain

        try:
            return await run_until_client_disconnect(
                request,
                _work,
                job_id=job_id,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_id,
            )
        except ConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc.message),
            ) from exc
        except ClientDisconnected as exc:
            raise HTTPException(
                status_code=499,
                detail=str(exc.message or "client disconnected during ingest-push"),
            ) from exc
        finally:
            if job_id:
                from .client_sync_job_snapshots import clear_job_snapshot

                clear_job_snapshot(job_id)

    @api.post("/api/v1/projects/{project_id}/graph/ingest-push/cancel")
    async def ingest_push_cancel(
        project_id: str,
        body: IngestPushCancelRequest,
        _auth: ContentPushHttpAuth,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        # Cancel only the exact (tenant, workspace, project, job_id) handle.
        scope = scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        found = cancel_job(
            body.job_id,
            tenant_id=scope.tenant_id,
            workspace_id=scope.workspace_id,
            project_id=scope.project_id,
        )
        return {"ok": True, "cancelled": found, "job_id": body.job_id}

    @api.post("/api/v1/projects/{project_id}/graph/purge")
    async def purge(
        project_id: str,
        body: PurgeRequest,
        _auth: ContentPushHttpAuth,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if not body.yes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="yes: true is required to confirm destructive purge",
            )
        scope = scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        result = service.purge_scope(scope)
        return {"ok": True, "purge": result}

    @api.get("/api/v1/projects/{project_id}/graph/file-hashes")
    async def file_hashes(
        project_id: str,
        _auth: ContentPushHttpAuth,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        hashes = service.file_content_hashes(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        )
        return {"hashes": hashes}

    @api.post("/api/v1/projects/{project_id}/graph/ingest-runtime-traces")
    async def ingest_runtime_traces(
        project_id: str,
        body: IngestRuntimeTracesRequest,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_actor_id: str = Header(),
        x_correlation_id: str | None = Header(default=None),
        idempotency_key: str = Header(alias="Idempotency-Key"),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return service.ingest_runtime_traces(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id),
            x_actor_id,
            x_correlation_id or str(uuid4()),
            idempotency_key,
            body.model_dump(),
        )

    @api.get("/api/v1/projects/{project_id}/graph/language-profile")
    async def language_profile(
        project_id: str,
        x_tenant_id: str = Header(),
        x_workspace_id: str = Header(),
        x_project_group_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        profile = service.get_polyglot_profile(
            scope_from(project_id, x_tenant_id, x_workspace_id, x_project_group_id)
        )
        return profile.to_dict()
