"""Tests for LockedStore / sync worker helper."""

from __future__ import annotations

import os
import threading
import time
from types import SimpleNamespace

from code_graph_service.locked_store import (
    LockedStore,
    apply_sync_compute_limits,
    resolve_sync_cpu_plan,
    sync_max_file_workers,
)


def test_sync_max_file_workers_auto_from_cpu_and_rpm(monkeypatch):
    monkeypatch.delenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", raising=False)
    monkeypatch.delenv("ASTLOOM_SYNC_CPU_PERCENT", raising=False)
    monkeypatch.setenv("ASTLOOM_LITELLM_RPM", "30")
    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 8)
    assert sync_max_file_workers() == 8

    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 64)
    assert sync_max_file_workers({"ASTLOOM_LITELLM_RPM": "10"}) == 10

    # High RPM: limited by CPU only (no fixed 32 ceiling)
    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 64)
    assert sync_max_file_workers({"ASTLOOM_LITELLM_RPM": "100"}) == 64


def test_sync_max_file_workers_explicit_override(monkeypatch):
    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 8)
    assert sync_max_file_workers({"ASTLOOM_SYNC_MAX_FILE_WORKERS": "3", "ASTLOOM_LITELLM_RPM": "30"}) == 3
    assert sync_max_file_workers({"ASTLOOM_SYNC_MAX_FILE_WORKERS": "auto", "ASTLOOM_LITELLM_RPM": "5"}) == 5
    assert sync_max_file_workers({"ASTLOOM_SYNC_MAX_FILE_WORKERS": "nope", "ASTLOOM_LITELLM_RPM": "2"}) == 2
    assert sync_max_file_workers({"ASTLOOM_SYNC_MAX_FILE_WORKERS": "0", "ASTLOOM_LITELLM_RPM": "7"}) == 7


def test_sync_cpu_percent_derives_workers_and_embed_slots(monkeypatch):
    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 40)
    plan = resolve_sync_cpu_plan(
        {
            "ASTLOOM_SYNC_CPU_PERCENT": "25",
            "ASTLOOM_LITELLM_RPM": "30",
        }
    )
    assert plan.mode == "percent"
    assert plan.cpu_percent == 25
    assert plan.workers == 10
    assert plan.embed_concurrency == 4
    assert plan.torch_threads == 1
    assert plan.store_concurrency == 8
    assert sync_max_file_workers({"ASTLOOM_SYNC_CPU_PERCENT": "25", "ASTLOOM_LITELLM_RPM": "30"}) == 10


def test_store_concurrency_caps_at_eight_and_floors_at_two(monkeypatch):
    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 48)
    plan = resolve_sync_cpu_plan({"ASTLOOM_SYNC_CPU_PERCENT": "60"})
    assert plan.workers == 29
    assert plan.store_concurrency == 8
    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 2)
    plan_small = resolve_sync_cpu_plan({"ASTLOOM_SYNC_CPU_PERCENT": "50"})
    assert plan_small.workers == 1
    assert plan_small.store_concurrency == 2


def test_sync_cpu_percent_rounds_and_floors_at_one(monkeypatch):
    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 8)
    plan = resolve_sync_cpu_plan({"ASTLOOM_SYNC_CPU_PERCENT": "1"})
    assert plan.workers == 1
    assert plan.embed_concurrency == 1
    plan50 = resolve_sync_cpu_plan({"ASTLOOM_SYNC_CPU_PERCENT": "50"})
    assert plan50.workers == 4


def test_explicit_workers_override_cpu_percent(monkeypatch):
    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 40)
    plan = resolve_sync_cpu_plan(
        {
            "ASTLOOM_SYNC_CPU_PERCENT": "50",
            "ASTLOOM_SYNC_MAX_FILE_WORKERS": "3",
        }
    )
    assert plan.mode == "workers"
    assert plan.workers == 3
    assert plan.embed_concurrency == 3
    assert plan.torch_threads == 1


def test_auto_plan_caps_embed_and_pins_torch(monkeypatch):
    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 16)
    plan = resolve_sync_cpu_plan({"ASTLOOM_LITELLM_RPM": "30"})
    assert plan.mode == "auto"
    assert plan.workers == 16
    assert plan.embed_concurrency == 4
    assert plan.torch_threads == 1


def test_apply_sync_compute_limits_sets_thread_env(monkeypatch):
    monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    monkeypatch.delenv("MKL_NUM_THREADS", raising=False)
    monkeypatch.delenv("OPENBLAS_NUM_THREADS", raising=False)
    monkeypatch.delenv("TOKENIZERS_PARALLELISM", raising=False)
    plan = resolve_sync_cpu_plan(
        {"ASTLOOM_SYNC_CPU_PERCENT": "25"},
        cpu_count=40,
    )
    apply_sync_compute_limits(plan)
    assert os.environ["OMP_NUM_THREADS"] == "1"
    assert os.environ["MKL_NUM_THREADS"] == "1"
    assert os.environ["OPENBLAS_NUM_THREADS"] == "1"
    assert os.environ["TOKENIZERS_PARALLELISM"] == "false"


def test_locked_store_allows_concurrent_reads(monkeypatch):
    """Write lock must not serialize list_symbols (Neo4j-style lock_reads=False)."""

    class SlowReadStore:
        def __init__(self) -> None:
            self.read_peak = 0
            self._active = 0
            self._lock = threading.Lock()

        def list_symbols(self, _scope=None):
            with self._lock:
                self._active += 1
                self.read_peak = max(self.read_peak, self._active)
            time.sleep(0.05)
            with self._lock:
                self._active -= 1
            return []

        def put_symbol(self, _symbol=None):
            return None

    store = LockedStore(SlowReadStore(), lock_reads=False)
    barrier = threading.Barrier(4)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait(timeout=1.0)
            store.list_symbols()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)
    assert errors == []
    assert store._store.read_peak >= 2


def test_locked_store_caps_concurrent_ops():
    class SlowReadStore:
        def __init__(self) -> None:
            self.read_peak = 0
            self._active = 0
            self._lock = threading.Lock()

        def list_symbols(self, _scope=None):
            with self._lock:
                self._active += 1
                self.read_peak = max(self.read_peak, self._active)
            time.sleep(0.08)
            with self._lock:
                self._active -= 1
            return []

    store = LockedStore(SlowReadStore(), lock_reads=False, max_concurrent=2)
    barrier = threading.Barrier(6)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait(timeout=1.0)
            store.list_symbols()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=3.0)
    assert errors == []
    assert store._store.read_peak <= 2


def test_locked_store_nested_reads_are_reentrant():
    class NestingStore:
        def __init__(self) -> None:
            self.outer = None

        def list_symbols(self, _scope=None):
            # Nested call through the same LockedStore wrapper.
            return self.outer.get_symbol("x")

        def get_symbol(self, _id):
            return "ok"

    inner = NestingStore()
    locked = LockedStore(inner, lock_reads=False, max_concurrent=1)
    inner.outer = locked
    assert locked.list_symbols() == "ok"


def test_write_waiters_do_not_starve_all_read_slots():
    """With bounded slots, one long write must leave room for a concurrent read."""

    class Store:
        def __init__(self) -> None:
            self.write_entered = threading.Event()
            self.release_write = threading.Event()
            self.read_done = threading.Event()

        def put_symbol(self, _symbol=None):
            self.write_entered.set()
            self.release_write.wait(timeout=2.0)

        def list_symbols(self, _scope=None):
            self.read_done.set()
            return []

    raw = Store()
    store = LockedStore(raw, lock_reads=False, max_concurrent=2)
    errors: list[BaseException] = []

    def writer() -> None:
        try:
            store.put_symbol()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    w1 = threading.Thread(target=writer)
    w1.start()
    assert raw.write_entered.wait(timeout=1.0)
    threading.Thread(target=lambda: store.list_symbols()).start()
    assert raw.read_done.wait(timeout=1.0)
    raw.release_write.set()
    w1.join(timeout=2.0)
    assert errors == []


def test_locked_store_serializes_mutations():
    class Counter:
        def __init__(self) -> None:
            self.value = 0

        def put_symbol(self, _symbol=None) -> int:
            current = self.value
            self.value = current + 1
            return self.value

    locked = LockedStore(Counter())
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for _ in range(200):
                locked.put_symbol()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert locked.value == 1600


def test_build_service_does_not_serialize_remote_embeddings(monkeypatch):
    import code_graph_service.bootstrap as bootstrap
    import code_graph_service.llm_wiring as llm_wiring
    from code_graph_service.testing import InMemoryStore
    from llm_gateway import FakeLlmGateway

    class RemoteEmbeddings:
        local = None
        model = "remote/model"

        def __init__(self) -> None:
            self.barrier = threading.Barrier(2)

        def embed(self, text: str):
            self.barrier.wait(timeout=1.0)
            return text

    remote = RemoteEmbeddings()
    gateway = FakeLlmGateway()
    monkeypatch.setattr(bootstrap, "build_store", lambda _settings, **_kw: InMemoryStore())
    monkeypatch.setattr(bootstrap, "build_llm_gateway", lambda: gateway)
    monkeypatch.setattr(
        bootstrap,
        "build_embeddings",
        lambda _gateway, settings=None: remote,
    )
    monkeypatch.setattr(bootstrap, "build_embedding_index", lambda _settings, **_kw: None)
    monkeypatch.setattr(llm_wiring, "maybe_preload_embeddings", lambda _embeddings: False)
    service = bootstrap.build_service(SimpleNamespace(database_url=""))

    errors: list[BaseException] = []

    def worker(value: str) -> None:
        try:
            service.embeddings.embed(value)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(value,)) for value in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)

    assert errors == []
    assert all(not thread.is_alive() for thread in threads)


def test_build_service_does_not_serialize_loaded_local_embeddings(monkeypatch):
    import code_graph_service.bootstrap as bootstrap
    import code_graph_service.llm_wiring as llm_wiring
    from code_graph_service.testing import InMemoryStore
    from llm_gateway import FakeLlmGateway

    class LocalEmbeddings:
        model = "local/model"

        def __init__(self) -> None:
            self.barrier = threading.Barrier(2)

        def embed(self, text: str, *, is_query: bool = False):
            self.barrier.wait(timeout=1.0)
            return text

    class HybridEmbeddings:
        def __init__(self) -> None:
            self.local = LocalEmbeddings()

        def embed(self, text: str):
            return self.local.embed(text)

    embeddings = HybridEmbeddings()
    gateway = FakeLlmGateway()
    monkeypatch.setattr(bootstrap, "build_store", lambda _settings, **_kw: InMemoryStore())
    monkeypatch.setattr(bootstrap, "build_llm_gateway", lambda: gateway)
    monkeypatch.setattr(bootstrap, "build_embeddings", lambda _gateway, settings=None: embeddings)
    monkeypatch.setattr(bootstrap, "build_embedding_index", lambda _settings, **_kw: None)
    monkeypatch.setattr(llm_wiring, "maybe_preload_embeddings", lambda _embeddings: False)
    service = bootstrap.build_service(SimpleNamespace(database_url=""))
    errors: list[BaseException] = []

    def worker(value: str) -> None:
        try:
            service.embeddings.embed(value)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(value,)) for value in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)

    assert errors == []
    assert all(not thread.is_alive() for thread in threads)


def test_local_embedding_limit_is_shared_across_service_instances(monkeypatch):
    import code_graph_service.local_embeddings as local_embeddings

    # Prior tests may raise process-wide slots via apply_sync_compute_limits.
    local_embeddings.configure_local_embed_slots(4)

    class Encoder:
        def __init__(self) -> None:
            self.active = 0
            self.peak = 0
            self.lock = threading.Lock()

        def encode(self, _payload, **_kwargs):
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            time.sleep(0.1)
            with self.lock:
                self.active -= 1
            return [0.0, 0.0]

    encoder = Encoder()
    monkeypatch.setattr(local_embeddings, "_load_sentence_transformer", lambda *_args: encoder)
    left = local_embeddings.LocalBgeEmbeddings(model_name="same", cache_dir="same", dims=2)
    right = local_embeddings.LocalBgeEmbeddings(model_name="same", cache_dir="same", dims=2)
    start = threading.Barrier(8)
    errors: list[BaseException] = []

    def worker(instance) -> None:
        try:
            start.wait(timeout=1.0)
            instance.embed("value")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(left if index < 4 else right,))
        for index in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)

    assert errors == []
    assert encoder.peak <= 4


def test_local_model_loads_are_process_serialized(monkeypatch):
    import code_graph_service.local_embeddings as local_embeddings

    active = 0
    peak = 0
    lock = threading.Lock()

    class Encoder:
        def encode(self, _payload, **_kwargs):
            return [0.0, 0.0]

    def load_model(*_args):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.1)
        with lock:
            active -= 1
        return Encoder()

    monkeypatch.setattr(local_embeddings, "_load_sentence_transformer", load_model)
    left = local_embeddings.LocalBgeEmbeddings(model_name="left", cache_dir="same", dims=2)
    right = local_embeddings.LocalBgeEmbeddings(model_name="right", cache_dir="same", dims=2)
    start = threading.Barrier(2)

    def worker(instance) -> None:
        start.wait(timeout=1.0)
        instance.embed("value")

    threads = [threading.Thread(target=worker, args=(instance,)) for instance in (left, right)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)

    assert all(not thread.is_alive() for thread in threads)
    assert peak == 1
