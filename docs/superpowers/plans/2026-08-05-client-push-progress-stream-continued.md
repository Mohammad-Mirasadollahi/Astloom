---
doc_id: as.doc.sea.client-push-progress-stream-plan-continued
title: Client content-push progress stream implementation plan (continued)
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-engineering
summary: Tasks 4–6 of the NDJSON ingest-push progress stream plan — client consumer, SyncProgressTracker
  wiring, and documentation updates.
tags:
- plan
- sync
- ingest
- client
- progress
phase: 08-software-engineering-architecture
canonical_path: docs/superpowers/plans/2026-08-05-client-push-progress-stream-continued.md
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
- backend/packages/astloom_cli/connect_flow/client_push.py::build_push_files
- backend/packages/astloom_cli/connect_flow/client_push.py::client_push_sync
- backend/packages/astloom_cli/connect_flow/client_push.py::_run_ingest_push_http
- backend/packages/astloom_cli/connect_flow/push_stream.py::consume_ndjson_ingest_push
- backend/packages/astloom_cli/connect_flow/push_stream.py::stream_accept_headers
- backend/packages/astloom_cli/sync_progress/tracker.py::SyncProgressTracker
- backend/packages/astloom_cli/sync_progress/render.py::print_progress_line
related_docs:
- docs/superpowers/plans/2026-08-05-client-push-progress-stream.md
- docs/superpowers/specs/2026-08-05-client-push-progress-stream-design.md
- docs/superpowers/specs/2026-08-10-client-sync-auto-discovery-inventory-design.md
---

# Client content-push progress stream implementation plan (continued)

## Purpose

Continuation of the server stream plan: client NDJSON consumer, wiring
`SyncProgressTracker` into `astloom-client sync`, and doc updates.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Complete [part 1](./2026-08-05-client-push-progress-stream.md) (Tasks 1–3) first.

**Goal / Architecture / Global Constraints:** same as part 1 and
`docs/superpowers/specs/2026-08-05-client-push-progress-stream-design.md`.

---

### Task 4: Client NDJSON consumer

**Files:**
- Create: `backend/packages/astloom_cli/connect_flow/push_stream.py`
- Create: `tests/backend/tools/astloom-cli/test_push_stream.py`

**Interfaces:**
- Produces:
  - `stream_accept_headers() -> dict[str, str]` → `{"Accept": "application/x-ndjson"}`
  - `consume_ndjson_ingest_push(*, lines: Iterable[str], on_progress: Callable[[dict], None], begin_phase: Callable[[], None] | None = None) -> dict[str, Any]`
    - For each parsed object: if `type==progress`, optionally `begin_phase()` when `phase` changes; call `on_progress(event_without_type)`; if `type==result` return payload without `type`; if `type==error` raise `SystemExit(f"error: ingest-push stream: {message}")`
    - If stream ends without `result` → `SystemExit("error: ingest-push stream ended without result")`

- [ ] **Step 1: Failing tests**

```python
from astloom_cli.connect_flow.push_stream import (
    consume_ndjson_ingest_push,
    stream_accept_headers,
)

def test_stream_accept_headers():
    assert stream_accept_headers()["Accept"] == "application/x-ndjson"

def test_consume_ndjson_feeds_progress_and_returns_result():
    seen: list[dict] = []
    phases: list[str] = []
    lines = [
        '{"type":"progress","phase":"ingest","done":0,"total":2}\n',
        '{"type":"progress","phase":"ingest","done":1,"total":2,"file":"a.py"}\n',
        '{"type":"progress","phase":"docs","done":0,"total":1}\n',
        '{"type":"result","files_ingested":1,"docs":{"docs_upserted":1}}\n',
    ]
    def begin():
        phases.append("begin")
    out = consume_ndjson_ingest_push(
        lines=lines,
        on_progress=lambda e: seen.append(e),
        begin_phase=begin,
    )
    assert out["files_ingested"] == 1
    assert out["docs"]["docs_upserted"] == 1
    assert any(e.get("done") == 1 for e in seen)
    assert "begin" in phases  # at least when phase flips to docs

def test_consume_ndjson_error_exits():
    import pytest
    with pytest.raises(SystemExit, match="ingest-push stream"):
        consume_ndjson_ingest_push(
            lines=['{"type":"error","message":"boom"}\n'],
            on_progress=lambda e: None,
        )
```

- [ ] **Step 2: Run — FAIL**

```bash
PYTHONPATH=backend/packages:backend/services/code-graph-service/src \
  .venv/bin/python -m pytest tests/backend/tools/astloom-cli/test_push_stream.py -v
```

(Use the same PYTHONPATH pattern as other `tests/backend/tools/astloom-cli` tests in this repo.)

- [ ] **Step 3: Implement `push_stream.py`**

```python
def consume_ndjson_ingest_push(*, lines, on_progress, begin_phase=None):
    import json
    last_phase = None
    for raw in lines:
        text = raw.strip() if isinstance(raw, str) else raw.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        obj = json.loads(text)
        kind = obj.get("type")
        if kind == "progress":
            phase = obj.get("phase")
            if begin_phase and phase != last_phase and last_phase is not None:
                begin_phase()
            last_phase = phase
            event = {k: v for k, v in obj.items() if k != "type"}
            on_progress(event)
        elif kind == "result":
            return {k: v for k, v in obj.items() if k != "type"}
        elif kind == "error":
            raise SystemExit(f"error: ingest-push stream: {obj.get('message') or 'unknown'}")
        else:
            raise SystemExit(f"error: ingest-push stream: unknown type {kind!r}")
    raise SystemExit("error: ingest-push stream ended without result")
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit only if the user explicitly asks**

---

### Task 5: Wire HTTP client + `client_push_sync` tracker

**Files:**
- Modify: `backend/packages/astloom_cli/connect_flow/client_push.py` (`_run_ingest_push_http`, `client_push_sync`)
- Modify: `tests/backend/tools/astloom-cli/test_client_push_ingest.py` and/or `test_push_stream.py`

**Interfaces:**
- Consumes: `stream_accept_headers`, `consume_ndjson_ingest_push`, `SyncProgressTracker`
- Produces: live console progress during `astloom-client sync`

- [ ] **Step 1: Failing test — HTTP path requests NDJSON and feeds tracker**

Mock httpx so `post(..., stream=True)` yields an object with `iter_lines()` returning progress+result, and assert:

1. Request headers include `Accept: application/x-ndjson` (and existing auth headers).
2. A spy/`list` on_progress receives at least one event **or** `SyncProgressTracker.update` is called (prefer injecting a simple callable via a new optional `on_progress` argument on `_run_ingest_push_http` for testability, while `client_push_sync` passes the tracker).

```python
def test_run_ingest_push_http_consumes_ndjson(monkeypatch):
    from types import SimpleNamespace, ModuleType
    import sys
    from astloom_cli.connect_flow import client_push as cp

    calls = {}
    class Resp:
        status_code = 200
        def raise_for_status(self): ...
        def iter_lines(self):
            yield '{"type":"progress","phase":"ingest","done":1,"total":1,"file":"a.py"}'
            yield '{"type":"result","files_ingested":1,"files_failed":0}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def post(url, headers=None, json=None, timeout=None, verify=None):
        calls["headers"] = dict(headers or {})
        return Resp()

    fake = ModuleType("httpx")
    fake.HTTPError = Exception
    fake.post = post  # if code uses client.stream, fake that instead
    # Prefer implementing with: httpx.stream("POST", ...) as response
    monkeypatch.setitem(sys.modules, "httpx", fake)

    seen = []
    settings = SimpleNamespace(
        graph_url="https://example.test",
        api_token="tok",
        tenant="t",
        workspace="w",
        project="p",
        actor_id="a",
        # plus whatever _http_headers / httpx_verify need
    )
    # Patch httpx_verify and _http_headers as existing tests do
    out = cp._run_ingest_push_http(
        settings,
        Namespace(project="p", sync_mode=""),
        {"files": []},
        on_progress=lambda e: seen.append(e),
    )
    assert out["files_ingested"] == 1
    assert calls["headers"].get("Accept") == "application/x-ndjson"
    assert seen
```

Adjust the fake to match the real call shape you implement (`httpx.stream` context manager is preferred over `post`).

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

In `_run_ingest_push_http`:

```python
def _run_ingest_push_http(settings, args, body, *, on_progress=None, begin_phase=None):
    ...
    headers = {**_http_headers(settings), **stream_accept_headers()}
    with httpx.stream(
        "POST", url, headers=headers, json=payload, timeout=600.0, verify=httpx_verify(settings)
    ) as response:
        if response.status_code >= 400:
            # read body for http_error_message if needed
            raise SystemExit(...)
        if on_progress is None:
            # still parse stream for result (client always requests stream)
            return consume_ndjson_ingest_push(lines=response.iter_lines(), on_progress=lambda e: None)
        return consume_ndjson_ingest_push(
            lines=response.iter_lines(),
            on_progress=on_progress,
            begin_phase=begin_phase,
        )
```

In `client_push_sync` after consent / note lines:

```python
from astloom_cli.sync_progress import SyncProgressTracker
scope_txt = f"{settings.tenant}/{settings.workspace}/{settings.project}"
tracker = SyncProgressTracker(
    scope=scope_txt,
    path=str(work),
    interval_sec=float(getattr(args, "progress_interval", 30) or 30),
)
...
for index, batch in enumerate(...):
    print(f"   {ui.warn('…')} push batch {index} (...)")  # keep as phase marker
    result = _run_ingest_push(
        settings, args, batch,
        on_progress=tracker,
        begin_phase=tracker.begin_phase,
    )
```

Propagate `on_progress` / `begin_phase` through `_run_ingest_push` → `_run_ingest_push_http`.

Fallback: if response `Content-Type` is JSON (old server), `response.json()` once and return — detect via content-type or first-byte peek. Minimum: if `iter_lines` yields a single JSON object without `type`, treat as result dict (compat).

```python
# inside consume or HTTP wrapper:
# if content-type includes application/json and not ndjson → response.json()
```

- [ ] **Step 4: Run client tests — PASS**

```bash
.venv/bin/python -m pytest \
  tests/backend/tools/astloom-cli/test_push_stream.py \
  tests/backend/tools/astloom-cli/test_client_push_ingest.py -q
```

- [ ] **Step 5: Commit only if the user explicitly asks**

---

### Task 6: Docs touch-up + spec status

**Files:**
- Modify: `docs/superpowers/specs/2026-08-05-client-push-progress-stream-design.md` (`status: active`, bump `doc_version` / `updated_at`)
- Modify: `docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding-continued.md` — one short note that content-push streams NDJSON progress (same UI as local sync); bump revision stamps
- Modify: Progress bullet in `docs/08-software-engineering-architecture/42-astloom-cli-command-reference-continued-continued-continued.md` if it currently implies progress is local-only — add that `astloom-client sync` streams the same tracker lines over HTTPS

- [ ] **Step 1:** Apply factual one-paragraph / table-row updates only (no new speculative features).
- [ ] **Step 2:** `astloom docs-standards` — new/edited docs conforming.
- [ ] **Step 3:** Manual smoke (optional): on a connected client host, run `astloom-client sync` and confirm percent / ETA / symbols lines appear during a large batch.
- [ ] **Step 4:** Commit only if the user explicitly asks

---

## Spec coverage checklist

| Spec requirement | Task |
| --- | --- |
| NDJSON opt-in Accept / `stream=1` | 1–2 |
| `progress` / `result` / `error` line types | 2, 4 |
| Non-stream JSON unchanged | 2 |
| Reuse `ingest_pushed_sources` `on_progress` (+ embeddings) | 2 |
| Docs phase progress | 3 |
| Client `SyncProgressTracker` + `--progress-interval` | 5 |
| No source bodies in progress | 2 (`_on_progress` strips `source`) |
| Fail closed on stream errors | 4 |
| Auth unchanged | 2 (existing `ContentPushHttpAuth`) |

## Placeholder / consistency self-review

- No TBD / “similar to Task N” without code.
- Event field names match tracker: `phase`, `done`, `total`, `file`, `status`, `symbols_indexed`, `edges_written`, …
- Type constants `progress` / `result` / `error` shared conceptually between server and client.

## Related Documents

- [Part 1 (Tasks 1–3)](./2026-08-05-client-push-progress-stream.md)
- [Design](../specs/2026-08-05-client-push-progress-stream-design.md)

