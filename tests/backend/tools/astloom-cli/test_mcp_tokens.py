"""Tests for MCP token estimate + usage log filtering."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astloom_cli.mcp_token_report import (
    aggregate_history,
    estimate_connect,
    format_text,
    parse_time_range,
    resolve_scope_ids,
)
from astloom_cli.mcp_usage_log import append_mcp_usage_event, load_mcp_usage_events


def test_parse_time_range_relative():
    tr = parse_time_range("24h", None)
    assert "24h" in tr.label
    assert tr.end - tr.start <= timedelta(hours=24, seconds=2)


def test_resolve_scope_ids():
    assert resolve_scope_ids("all") is None
    assert resolve_scope_ids("mir/dev/astloom,acme/eng/p") == [
        "mir/dev/astloom",
        "acme/eng/p",
    ]


def test_estimate_connect_lazy_cheaper_than_full():
    est = estimate_connect("programming-cursor-mcp")
    conn = est["connect"]
    assert conn["lazy_tools_list_tokens"] > 0
    assert conn["full_catalog_tools_list_tokens"] > conn["lazy_tools_list_tokens"]
    assert conn["saved_vs_full_catalog"] == (
        conn["full_catalog_tools_list_tokens"] - conn["lazy_tools_list_tokens"]
    )
    assert est["tool_count_catalog"] >= 2
    assert any(r["tool"] == "astloom_docs_authoring_standards" for r in est["heavy_tools"])


def test_append_and_aggregate_by_client_and_scope(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_MCP_USAGE_LOG_DIR", str(tmp_path / "mcp-usage"))
    now = datetime.now(timezone.utc)
    for i, (client, scope, tout) in enumerate(
        [
            ("cursor", "mir/dev/astloom", 100),
            ("cursor", "mir/dev/astloom", 50),
            ("vscode", "acme/eng/p", 200),
        ]
    ):
        append_mcp_usage_event(
            {
                "ts": (now - timedelta(minutes=i)).isoformat().replace("+00:00", "Z"),
                "event": "tools/call",
                "tool": "astloom_ping",
                "tokens_in": 10,
                "tokens_out": tout,
                "client_id": client,
                "scope": scope,
                "usage_profile": "programming-cursor-mcp",
            }
        )
    # Force ts from event body: append_mcp_usage_event overwrites ts — load all recent
    events = load_mcp_usage_events(
        start=now - timedelta(hours=1),
        end=now + timedelta(minutes=1),
    )
    assert len(events) == 3

    all_hist = aggregate_history(events, client_ids=None, scope_ids=None)
    assert all_hist["totals"]["calls"] == 3
    assert all_hist["by_client_id"]["cursor"]["calls"] == 2
    assert all_hist["by_scope_id"]["acme/eng/p"]["tokens_out"] == 200

    cursor_only = aggregate_history(events, client_ids=["cursor"], scope_ids=None)
    assert cursor_only["totals"]["calls"] == 2

    scope_only = aggregate_history(
        events, client_ids=None, scope_ids=["mir/dev/astloom"]
    )
    assert scope_only["totals"]["calls"] == 2


def test_format_text_includes_connect_section():
    est = estimate_connect("programming-cursor-mcp")
    report = {
        "range": "last 7d (default)",
        "estimate": est,
        "clients": {
            "selected": ["cursor"],
            "wiring": [
                {
                    "client_id": "cursor",
                    "title": "Cursor",
                    "config_path": "/tmp/x",
                    "wired": False,
                }
            ],
            "wired_count": 0,
            "if_each_wired_client_connects_tokens": 0,
        },
        "history": {
            "totals": {"calls": 0, "tokens_in": 0, "tokens_out": 0},
            "by_client_id": {},
            "by_scope_id": {},
            "by_tool": {},
            "event_count": 0,
        },
        "filters": {"clients": "cursor", "scope_ids": "all"},
    }
    text = format_text(report)
    assert "Lazy facade" in text
    assert "Clients (IDE ids)" in text
