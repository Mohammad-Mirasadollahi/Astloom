"""Unit tests for NDJSON streaming helpers on content-push ingest."""

from __future__ import annotations

import asyncio
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from code_graph_service.api import build_app
from code_graph_service.api.ingest_push_stream import (
    build_progress_stream,
    iter_queue_with_heartbeat,
    ndjson_line,
    run_push_with_progress,
    wants_ndjson_stream,
)
from code_graph_service.core import CodeGraphService
from code_graph_service.domain.errors import ClientDisconnected
from code_graph_service.testing import InMemoryStore


def _headers(*, token: str | None = None) -> dict[str, str]:
    headers = {
        "X-Tenant-Id": "t",
        "X-Workspace-Id": "w",
        "X-Actor-Id": "tester",
        "Idempotency-Key": "key-1",
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def test_wants_ndjson_stream_from_accept():
    assert wants_ndjson_stream(accept="application/x-ndjson", stream_query=None) is True
    assert wants_ndjson_stream(accept="application/json", stream_query=None) is False


def test_wants_ndjson_stream_from_composite_accept():
    # Real clients/proxies send a list; the whole opt-in depends on the substring match.
    assert (
        wants_ndjson_stream(
            accept="application/json, application/x-ndjson;q=0.9", stream_query=None
        )
        is True
    )


@pytest.mark.parametrize("value", ["1", "true", "yes", " true "])
def test_wants_ndjson_stream_from_query(value):
    assert wants_ndjson_stream(accept=None, stream_query=value) is True


@pytest.mark.parametrize("value", ["0", "", "no", None])
def test_wants_ndjson_stream_query_off(value):
    assert wants_ndjson_stream(accept=None, stream_query=value) is False


def test_ndjson_line_is_one_json_object_plus_newline():
    raw = ndjson_line({"type": "progress", "done": 1, "total": 2})
    assert raw.endswith(b"\n")
    assert b"\n" not in raw[:-1]
    assert json.loads(raw.decode())["done"] == 1


def test_build_progress_stream_bridges_worker_thread_to_loop():
    async def main():
        q, emit = build_progress_stream()
        worker = asyncio.to_thread(run_push_with_progress, emit, lambda: {"files_ingested": 1})
        task = asyncio.create_task(worker)
        items = []
        while True:
            item = await q.get()
            if item is None:
                break
            items.append(item)
        await task
        return items

    assert asyncio.run(main()) == [{"type": "result", "files_ingested": 1}]


def test_run_push_with_progress_emits_result_then_sentinel():
    emitted: list[dict | None] = []
    run_push_with_progress(emitted.append, lambda: {"files_ingested": 3})
    assert emitted == [{"type": "result", "files_ingested": 3}, None]


def test_run_push_with_progress_emits_error_then_sentinel_on_client_disconnected():
    emitted: list[dict | None] = []
    run_push_with_progress(
        emitted.append, lambda: (_ for _ in ()).throw(ClientDisconnected("stopped"))
    )
    assert emitted == [{"type": "error", "message": "stopped"}, None]


def test_run_push_with_progress_emits_error_then_sentinel_on_unexpected_exception():
    emitted: list[dict | None] = []
    run_push_with_progress(emitted.append, lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert emitted[-1] is None
    assert emitted[0]["type"] == "error"
    assert "boom" in emitted[0]["message"]


def test_iter_queue_with_heartbeat_emits_when_worker_silent():
    async def main():
        q: asyncio.Queue[dict | None] = asyncio.Queue()
        items = []

        async def produce():
            await asyncio.sleep(0.2)
            q.put_nowait({"type": "result", "files_ingested": 1})
            q.put_nowait(None)

        producer = asyncio.create_task(produce())
        async for item in iter_queue_with_heartbeat(q, heartbeat_sec=0.05):
            items.append(item)
        await producer
        return items

    items = asyncio.run(main())
    assert any(i.get("status") == "heartbeat" for i in items)
    assert items[-1]["type"] == "result"


def test_ingest_push_ndjson_stream_emits_progress_then_result(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    service = CodeGraphService(InMemoryStore())
    client = TestClient(build_app(service))
    headers = {
        **_headers(token="secret-token-123456"),
        "Accept": "application/x-ndjson",
    }
    with client.stream(
        "POST",
        "/api/v1/projects/demo/graph/ingest-push",
        headers=headers,
        json={
            "files": [
                {
                    "file_path": "src/a.py",
                    "source": "def alpha():\n    return 1\n",
                    "language": "python",
                }
            ],
            "present_paths": ["src/a.py"],
        },
    ) as response:
        assert response.status_code == 200
        assert "ndjson" in response.headers.get("content-type", "")
        lines = [ln for ln in response.iter_lines() if ln]
    events = [json.loads(ln) for ln in lines]
    assert any(e.get("type") == "progress" for e in events)
    assert events[-1]["type"] == "result"
    assert events[-1]["files_ingested"] == 1


def test_ingest_push_ndjson_stream_via_query_param(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    client = TestClient(build_app(CodeGraphService(InMemoryStore())))
    with client.stream(
        "POST",
        "/api/v1/projects/demo/graph/ingest-push?stream=1",
        headers=_headers(token="secret-token-123456"),
        json={"files": [], "present_paths": []},
    ) as response:
        assert response.status_code == 200
        assert "ndjson" in response.headers.get("content-type", "")
        lines = [json.loads(ln) for ln in response.iter_lines() if ln]
    assert lines[0]["type"] == "progress"
    assert lines[0]["status"] == "registered"
    assert lines[-1]["type"] == "result"


def test_ingest_push_stream_emits_docs_phase(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    client = TestClient(build_app(CodeGraphService(InMemoryStore())))
    headers = {**_headers(token="secret-token-123456"), "Accept": "application/x-ndjson"}
    with client.stream(
        "POST",
        "/api/v1/projects/demo/graph/ingest-push?stream=1",
        headers=headers,
        json={
            "files": [],
            "present_paths": [],
            "docs": [
                {
                    "doc_id": "as.doc.test.a",
                    "relative_path": "docs/a.md",
                    "body": "# A\n",
                    "title": "A",
                    "linked_symbol_tokens": [],
                }
            ],
        },
    ) as response:
        lines = [ln for ln in response.iter_lines() if ln]
    events = [json.loads(ln) for ln in lines]
    docs_progress = [e for e in events if e.get("type") == "progress" and e.get("phase") == "docs"]
    assert docs_progress, events
    assert any(e.get("docs_indexed") == 1 for e in docs_progress), docs_progress
    assert events[-1]["type"] == "result"
    assert events[-1]["docs"]["docs_upserted"] == 1


def test_ingest_push_stream_cancel_signal_emits_error_then_closes(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from code_graph_service.api.job_cancel_registry import clear_jobs_for_tests

    clear_jobs_for_tests()
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    service = CodeGraphService(InMemoryStore())
    started = threading.Event()

    def blocking_ingest(self, *args, should_cancel=None, **kwargs):
        started.set()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if should_cancel and should_cancel():
                raise ClientDisconnected("cancelled via job signal")
            time.sleep(0.05)
        raise AssertionError("ingest should have been cancelled via job signal")

    monkeypatch.setattr(CodeGraphService, "ingest_pushed_sources", blocking_ingest)
    # Do not treat disconnect as cancel — only the explicit job signal, like the
    # non-stream job-cancel test.
    monkeypatch.setattr("starlette.requests.Request.is_disconnected", lambda self: False)

    client = TestClient(build_app(service))
    headers = {
        **_headers(token="secret-token-123456"),
        "Accept": "application/x-ndjson",
        "X-Sync-Job-Id": "job-stream-1",
    }

    def push() -> list[dict]:
        with client.stream(
            "POST",
            "/api/v1/projects/demo/graph/ingest-push",
            headers=headers,
            json={
                "files": [
                    {
                        "file_path": "src/a.py",
                        "source": "def a():\n    return 1\n",
                        "language": "python",
                    }
                ]
            },
        ) as response:
            assert response.status_code == 200
            return [json.loads(ln) for ln in response.iter_lines() if ln]

    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(push)
        assert started.wait(timeout=5)
        cancel = client.post(
            "/api/v1/projects/demo/graph/ingest-push/cancel",
            headers={
                "X-Tenant-Id": "t",
                "X-Workspace-Id": "w",
                "Authorization": "Bearer secret-token-123456",
            },
            json={"job_id": "job-stream-1"},
        )
        assert cancel.status_code == 200, cancel.text
        events = fut.result(timeout=5)

    assert events[-1]["type"] == "error"
    assert "cancelled" in events[-1]["message"].lower()


def test_ingest_push_without_stream_still_json(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    client = TestClient(build_app(CodeGraphService(InMemoryStore())))
    push = client.post(
        "/api/v1/projects/demo/graph/ingest-push",
        headers=_headers(token="secret-token-123456"),
        json={"files": [], "present_paths": []},
    )
    assert push.status_code == 200
    assert isinstance(push.json(), dict)
    assert "files_ingested" in push.json()
