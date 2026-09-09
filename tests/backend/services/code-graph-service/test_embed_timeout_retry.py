"""Embedding call timeout defaults, DNS retry, and one automatic timeout retry."""

from __future__ import annotations

import concurrent.futures as cf

import pytest

import code_graph_service.llm_wiring as wiring


def test_embed_timeout_default_is_cloud_friendly(monkeypatch):
    monkeypatch.delenv("ASTLOOM_EMBED_TIMEOUT_SECONDS", raising=False)
    assert wiring._embed_timeout_seconds() == 180.0


def test_run_with_timeout_retries_once(monkeypatch):
    monkeypatch.setenv("ASTLOOM_EMBED_TIMEOUT_SECONDS", "1")
    calls = {"n": 0}

    class _Fut:
        def result(self, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise cf.TimeoutError()
            return "ok"

    class _Pool:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def submit(self, fn, *a, **k):
            return _Fut()

    monkeypatch.setattr(cf, "ThreadPoolExecutor", _Pool)
    assert wiring._run_with_timeout(lambda: None) == "ok"
    assert calls["n"] == 2


def test_run_with_timeout_retries_dns_then_succeeds(monkeypatch):
    monkeypatch.setenv("ASTLOOM_EMBED_TIMEOUT_SECONDS", "1")
    monkeypatch.setattr(wiring, "_embed_retry_sleep_seconds", lambda _attempt: 0)
    calls = {"n": 0}

    def _flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError(
                "litellm.APIError: OpenrouterException - "
                "[Errno -3] Temporary failure in name resolution"
            )
        return "ok"

    assert wiring._run_with_timeout(_flaky) == "ok"
    assert calls["n"] == 3


def test_run_with_timeout_does_not_retry_permanent_errors(monkeypatch):
    monkeypatch.setenv("ASTLOOM_EMBED_TIMEOUT_SECONDS", "1")
    calls = {"n": 0}

    def _auth():
        calls["n"] += 1
        raise RuntimeError("Unauthorized: invalid api key")

    with pytest.raises(RuntimeError, match="invalid api key"):
        wiring._run_with_timeout(_auth)
    assert calls["n"] == 1


def test_is_transient_embed_error_matches_operator_failures():
    assert wiring._is_transient_embed_error(
        RuntimeError("OpenrouterException - [Errno -3] Temporary failure in name resolution")
    )
    assert wiring._is_transient_embed_error(
        RuntimeError("embedding call timed out after 60.0s")
    )
    assert not wiring._is_transient_embed_error(RuntimeError("openrouter down"))
    assert not wiring._is_transient_embed_error(RuntimeError("context length exceeded"))
