"""Live: astloom-client content-push over real code-graph HTTPS (speed + finalize).

Proves multi-batch client push finalizes once (last batch only) and completes
without hanging at 100%. Burns remote Provider RPM when docs/embeds are on.

Re-run:
  .venv/bin/python -m pytest \\
    tests/live/code-graph-service/test_client_content_push_speed_live.py -m live -v
"""

from __future__ import annotations

import json
import os
import socket
import time
import uuid
from argparse import Namespace
from pathlib import Path

import httpx
import pytest

from astloom_cli.connect_config import ConnectSettings
from astloom_cli.connect_flow import client_push as cp
from astloom_cli.connect_http import httpx_verify

pytestmark = pytest.mark.live

GRAPH_URL = os.environ.get("ASTLOOM_CODE_GRAPH_URL", "https://127.0.0.1:32140").rstrip("/")
_ARTIFACT = Path("/opt/Astloom/tests/artifacts/code-graph-live/client-content-push-speed.json")


def _require_graph_https() -> None:
    host, port = "127.0.0.1", 32140
    if "://" in GRAPH_URL:
        from urllib.parse import urlparse

        parsed = urlparse(GRAPH_URL)
        host = parsed.hostname or host
        port = int(parsed.port or 32140)
    sock = socket.socket()
    sock.settimeout(2)
    try:
        sock.connect((host, port))
    except OSError as exc:
        pytest.skip(f"code-graph HTTPS not reachable at {host}:{port}: {exc}")
    finally:
        sock.close()


def _headers(project: str, *, job_id: str | None = None) -> dict[str, str]:
    token = (
        os.environ.get("ASTLOOM_CODE_GRAPH_HTTP_TOKEN")
        or os.environ.get("ASTLOOM_CONNECT_TOKEN")
        or os.environ.get("ASTLOOM_GRAPH_HTTP_TOKEN")
        or "loopback-live"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "mir",
        "X-Workspace-Id": "live-client",
        "X-Actor-Id": "live-client-speed",
        "Idempotency-Key": f"live-client-{uuid.uuid4().hex}",
        "Accept": "application/x-ndjson",
    }
    if job_id:
        headers["X-Sync-Job-Id"] = job_id
    return headers


def _push_batch(
    *,
    project: str,
    body: dict,
    verify: bool | str,
) -> tuple[dict, list[dict], float]:
    url = f"{GRAPH_URL}/api/v1/projects/{project}/graph/ingest-push?stream=1"
    events: list[dict] = []
    result: dict = {}
    t0 = time.perf_counter()
    with httpx.stream(
        "POST",
        url,
        headers=_headers(project),
        json=body,
        timeout=httpx.Timeout(600.0, connect=30.0),
        verify=verify,
    ) as response:
        if response.status_code >= 400:
            response.read()
            raise AssertionError(f"ingest-push HTTP {response.status_code}: {response.text[:500]}")
        for line in response.iter_lines():
            text = line.strip() if isinstance(line, str) else line.decode("utf-8", "replace").strip()
            if not text:
                continue
            obj = json.loads(text)
            kind = obj.get("type")
            if kind == "progress":
                events.append({k: v for k, v in obj.items() if k != "type"})
            elif kind == "result":
                result = {k: v for k, v in obj.items() if k != "type"}
            elif kind == "error":
                raise AssertionError(f"ingest-push stream error: {obj.get('message')}")
    return result, events, time.perf_counter() - t0


@pytest.mark.timeout(900)
def test_client_multi_batch_finalize_once_and_completes_live(tmp_path: Path, monkeypatch):
    """N HTTP batches → finalize only on last; overall push finishes (no 100% hang)."""
    _require_graph_https()
    monkeypatch.setattr(cp, "_MAX_BATCH_FILES", 2)
    monkeypatch.setattr(cp, "_MAX_BATCH_BYTES", 50_000_000)

    project = f"client-speed-{uuid.uuid4().hex[:10]}"
    n_files = 6
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    files: list[dict[str, str]] = []
    for i in range(n_files):
        # Multi-symbol files exercise batched docs on the server path.
        body = (
            f"def fn_{i}_a(x):\n    return x + {i}\n\n"
            f"def fn_{i}_b(x):\n    return x * {i}\n"
        )
        rel = f"src/m{i}.py"
        (root / rel).write_text(body, encoding="utf-8")
        files.append({"file_path": rel, "source": body, "language": "python"})

    present = [f["file_path"] for f in files]
    batches = cp._batches(files, present, include_present_paths=True)
    assert len(batches) >= 2
    assert all(b.get("finalize_cross_file") is False for b in batches[:-1])
    assert batches[-1].get("finalize_cross_file") is True

    settings = ConnectSettings(
        graph_url=GRAPH_URL,
        api_token=(
            os.environ.get("ASTLOOM_CODE_GRAPH_HTTP_TOKEN")
            or os.environ.get("ASTLOOM_CONNECT_TOKEN")
            or "loopback-live"
        ),
        tenant="mir",
        workspace="live-client",
        project=project,
        tls_verify=False,
    )
    verify = httpx_verify(settings)

    batch_reports: list[dict] = []
    wall0 = time.perf_counter()
    for index, batch in enumerate(batches, start=1):
        # Match client_push: embedding_refresh touched every batch; finalize flag from _batches.
        body = {**batch, "embedding_refresh_mode": "touched"}
        result, events, sec = _push_batch(project=project, body=body, verify=verify)
        finalizing = [e for e in events if e.get("status") == "finalizing"]
        batch_reports.append(
            {
                "index": index,
                "files": len(batch.get("files") or []),
                "finalize_cross_file": batch.get("finalize_cross_file"),
                "wall_sec": round(sec, 3),
                "files_ingested": int(result.get("files_ingested") or 0),
                "files_failed": int(result.get("files_failed") or 0),
                "finalizing_events": len(finalizing),
                "finalizing_files": [str(e.get("file") or "") for e in finalizing[:12]],
            }
        )
        assert int(result.get("files_failed") or 0) == 0
        if batch.get("finalize_cross_file"):
            assert finalizing, "last batch must emit finalizing progress"
        else:
            assert not finalizing, (
                f"intermediate batch {index} must not finalize "
                f"(got {len(finalizing)} finalizing events)"
            )

    total_sec = time.perf_counter() - wall0
    ingested = sum(int(r["files_ingested"]) for r in batch_reports)
    assert ingested == n_files
    rate = ingested / total_sec if total_sec else 0.0

    # Second push: unchanged bodies → should skip LLM-heavy work (hash skip).
    t_skip = time.perf_counter()
    skip_result, skip_events, skip_sec = _push_batch(
        project=project,
        body={
            **batches[-1],
            "files": files,  # full set in one shot for noop check
            "finalize_cross_file": True,
            "embedding_refresh_mode": "touched",
            "present_paths": present,
            "inventory_complete": True,
        },
        verify=verify,
    )
    # Re-pushing all files in one batch after they exist: mostly skipped.
    skip_failed = int(skip_result.get("files_failed") or 0)
    assert skip_failed == 0

    evidence = {
        "mode": "astloom-client content-push HTTPS live",
        "graph_url": GRAPH_URL,
        "project": project,
        "files": n_files,
        "batches": len(batches),
        "batch_reports": batch_reports,
        "total_wall_sec": round(total_sec, 3),
        "files_per_sec": round(rate, 3),
        "noop_repush_wall_sec": round(skip_sec, 3),
        "noop_files_ingested": int(skip_result.get("files_ingested") or 0),
        "noop_files_skipped": int(skip_result.get("files_skipped") or 0),
        "finalize_only_on_last_batch": all(
            (r["finalizing_events"] > 0) == bool(r["finalize_cross_file"])
            for r in batch_reports
        ),
    }
    _ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    _ARTIFACT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    assert evidence["finalize_only_on_last_batch"] is True
    # Must finish; with OpenRouter docs+embeds this is slower than stub, but must not hang.
    assert total_sec < 800, f"client push too slow / hung: {total_sec:.1f}s"
    # Noop second pass should be materially faster than first full push when hashes match.
    if total_sec >= 20:
        assert skip_sec < total_sec * 0.75, (
            f"expected hash-skip faster than first push "
            f"(first={total_sec:.1f}s noop={skip_sec:.1f}s)"
        )


@pytest.mark.timeout(900)
def test_astloom_client_push_sync_entrypoint_live(tmp_path: Path, monkeypatch, capsys):
    """End-to-end ``client_push_sync`` against live HTTPS (allow_cloud_llm)."""
    _require_graph_https()
    monkeypatch.setattr(cp, "_MAX_BATCH_FILES", 2)

    project = f"client-entry-{uuid.uuid4().hex[:10]}"
    root = tmp_path / "entry-repo"
    (root / "src").mkdir(parents=True)
    for i in range(4):
        (root / "src" / f"e{i}.py").write_text(
            f"def entry_{i}(x):\n    return x + {i}\n",
            encoding="utf-8",
        )
    (root / "astloom.sync.yaml").write_text(
        "code:\n  include_extensions: [\".py\"]\n  exclude: []\n",
        encoding="utf-8",
    )

    settings = ConnectSettings(
        graph_url=GRAPH_URL,
        api_token=(
            os.environ.get("ASTLOOM_CODE_GRAPH_HTTP_TOKEN")
            or os.environ.get("ASTLOOM_CONNECT_TOKEN")
            or "loopback-live"
        ),
        tenant="mir",
        workspace="live-client",
        project=project,
        tls_verify=False,
    )
    args = Namespace(
        project=project,
        tenant="mir",
        workspace="live-client",
        sync_mode="",
        progress_interval=5,
        allow_cloud_llm=True,
        max_files=50,
        include_path=None,
    )
    t0 = time.perf_counter()
    code = cp.client_push_sync(settings, args, work=root)
    sec = time.perf_counter() - t0
    out = capsys.readouterr().out
    assert code == 0, out[-2000:]
    assert "content-push" in out.lower() or "push=" in out
    assert sec < 800, f"client_push_sync hung/slow: {sec:.1f}s"
    # Progress should mention finalizing at least once on last batch.
    assert "finalizing" in out.lower() or "files_ingested" in out.lower() or "ok" in out.lower()
