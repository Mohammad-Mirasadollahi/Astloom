"""Embedding call timeout defaults and one automatic retry."""

from __future__ import annotations

import concurrent.futures as cf

import code_graph_service.llm_wiring as wiring


def test_embed_timeout_default_is_cloud_friendly(monkeypatch):
    monkeypatch.delenv("ASTLOOM_EMBED_TIMEOUT_SECONDS", raising=False)
    assert wiring._embed_timeout_seconds() == 60.0


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
