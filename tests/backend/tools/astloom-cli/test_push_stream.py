"""Tests for client NDJSON ingest-push stream consumer."""

from __future__ import annotations

import pytest

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
    assert "begin" in phases


def test_consume_ndjson_malformed_line_exits_with_actionable_message():
    """A proxy injecting HTML mid-body must not surface as a raw JSONDecodeError."""
    with pytest.raises(SystemExit, match="malformed line"):
        consume_ndjson_ingest_push(
            lines=["<html>502 Bad Gateway</html>"],
            on_progress=lambda e: None,
        )


def test_consume_ndjson_non_object_line_exits():
    with pytest.raises(SystemExit, match="malformed line"):
        consume_ndjson_ingest_push(lines=["null"], on_progress=lambda e: None)


def test_consume_ndjson_error_exits():
    with pytest.raises(SystemExit, match="ingest-push stream"):
        consume_ndjson_ingest_push(
            lines=['{"type":"error","message":"boom"}\n'],
            on_progress=lambda e: None,
        )
