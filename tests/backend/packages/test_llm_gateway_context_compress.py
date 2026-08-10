"""Unit tests for LiteLLM ingress compression hook."""

from __future__ import annotations

import json

import pytest

from llm_gateway.gateway import _maybe_compress_message_content


def test_litellm_hook_skips_short_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASTLOOM_CONTEXT_COMPRESS", raising=False)
    assert _maybe_compress_message_content("short") == "short"


def test_litellm_hook_compresses_large_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTLOOM_CONTEXT_COMPRESS", "1")
    monkeypatch.setenv("ASTLOOM_CONTEXT_COMPRESS_MIN_CHARS", "100")
    payload = json.dumps({"rows": [{"n": i, "s": "z" * 200} for i in range(40)]})
    out = _maybe_compress_message_content(payload)
    assert out != payload
    assert "astloom_context: handle=" in out
    assert len(out) < len(payload)


def test_litellm_hook_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTLOOM_CONTEXT_COMPRESS", "0")
    payload = "x" * 5000
    assert _maybe_compress_message_content(payload) == payload
