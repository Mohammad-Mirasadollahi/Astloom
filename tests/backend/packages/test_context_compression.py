"""Unit tests for native context compression (doc 54)."""

from __future__ import annotations

import json

from context_compression import WATERMARK, ContextCompressionStore, compress_payload, metrics_snapshot, reset_metrics


def test_json_minify_and_truncate_saves_chars():
    big = {"items": [{"id": i, "blob": "x" * 500} for i in range(40)]}
    raw = json.dumps(big)
    result = compress_payload(raw, content_type="json", min_chars=100)
    assert not result.skipped
    assert result.content_type == "json"
    assert result.compressed_chars < result.original_chars
    assert result.lossy
    parsed = json.loads(result.compressed)
    assert isinstance(parsed["items"], list)
    assert len(parsed["items"]) <= 25


def test_below_threshold_skipped():
    result = compress_payload("tiny", min_chars=1000)
    assert result.skipped
    assert result.compressed == "tiny"


def test_store_round_trip_and_scope_isolation():
    store = ContextCompressionStore()
    scope = {"tenant_id": "t1", "workspace_id": "w", "project_id": "p"}
    other = {"tenant_id": "t2", "workspace_id": "w", "project_id": "p"}
    handle = store.put("SECRET", scope=scope, content_type="text", lossy=False, ttl_seconds=120)
    assert store.get(handle, scope=scope)["payload"] == "SECRET"
    assert store.get(handle, scope=other) is None


def test_watermark_skips_double_compress():
    reset_metrics()
    raw = ("y" * 3000) + f"\n{WATERMARK} handle=x\n"
    result = compress_payload(raw, min_chars=100)
    assert result.skipped
    assert "already_compressed" in result.notes


def test_metrics_track_savings():
    reset_metrics()
    big = json.dumps({"items": [{"id": i, "blob": "x" * 400} for i in range(30)]})
    compress_payload(big, content_type="json", min_chars=100)
    snap = metrics_snapshot()
    assert snap["calls"] == 1
    assert snap["applied"] == 1
    assert snap["chars_saved"] > 0
    assert snap["pct_saved"] > 0
