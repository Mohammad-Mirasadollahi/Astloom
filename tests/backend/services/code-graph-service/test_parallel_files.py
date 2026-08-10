"""Tests for cancel-aware parallel file jobs (Ctrl+C / disconnect)."""

from __future__ import annotations

import threading

import pytest

import code_graph_service.application.ingest.parallel_files as mod
from code_graph_service.application.ingest.parallel_files import run_parallel_file_jobs
from code_graph_service.domain.errors import ClientDisconnected


def test_run_parallel_file_jobs_runs_all():
    seen: list[int] = []
    lock = threading.Lock()

    def fn(index: int, item: int) -> None:
        with lock:
            seen.append(item)

    run_parallel_file_jobs(workers=3, items=[1, 2, 3, 4], fn=fn)
    assert sorted(seen) == [1, 2, 3, 4]


def test_run_parallel_file_jobs_keyboard_interrupt_cancels_pending(monkeypatch, capsys):
    started = threading.Event()
    release = threading.Event()
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

    original_wait = mod.wait
    interrupt_once = {"done": False}

    def wait_then_interrupt(fs, timeout=None, return_when=None):
        if not interrupt_once["done"] and started.wait(timeout=5):
            interrupt_once["done"] = True
            release.set()
            raise KeyboardInterrupt
        kwargs: dict = {}
        if return_when is not None:
            kwargs["return_when"] = return_when
        return original_wait(fs, timeout=timeout, **kwargs)

    monkeypatch.setattr(mod, "wait", wait_then_interrupt)
    with pytest.raises(KeyboardInterrupt):
        run_parallel_file_jobs(workers=2, items=[0, 1, 2, 3], fn=fn)

    started_items = {entry[1] for entry in ran if entry[0] == "start"}
    done_items = {entry[1] for entry in ran if entry[0] == "done"}
    assert started_items <= {0, 1}
    assert done_items <= started_items
    assert 2 not in started_items
    assert 3 not in started_items
    out = capsys.readouterr().out
    assert "Stopping sync" in out
    assert "cancelling" in out


def test_run_parallel_file_jobs_abandon_stuck_workers(monkeypatch, capsys):
    started = threading.Event()
    block = threading.Event()
    exited: list[int] = []

    def fn(index: int, item: int) -> None:
        if item == 0:
            started.set()
            block.wait(timeout=30)

    original_wait = mod.wait
    interrupt_once = {"done": False}

    def wait_then_interrupt(fs, timeout=None, return_when=None):
        if not interrupt_once["done"] and started.wait(timeout=5):
            interrupt_once["done"] = True
            raise KeyboardInterrupt
        kwargs: dict = {}
        if return_when is not None:
            kwargs["return_when"] = return_when
        return original_wait(fs, timeout=timeout, **kwargs)

    def fake_exit(code: int) -> None:
        exited.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(mod, "wait", wait_then_interrupt)
    monkeypatch.setattr(mod.os, "_exit", fake_exit)
    try:
        with pytest.raises(SystemExit) as excinfo:
            run_parallel_file_jobs(
                workers=2,
                items=[0, 1, 2],
                fn=fn,
                shutdown_grace_sec=0.05,
            )
        assert excinfo.value.code == 130
    finally:
        block.set()

    assert exited == [130]
    out = capsys.readouterr().out
    assert "abandoning" in out


def test_run_parallel_file_jobs_should_cancel_does_not_os_exit(monkeypatch, capsys):
    started = threading.Event()
    block = threading.Event()
    cancel = threading.Event()
    exited: list[int] = []

    def fn(index: int, item: int) -> None:
        if item == 0:
            started.set()
            block.wait(timeout=30)

    def fake_exit(code: int) -> None:
        exited.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(mod.os, "_exit", fake_exit)

    def worker() -> None:
        with pytest.raises(ClientDisconnected):
            run_parallel_file_jobs(
                workers=2,
                items=[0, 1, 2],
                fn=fn,
                should_cancel=cancel.is_set,
                shutdown_grace_sec=0.05,
            )

    thread = threading.Thread(target=worker)
    thread.start()
    assert started.wait(timeout=5)
    cancel.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    block.set()
    assert exited == []
    out = capsys.readouterr().out
    assert "client disconnect" in out
