"""Client content-push sync: local discovery → HTTPS ingest-push (no durable stage).

SSH content-push has been removed (API-only HTTPS migration); a bare
``server.ssh`` with no ``server.graph_url`` fails closed rather than falling
back to SSH.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from astloom_cli import ui
from astloom_cli.connect_config import ConnectSettings, http_error_message
from astloom_cli.connect_flow.push_stream import (
    consume_ndjson_ingest_push,
    stream_accept_headers,
)
from astloom_cli.connect_http import httpx_verify
from astloom_cli.parser._core import (
    HARD_SYNC_MAX_FILES,
    max_files_is_auto,
    resolve_discovery_max_files,
)
from astloom_cli.sync_config import resolve_sync_filters
from astloom_cli.util import ensure_service_import_paths

ensure_service_import_paths()

from code_graph_service.domain.errors import ValidationError
from code_graph_service.domain.hashing import content_hash
from code_graph_service.domain.path_safety import safe_repo_rel_path
from code_graph_service.domain.repo_discovery import (
    DEFAULT_MAX_FILE_BYTES,
    discover_source_files,
)

# Soft cap per ingest-push HTTP body (bytes of encoded JSON).
_MAX_BATCH_BYTES = 4_000_000
# Keep each batch under the HTTP schema files[] max_length (2000).
_MAX_BATCH_FILES = 1500

# Floor denylist: never push these into the graph (even if sync.yaml includes them).
_SECRET_BASENAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        ".env.staging",
        "credentials.json",
        "service-account.json",
        "id_rsa",
        "id_rsa.pub",
        "id_ed25519",
        "id_ed25519.pub",
        "id_ecdsa",
        "id_ecdsa.pub",
    }
)
_SECRET_SUFFIXES = (".pem", ".p12", ".pfx", ".key")

# Fail-closed default when the server's /api/v1/llm/config probe is unreachable:
# assume cloud LLM routes are enabled so the consent gate still fires.
ASSUME_CLOUD_LLM_CONFIG: dict[str, Any] = {
    "enabled": True,
    "docs_enabled": True,
    "route_docs": {"primary_model": "unknown"},
    "embeddings_enabled": True,
    "route_embed": {"primary_model": "unknown"},
    "api_base": "",
}


def _looks_like_secret_path(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    lower = name.lower()
    if name in _SECRET_BASENAMES or lower in _SECRET_BASENAMES:
        return True
    if lower.startswith(".env."):
        return True
    return any(lower.endswith(suf) for suf in _SECRET_SUFFIXES)


def build_push_files(
    root: Path,
    args: Any,
    *,
    remote_hashes: dict[str, str] | None = None,
) -> tuple[list[dict[str, str]], list[str], int, bool]:
    """Discover local sources; return (files, present_paths, skipped, prune_ok).

    ``prune_ok`` is True only when discovery is an authoritative full inventory
    (no ``--include-path`` scope and not truncated by ``max_files``). Callers must
    omit ``present_paths`` when False so partial syncs cannot prune the graph.
    """
    filters = resolve_sync_filters(
        root=root,
        cli_exclude_dirs=list(getattr(args, "exclude_dir", None) or []),
        cli_include_paths=list(getattr(args, "include_path", None) or []),
        cli_include_extensions=list(getattr(args, "include_ext", None) or []) or None,
    )
    max_files = resolve_discovery_max_files(getattr(args, "max_files", None))
    discovered = discover_source_files(
        root,
        include_extensions=filters.get("include_extensions"),
        exclude_dirs=filters.get("exclude_dirs"),
        exclude_globs=filters.get("exclude_globs"),
        reinclude_globs=filters.get("layered_reinclude_globs") or [],
        include_path_prefixes=filters.get("include_paths"),
        max_files=max_files,
        max_file_bytes=int(filters.get("max_file_bytes") or DEFAULT_MAX_FILE_BYTES),
    )
    present = [
        item.relative_path.replace("\\", "/")
        for item in discovered
        if not _looks_like_secret_path(item.relative_path.replace("\\", "/"))
    ]
    known = remote_hashes or {}
    files: list[dict[str, str]] = []
    skipped = 0
    secret_skips = 0
    for item in discovered:
        rel = item.relative_path.replace("\\", "/")
        try:
            rel = safe_repo_rel_path(rel)
        except ValidationError:
            continue
        if _looks_like_secret_path(rel):
            secret_skips += 1
            continue
        try:
            text = Path(item.absolute_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if len(text.encode("utf-8")) > int(filters.get("max_file_bytes") or DEFAULT_MAX_FILE_BYTES):
            continue
        hashed = content_hash(text, item.language)
        if known.get(rel) == hashed.get("hash"):
            skipped += 1
            continue
        files.append(
            {
                "file_path": rel,
                "source": text,
                "language": item.language,
            }
        )
    scoped = bool(filters.get("include_paths"))
    truncated = len(discovered) >= max_files
    prune_ok = (not scoped) and (not truncated)
    return files, present, skipped + secret_skips, prune_ok


def _batches(
    files: list[dict[str, str]],
    present: list[str],
    *,
    docs: list[dict[str, Any]] | None = None,
    include_present_paths: bool = True,
) -> list[dict[str, Any]]:
    """Split files into JSON-size-capped batches; last batch may carry present_paths (+ docs)."""
    if not files:
        batch: dict[str, Any] = {
            "files": [],
            "include_outcomes": True,
            "max_files": HARD_SYNC_MAX_FILES,
        }
        if include_present_paths:
            batch["present_paths"] = present
            batch["inventory_complete"] = True
        if docs is not None:
            batch["docs"] = docs
        return [batch]
    out: list[dict[str, Any]] = []
    current: list[dict[str, str]] = []
    size = 2
    for entry in files:
        chunk = json.dumps(entry, ensure_ascii=False)
        chunk_len = len(chunk.encode("utf-8")) + 1
        if current and (
            size + chunk_len > _MAX_BATCH_BYTES or len(current) >= _MAX_BATCH_FILES
        ):
            out.append(
                {
                    "files": current,
                    "include_outcomes": True,
                    "max_files": HARD_SYNC_MAX_FILES,
                }
            )
            current = []
            size = 2
        current.append(entry)
        size += chunk_len
    last: dict[str, Any] = {
        "files": current,
        "include_outcomes": True,
        "max_files": HARD_SYNC_MAX_FILES,
    }
    if include_present_paths:
        last["present_paths"] = present
        last["inventory_complete"] = True
    if docs is not None:
        last["docs"] = docs
    out.append(last)
    return out


def build_push_docs(root: Path, args: Any) -> list[dict[str, Any]]:
    """Discover human Markdown docs for optional content-push docs phase."""
    from astloom_cli.markdown_frontmatter import (
        parse_markdown_frontmatter,
        provisional_frontmatter,
    )
    from code_graph_service.domain.doc_discovery import discover_documentation_files

    filters = resolve_sync_filters(
        root=root,
        cli_exclude_dirs=list(getattr(args, "exclude_dir", None) or []),
        cli_include_paths=list(getattr(args, "include_path", None) or []),
        cli_include_extensions=list(getattr(args, "include_ext", None) or []) or None,
    )
    if not filters.get("docs_enabled", True):
        return []
    match_globs = list(filters.get("doc_match_globs") or [])
    if not match_globs:
        return []
    max_files = resolve_discovery_max_files(getattr(args, "max_files", None))
    # CLI/sync --include-path must scope docs the same way as code discovery.
    doc_paths = list(filters.get("doc_paths") or [])
    include_paths = list(filters.get("include_paths") or [])
    if include_paths:
        doc_paths = include_paths
    discovered = discover_documentation_files(
        root,
        match_globs=match_globs,
        exclude_dirs=filters.get("doc_exclude_dirs"),
        exclude_globs=filters.get("doc_exclude_globs"),
        doc_paths=doc_paths or None,
        max_files=max_files,
    )
    docs: list[dict[str, Any]] = []
    for item in discovered:
        rel = item.relative_path.replace("\\", "/")
        try:
            rel = safe_repo_rel_path(rel)
        except ValidationError:
            continue
        if _looks_like_secret_path(rel):
            continue
        try:
            text = Path(item.absolute_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if len(text.encode("utf-8")) > 2_000_000:
            continue
        partial, body = parse_markdown_frontmatter(text)
        frontmatter = provisional_frontmatter(rel, body, partial)
        doc_id = str(frontmatter.get("doc_id") or "").strip()
        if not doc_id:
            continue
        tokens = frontmatter.get("linked_symbols") or []
        if not isinstance(tokens, list):
            tokens = []
        docs.append(
            {
                "doc_id": doc_id,
                "relative_path": rel,
                "body": body,
                "title": str(frontmatter.get("title") or doc_id),
                "linked_symbol_tokens": [str(t) for t in tokens if str(t).strip()],
            }
        )
    return docs


def _http_headers(
    settings: ConnectSettings,
    *,
    job_id: str | None = None,
) -> dict[str, str]:
    import uuid

    headers = {
        "X-Tenant-Id": settings.tenant or "default",
        "X-Workspace-Id": settings.workspace or "default",
        "X-Actor-Id": settings.actor_id or "connect-cli",
        "Idempotency-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }
    if settings.api_token:
        headers["Authorization"] = f"Bearer {settings.api_token}"
    jid = str(job_id or "").strip()
    if jid:
        headers["X-Sync-Job-Id"] = jid
    return headers


def _signal_cancel_job(settings: ConnectSettings, args: Any, job_id: str) -> bool:
    """Best-effort explicit cancel for one in-flight ingest-push job (separate HTTP call)."""
    jid = str(job_id or "").strip()
    if not jid or not _graph_http_ready(settings):
        return False
    import httpx

    project = str(getattr(args, "project", None) or settings.project or "project")
    url = f"{settings.graph_url.rstrip('/')}/api/v1/projects/{project}/graph/ingest-push/cancel"
    try:
        with httpx.Client(timeout=5.0, verify=httpx_verify(settings)) as client:
            response = client.post(
                url,
                headers=_http_headers(settings),
                json={"job_id": jid},
            )
    except Exception:  # noqa: BLE001 — shutdown path must not hang on cancel errors
        return False
    return 200 <= int(response.status_code) < 300


def _graph_http_ready(settings: ConnectSettings) -> bool:
    return bool((settings.graph_url or "").strip() and (settings.api_token or "").strip())


def fetch_remote_file_hashes(settings: ConnectSettings, args: Any) -> dict[str, str]:
    """Best-effort FILE hash map over HTTPS (empty when graph_url isn't ready)."""
    if not _graph_http_ready(settings):
        return {}
    import httpx

    project = str(getattr(args, "project", None) or settings.project or "project")
    url = f"{settings.graph_url.rstrip('/')}/api/v1/projects/{project}/graph/file-hashes"

    try:
        response = httpx.get(
            url,
            headers=_http_headers(settings),
            timeout=60.0,
            verify=httpx_verify(settings),
        )
    except httpx.HTTPError:
        return {}
    if response.status_code >= 400:
        return {}
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        return {}
    hashes = payload.get("hashes") if isinstance(payload, dict) else None
    if not isinstance(hashes, dict):
        return {}
    return {
        str(k).replace("\\", "/"): str(v)
        for k, v in hashes.items()
        if str(k).strip() and str(v).strip()
    }


def _run_ingest_push_http(
    settings: ConnectSettings,
    args: Any,
    body: dict[str, Any],
    *,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    begin_phase: Callable[[], None] | None = None,
) -> dict[str, Any]:
    import uuid

    import httpx

    project = str(getattr(args, "project", None) or settings.project or "project")
    # ?stream=1 alongside Accept: proxies that strip Accept still get NDJSON progress.
    url = (
        f"{settings.graph_url.rstrip('/')}/api/v1/projects/{project}"
        "/graph/ingest-push?stream=1"
    )
    refresh = "full" if str(getattr(args, "sync_mode", "") or "").strip().lower() == "heal" else "touched"
    payload = {**body, "embedding_refresh_mode": refresh}
    job_id = str(uuid.uuid4())
    headers = {**_http_headers(settings, job_id=job_id), **stream_accept_headers()}

    # Streaming POST so Ctrl+C closes the TCP socket; also POST cancel for this job_id.
    try:
        with httpx.stream(
            "POST",
            url,
            headers=headers,
            json=payload,
            timeout=600.0,
            verify=httpx_verify(settings),
        ) as response:
            if response.status_code == 499:
                raise KeyboardInterrupt
            if response.status_code >= 400:
                response.read()
                raise SystemExit(http_error_message("HTTP ingest-push", response))
            content_type = str((getattr(response, "headers", None) or {}).get("content-type") or "")
            if "application/json" in content_type and "ndjson" not in content_type:
                # Compat: pre-streaming server returns a single JSON result body.
                read = getattr(response, "read", None)
                if callable(read):
                    read()
                try:
                    data = response.json()
                except Exception:  # noqa: BLE001
                    return {}
                return data if isinstance(data, dict) else {}
            return consume_ndjson_ingest_push(
                lines=response.iter_lines(),
                on_progress=on_progress or (lambda _event: None),
                begin_phase=begin_phase,
            )
    except KeyboardInterrupt:
        _signal_cancel_job(settings, args, job_id)
        raise
    except httpx.HTTPError as exc:
        raise SystemExit(f"error: HTTP ingest-push failed: {exc}") from exc


def _run_ingest_push(
    settings: ConnectSettings,
    args: Any,
    body: dict[str, Any],
    *,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    begin_phase: Callable[[], None] | None = None,
) -> dict[str, Any]:
    if not _graph_http_ready(settings):
        raise SystemExit(
            "error: content-push requires server.graph_url + auth token (HTTPS); "
            "SSH content-push has been removed — set server.graph_url in "
            ".astloom/connect.yaml"
        )
    return _run_ingest_push_http(settings, args, body, on_progress=on_progress, begin_phase=begin_phase)


def client_push_sync(settings: ConnectSettings, args: Any, *, work: Path) -> int:
    """Discover local checkout and push changed bodies (+ optional docs) over HTTPS."""
    if not _graph_http_ready(settings):
        raise SystemExit(
            "error: content-push requires server.graph_url + auth token (HTTPS); "
            "SSH content-push has been removed — set server.graph_url in "
            ".astloom/connect.yaml"
        )

    tenant = str(getattr(args, "tenant", None) or settings.tenant or "default")
    workspace = str(getattr(args, "workspace", None) or settings.workspace or "default")
    project = str(getattr(args, "project", None) or settings.project or work.name or "project")

    from astloom_cli.commands.graph import _require_cloud_llm_consent

    class _HttpLlmProbe:
        def llm_config(self) -> dict[str, Any]:
            import httpx

            url = f"{settings.graph_url.rstrip('/')}/api/v1/llm/config"
            try:
                response = httpx.get(
                    url,
                    headers=_http_headers(settings),
                    timeout=30.0,
                    verify=httpx_verify(settings),
                )
            except httpx.HTTPError:
                return dict(ASSUME_CLOUD_LLM_CONFIG)
            if response.status_code >= 400:
                return dict(ASSUME_CLOUD_LLM_CONFIG)
            try:
                payload = response.json()
            except Exception:  # noqa: BLE001
                return dict(ASSUME_CLOUD_LLM_CONFIG)
            return payload if isinstance(payload, dict) else dict(ASSUME_CLOUD_LLM_CONFIG)

    _require_cloud_llm_consent(
        _HttpLlmProbe(),
        allowed=bool(getattr(args, "allow_cloud_llm", False)),
        tenant=tenant,
        workspace=workspace,
        project=project,
        paths=[str(work)],
    )

    print(f"   {ui.warn('…')} client content-push sync via HTTPS (no durable server checkout)")
    remote_hashes = fetch_remote_file_hashes(settings, args)
    if _graph_http_ready(settings) and not remote_hashes:
        print(
            f"   {ui.warn('!')} remote file-hashes empty — unchanged files cannot be skipped "
            f"(check token / TLS / graph file-hashes)"
        )
    files, present, skipped, prune_ok = build_push_files(work, args, remote_hashes=remote_hashes)
    docs = build_push_docs(work, args)
    batches = _batches(files, present, docs=docs, include_present_paths=prune_ok)
    auto = max_files_is_auto(getattr(args, "max_files", None))
    cap = resolve_discovery_max_files(getattr(args, "max_files", None))
    print(
        f"   {ui.dim('note')} present={len(present)}  "
        f"push={len(files)}  unchanged_skip={skipped}  "
        f"remote_hashes={len(remote_hashes)}  "
        f"batches={len(batches)}  docs={len(docs)}  "
        f"prune={'on' if prune_ok else 'off'}  "
        f"max_files={'auto/' + str(cap) if auto else str(cap)}"
    )
    if not prune_ok:
        print(
            f"   {ui.dim('note')} prune off — partial discovery "
            f"(include-path and/or max-files cap); will not delete other graph files"
        )
    if auto and len(present) >= HARD_SYNC_MAX_FILES:
        print(
            f"   {ui.warn('!')} discovery hit hard cap {HARD_SYNC_MAX_FILES} — "
            f"raise is not available; split the tree or exclude paths"
        )
    totals = {
        "files_ingested": 0,
        "files_failed": 0,
        "files_skipped": skipped,
        "files_discovered": len(present),
        "docs_upserted": 0,
        "docs_failed": 0,
    }

    from astloom_cli.sync_progress import SyncProgressTracker

    scope_txt = f"{tenant}/{workspace}/{project}"
    tracker = SyncProgressTracker(
        scope=scope_txt,
        path=str(work),
        interval_sec=float(getattr(args, "progress_interval", 30) or 30),
    )
    cancelled = False
    try:
        total_batches = len(batches)
        for index, batch in enumerate(batches, start=1):
            print(
                f"   {ui.warn('…')} push batch {index}/{total_batches} "
                f"({len(batch.get('files') or [])} files)"
            )
            tracker.begin_phase()
            result = _run_ingest_push(
                settings, args, batch,
                on_progress=tracker,
                begin_phase=tracker.begin_phase,
            )
            totals["files_ingested"] += int(result.get("files_ingested") or 0)
            totals["files_failed"] += int(result.get("files_failed") or 0)
            totals["files_skipped"] += int(result.get("files_skipped") or 0)
            docs_part = result.get("docs") if isinstance(result.get("docs"), dict) else {}
            totals["docs_upserted"] += int(docs_part.get("docs_upserted") or 0)
            totals["docs_failed"] += int(docs_part.get("docs_failed") or 0)
    except BaseException:
        # Any non-clean exit (Ctrl+C, stream error line, HTTP failure) must not print
        # a green "finished / 100%" block ahead of the error message.
        cancelled = True
        raise
    finally:
        tracker.finish(cancelled=cancelled)

    ui.kv(
        "Push",
        f"ingested={totals['files_ingested']}  failed={totals['files_failed']}  "
        f"skipped={totals['files_skipped']}  discovered={totals['files_discovered']}  "
        f"docs_upserted={totals['docs_upserted']}  docs_failed={totals['docs_failed']}",
    )
    if totals["files_failed"] or totals["docs_failed"]:
        return 1
    return 0
