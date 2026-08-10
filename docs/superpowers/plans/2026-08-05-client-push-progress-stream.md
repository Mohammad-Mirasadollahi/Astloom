---
doc_id: as.doc.sea.client-push-progress-stream-plan
title: Client content-push progress stream implementation plan
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-engineering
summary: Bite-sized TDD plan to stream SyncProgressTracker-compatible NDJSON events from HTTPS
  ingest-push to astloom-client for server-parity progress UI.
tags:
- plan
- sync
- ingest
- client
- progress
phase: 08-software-engineering-architecture
canonical_path: docs/superpowers/plans/2026-08-05-client-push-progress-stream.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
doc_version: 1.1.1
updated_at: 2026-08-10
linked_symbols:
- backend/services/code-graph-service/src/code_graph_service/api/ingest.py::register
- backend/services/code-graph-service/src/code_graph_service/api/ingest.py::ingest_push
- backend/services/code-graph-service/src/code_graph_service/api/ingest_push_stream.py::wants_ndjson_stream
- backend/packages/astloom_cli/connect_flow/client_push.py::build_push_files
- backend/packages/astloom_cli/connect_flow/client_push.py::_run_ingest_push_http
- backend/packages/astloom_cli/connect_flow/push_stream.py::consume_ndjson_ingest_push
- backend/packages/astloom_cli/connect_flow/push_stream.py::stream_accept_headers
- backend/packages/astloom_cli/sync_progress/tracker.py::SyncProgressTracker
related_docs:
- docs/superpowers/specs/2026-08-05-client-push-progress-stream-design.md
- docs/superpowers/specs/2026-08-04-client-direct-ingest-no-stage-design.md
- docs/superpowers/specs/2026-08-10-client-sync-auto-discovery-inventory-design.md
---

# Client content-push progress stream Implementation Plan

## Purpose

Executable TDD plan (Tasks 1–3) for server-side NDJSON progress streaming on
`ingest-push`. Client wiring continues in the sibling plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Continuation:** [Client content-push progress stream plan (continued)](./2026-08-05-client-push-progress-stream-continued.md) (Tasks 4–6).

## Global Constraints

- Normative design: `docs/superpowers/specs/2026-08-05-client-push-progress-stream-design.md`.
- Do not invent fake client-only upload percent; progress must come from server `on_progress`.
- Do not change `print_progress_line` layout.
- Do not revive SSH content-push.
- Non-stream clients must still receive a single JSON object (backward compatible).
- Same bearer / loopback auth; never put file source bodies in progress lines.
- English-only committed docs; tests under repository `tests/`.
- Create git commits only when the user explicitly asks.

## File map

| File | Responsibility |
| --- | --- |
| `backend/services/code-graph-service/src/code_graph_service/api/ingest_push_stream.py` | Detect stream mode; NDJSON encode; queue + generator for progress/result/error |
| `backend/services/code-graph-service/src/code_graph_service/api/ingest.py` | Branch ingest-push to StreamingResponse vs JSON; docs-phase progress |
| `backend/packages/astloom_cli/connect_flow/push_stream.py` | Client: request stream headers; parse NDJSON; feed tracker; return result |
| `backend/packages/astloom_cli/connect_flow/client_push.py` | Construct tracker; pass into HTTP push; `begin_phase` across batches |
| `tests/backend/services/code-graph-service/test_ingest_push_stream.py` | Server stream + non-stream + docs progress |
| `tests/backend/tools/astloom-cli/test_push_stream.py` | Client NDJSON consumer + tracker wiring |

---

### Task 1: Server NDJSON helpers (pure)

**Files:**
- Create: `backend/services/code-graph-service/src/code_graph_service/api/ingest_push_stream.py`
- Create: `tests/backend/services/code-graph-service/test_ingest_push_stream.py`

**Interfaces:**
- Produces:
  - `wants_ndjson_stream(*, accept: str | None, stream_query: str | None) -> bool`
  - `ndjson_line(payload: dict) -> bytes` (UTF-8 JSON + `\n`)
  - `PROGRESS = "progress"`, `RESULT = "result"`, `ERROR = "error"` type constants

- [ ] **Step 1: Write the failing tests**

```python
from code_graph_service.api.ingest_push_stream import (
    wants_ndjson_stream,
    ndjson_line,
)

def test_wants_ndjson_stream_from_accept():
    assert wants_ndjson_stream(accept="application/x-ndjson", stream_query=None) is True
    assert wants_ndjson_stream(accept="application/json", stream_query=None) is False

def test_wants_ndjson_stream_from_query():
    assert wants_ndjson_stream(accept=None, stream_query="1") is True
    assert wants_ndjson_stream(accept=None, stream_query="0") is False

def test_ndjson_line_is_one_json_object_plus_newline():
    raw = ndjson_line({"type": "progress", "done": 1, "total": 2})
    assert raw.endswith(b"\n")
    assert b"\n" not in raw[:-1]
    import json
    assert json.loads(raw.decode())["done"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/Astloom
PYTHONPATH=backend/services/code-graph-service/src:.venv/lib/python3.*/site-packages \
  .venv/bin/python -m pytest tests/backend/services/code-graph-service/test_ingest_push_stream.py::test_wants_ndjson_stream_from_accept -v
```

Expected: FAIL (module missing). Prefer the project’s usual pytest invocation from `tests/backend/services/code-graph-service/README.md` if PYTHONPATH differs.

- [ ] **Step 3: Minimal implementation**

```python
"""NDJSON framing for streaming content-push ingest progress."""

from __future__ import annotations

import json
from typing import Any

PROGRESS = "progress"
RESULT = "result"
ERROR = "error"


def wants_ndjson_stream(*, accept: str | None, stream_query: str | None) -> bool:
    if (stream_query or "").strip() in {"1", "true", "yes"}:
        return True
    text = (accept or "").lower()
    return "application/x-ndjson" in text


def ndjson_line(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
.venv/bin/python -m pytest tests/backend/services/code-graph-service/test_ingest_push_stream.py -q
```

- [ ] **Step 5: Commit only if the user explicitly asks**

---

### Task 2: Stream generator + HTTP ingest-push branch

**Files:**
- Modify: `backend/services/code-graph-service/src/code_graph_service/api/ingest_push_stream.py`
- Modify: `backend/services/code-graph-service/src/code_graph_service/api/ingest.py` (`ingest_push`)
- Modify: `tests/backend/services/code-graph-service/test_ingest_push_stream.py`
- Modify: `tests/backend/services/code-graph-service/test_content_push_http.py` (keep existing non-stream assertions green)

**Interfaces:**
- Consumes: `wants_ndjson_stream`, `ndjson_line`, `PROGRESS`/`RESULT`/`ERROR`
- Produces:
  - `build_progress_queue() -> queue.Queue` (sentinel-safe)
  - `run_push_with_progress(...)` sync worker that calls `ingest_pushed_sources` with `on_progress` putting `{"type":"progress", **event}` then puts `{"type":"result", **out}` or `{"type":"error","message":...}`
  - `ingest_push` returns `StreamingResponse` when stream requested; else existing JSON via `run_until_client_disconnect`

**Design notes (implement exactly):**

1. When streaming: create `queue.Queue`, pass `on_progress` that does `q.put({"type": PROGRESS, **event})` (never include `source`).
2. Run the same `_work` logic (ingest + docs) in `asyncio.to_thread`, putting RESULT or ERROR on the queue when finished; use a sentinel object or `None` after the terminal line so the async generator stops.
3. Keep disconnect cancel: if `should_cancel()` fires, put ERROR / raise `ClientDisconnected` consistently with today’s 499 path for non-stream; for stream, emit `{"type":"error","message":"..."}` then close.
4. Response headers: `Content-Type: application/x-ndjson`.
5. Non-stream path: **do not** put `on_progress` in payload; behavior unchanged.

- [ ] **Step 1: Failing HTTP stream test**

```python
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
    import json
    events = [json.loads(ln) for ln in lines]
    assert any(e.get("type") == "progress" for e in events)
    assert events[-1]["type"] == "result"
    assert events[-1]["files_ingested"] == 1


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
```

Reuse `_headers` from `test_content_push_http.py` (import or duplicate the small helper in the new test module).

- [ ] **Step 2: Run — expect FAIL** (no StreamingResponse branch yet)

```bash
.venv/bin/python -m pytest \
  tests/backend/services/code-graph-service/test_ingest_push_stream.py::test_ingest_push_ndjson_stream_emits_progress_then_result -v
```

- [ ] **Step 3: Implement stream branch in `ingest.py` + queue helper**

Skeleton for the worker progress hook:

```python
def _on_progress(event: dict[str, Any]) -> None:
    safe = {k: v for k, v in event.items() if k != "source"}
    q.put({"type": PROGRESS, **safe})
```

Pass `"on_progress": _on_progress` only in stream mode inside the payload dict for `ingest_pushed_sources`.

Async generator sketch:

```python
async def _gen():
    while True:
        item = await asyncio.to_thread(q.get)
        if item is None:
            break
        yield ndjson_line(item)
        if item.get("type") in {RESULT, ERROR}:
            q.put(None)  # or break after terminal
            break
```

Prefer one clear sentinel: worker always `q.put(terminal); q.put(None)` and generator yields until `None`.

Return:

```python
return StreamingResponse(_gen(), media_type="application/x-ndjson")
```

Return type annotation of `ingest_push` becomes `dict[str, Any] | StreamingResponse`.

- [ ] **Step 4: Run stream + existing content-push HTTP tests — expect PASS**

```bash
.venv/bin/python -m pytest \
  tests/backend/services/code-graph-service/test_ingest_push_stream.py \
  tests/backend/services/code-graph-service/test_content_push_http.py -q
```

- [ ] **Step 5: Commit only if the user explicitly asks**

---

### Task 3: Docs-phase progress events on server

**Files:**
- Modify: `backend/services/code-graph-service/src/code_graph_service/api/ingest.py` (docs loop inside stream `_work`)
- Modify: `tests/backend/services/code-graph-service/test_ingest_push_stream.py`

**Interfaces:**
- Consumes: same queue / `on_progress` sink as Task 2
- Produces: progress events with `phase="docs"`, `done`, `total=len(docs)`, `file=relative_path`, plus final `docs` block on RESULT (unchanged shape)

- [ ] **Step 1: Failing test**

```python
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
    import json
    events = [json.loads(ln) for ln in lines]
    docs_progress = [e for e in events if e.get("type") == "progress" and e.get("phase") == "docs"]
    assert docs_progress, events
    assert events[-1]["type"] == "result"
    assert events[-1]["docs"]["docs_upserted"] == 1
```

- [ ] **Step 2: Run — expect FAIL** (no docs progress yet)

- [ ] **Step 3: Emit docs progress in stream `_work`**

Before the docs loop (stream mode only), emit `done=0, total=N, phase="docs", status="started"`. After each upsert, emit `done=i, total=N, phase="docs", file=rel, status="ok"|"failed"`. Non-stream path: no progress emissions (keep quiet).

- [ ] **Step 4: Run Task 2+3 tests — PASS**

```bash
.venv/bin/python -m pytest tests/backend/services/code-graph-service/test_ingest_push_stream.py -q
```

- [ ] **Step 5: Commit only if the user explicitly asks**

---

## Related Documents

- [Design](../specs/2026-08-05-client-push-progress-stream-design.md)
- [Continued plan (Tasks 4–6)](./2026-08-05-client-push-progress-stream-continued.md)

