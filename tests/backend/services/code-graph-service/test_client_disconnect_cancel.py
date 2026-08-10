"""Client disconnect must cancel in-flight ingest-push work."""

from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace

import pytest

from code_graph_service.api.client_cancel import run_until_client_disconnect
from code_graph_service.core import CodeGraphService
from code_graph_service.domain.errors import ClientDisconnected
from code_graph_service.domain.models import Scope
from code_graph_service.testing import InMemoryStore


def test_run_parallel_file_jobs_should_cancel_stops_pending(capsys):
    from code_graph_service.application.ingest.parallel_files import run_parallel_file_jobs

    started = threading.Event()
    release = threading.Event()
    cancel = threading.Event()
    ran: list[tuple[str, int]] = []
    lock = threading.Lock()

    def fn(index: int, item: int) -> None:
        with lock:
            ran.append(("start", item))
        if item == 0:
            started.set()
        assert release.wait(timeout=5)
        with lock:
            ran.append(("done", item))

    def worker() -> None:
        with pytest.raises(ClientDisconnected):
            run_parallel_file_jobs(
                workers=2,
                items=[0, 1, 2, 3],
                fn=fn,
                should_cancel=cancel.is_set,
            )

    thread = threading.Thread(target=worker)
    thread.start()
    assert started.wait(timeout=5)
    cancel.set()
    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive()

    started_items = {entry[1] for entry in ran if entry[0] == "start"}
    # At most the in-flight worker slot(s) may start one more item before cancel is observed.
    assert 3 not in started_items
    assert len(started_items) < 4
    out = capsys.readouterr().out
    assert "Stopping sync" in out
    assert "cancelling" in out


def test_ingest_pushed_sources_honours_should_cancel(monkeypatch):
    monkeypatch.setattr(
        "code_graph_service.application.ingest.pushed.sync_max_file_workers",
        lambda: 1,
    )
    service = CodeGraphService(InMemoryStore())
    scope = Scope(tenant_id="t", workspace_id="w", project_id="p")
    cancel = threading.Event()
    calls = {"n": 0}
    real_ingest = service.ingest_file

    def gated_ingest(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            cancel.set()
        return real_ingest(*args, **kwargs)

    service.ingest_file = gated_ingest  # type: ignore[method-assign]
    files = [
        {
            "file_path": f"src/f{i}.py",
            "source": f"def f{i}():\n    return {i}\n",
            "language": "python",
        }
        for i in range(8)
    ]
    with pytest.raises(ClientDisconnected):
        service.ingest_pushed_sources(
            scope,
            "actor",
            "corr",
            "idem",
            {"files": files, "include_outcomes": False},
            should_cancel=cancel.is_set,
        )
    assert calls["n"] < 8


def test_run_until_client_disconnect_cancels_blocked_work():
    cancel_seen = threading.Event()
    finished = threading.Event()

    async def is_disconnected() -> bool:
        return cancel_seen.is_set()

    request = SimpleNamespace(is_disconnected=is_disconnected)

    def work(should_cancel) -> str:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if should_cancel():
                raise ClientDisconnected()
            time.sleep(0.05)
        finished.set()
        return "done"

    async def main() -> None:
        async def trip() -> None:
            await asyncio.sleep(0.15)
            cancel_seen.set()

        watcher = asyncio.create_task(trip())
        with pytest.raises(ClientDisconnected):
            await run_until_client_disconnect(request, work)  # type: ignore[arg-type]
        await watcher
        assert not finished.is_set()

    asyncio.run(main())


def test_ingest_push_http_returns_499_when_disconnected(monkeypatch):
    from fastapi.testclient import TestClient

    from code_graph_service.api import build_app
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
                raise ClientDisconnected()
            time.sleep(0.05)
        raise AssertionError("ingest should have been cancelled")

    monkeypatch.setattr(
        CodeGraphService,
        "ingest_pushed_sources",
        blocking_ingest,
    )

    async def disconnect_after_start(self):
        return started.is_set()

    monkeypatch.setattr(
        "starlette.requests.Request.is_disconnected",
        disconnect_after_start,
    )

    client = TestClient(build_app(service))
    response = client.post(
        "/api/v1/projects/demo/graph/ingest-push",
        headers={
            "X-Tenant-Id": "t",
            "X-Workspace-Id": "w",
            "X-Actor-Id": "tester",
            "Idempotency-Key": "key-disconnect",
            "Authorization": "Bearer secret-token-123456",
        },
        json={
            "files": [
                {
                    "file_path": "src/a.py",
                    "source": "def a():\n    return 1\n",
                    "language": "python",
                }
            ]
        },
    )
    assert response.status_code == 499
    assert "disconnected" in response.json()["detail"].lower()


def _scope(**overrides: str) -> dict[str, str]:
    base = {"tenant_id": "t", "workspace_id": "w", "project_id": "p"}
    base.update(overrides)
    return base


def test_job_cancel_registry_targets_exact_job_only():
    from code_graph_service.api.job_cancel_registry import (
        cancel_job,
        clear_jobs_for_tests,
        register_job,
        unregister_job,
    )
    from code_graph_service.domain.errors import ConflictError

    clear_jobs_for_tests()
    scope = _scope()
    a = register_job("job-a", **scope)
    b = register_job("job-b", **scope)
    other = register_job("job-other", **_scope(project_id="other-project"))

    assert cancel_job("job-a", **scope) is True
    assert a.is_set()
    assert not b.is_set()
    assert not other.is_set()

    # Same job_id but wrong project/tenant must not cancel anything.
    assert cancel_job("job-b", **_scope(project_id="wrong")) is False
    assert not b.is_set()
    assert cancel_job("job-b", **_scope(tenant_id="wrong")) is False
    assert not b.is_set()

    assert cancel_job("missing", **scope) is False
    assert cancel_job("", **scope) is False

    with pytest.raises(ConflictError):
        register_job("job-b", **scope)

    unregister_job("job-b", b)
    assert cancel_job("job-b", **scope) is False
    assert not other.is_set()


def test_unregister_does_not_drop_different_event():
    from code_graph_service.api.job_cancel_registry import (
        cancel_job,
        clear_jobs_for_tests,
        register_job,
        unregister_job,
    )

    clear_jobs_for_tests()
    scope = _scope()
    first = register_job("job-x", **scope)
    first.set()
    # Finished job may be replaced by a new registration with the same id.
    second = register_job("job-x", **scope)
    unregister_job("job-x", first)  # stale handle must not remove the live one
    assert cancel_job("job-x", **scope) is True
    assert second.is_set()


def test_ingest_push_http_cancel_signal_stops_exact_job(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from fastapi.testclient import TestClient

    from code_graph_service.api import build_app
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
                raise ClientDisconnected()
            time.sleep(0.05)
        raise AssertionError("ingest should have been cancelled via job signal")

    monkeypatch.setattr(CodeGraphService, "ingest_pushed_sources", blocking_ingest)
    # Do not treat disconnect as cancel — only the explicit job signal.
    monkeypatch.setattr(
        "starlette.requests.Request.is_disconnected",
        lambda self: False,
    )

    client = TestClient(build_app(service))
    headers = {
        "X-Tenant-Id": "t",
        "X-Workspace-Id": "w",
        "X-Actor-Id": "tester",
        "Idempotency-Key": "key-job",
        "Authorization": "Bearer secret-token-123456",
        "X-Sync-Job-Id": "job-exact-1",
    }

    def push() -> object:
        return client.post(
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
        )

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
            json={"job_id": "job-exact-1"},
        )
        assert cancel.status_code == 200, cancel.text
        assert cancel.json()["cancelled"] is True
        response = fut.result(timeout=5)

    assert response.status_code == 499


def test_client_ctrl_c_sends_cancel_signal(monkeypatch):
    from argparse import Namespace

    from astloom_cli.connect_config import ConnectSettings
    from astloom_cli.connect_flow import client_push as cp

    seen: dict[str, str] = {}

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None):
            assert "ingest-push/cancel" in url
            seen["cancel_job"] = str((json or {}).get("job_id") or "")
            return SimpleNamespace(status_code=200, json=lambda: {"ok": True})

    def _stream(method, url, *, headers=None, json=None, timeout=None, verify=None):
        # Ctrl+C while the streaming POST is open (before the response is entered).
        seen["push_job"] = str((headers or {}).get("X-Sync-Job-Id") or "")
        raise KeyboardInterrupt

    class _Httpx:
        Client = _Client
        HTTPError = Exception
        stream = staticmethod(_stream)

    monkeypatch.setattr(cp, "httpx_verify", lambda _s: True)
    import sys

    monkeypatch.setitem(sys.modules, "httpx", _Httpx)

    settings = ConnectSettings(
        graph_url="https://g.example",
        api_token="tokentokentoken12",
        project="p",
        tenant="t",
        workspace="w",
    )
    with pytest.raises(KeyboardInterrupt):
        cp._run_ingest_push_http(settings, Namespace(project="p", sync_mode=""), {"files": []})
    assert seen.get("push_job")
    assert seen.get("cancel_job") == seen.get("push_job")
