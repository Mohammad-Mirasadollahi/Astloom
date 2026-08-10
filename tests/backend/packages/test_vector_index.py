"""Unit tests for vector_index port, fake, config, id map, and turbovec contract."""

from __future__ import annotations

import numpy as np
import pytest

from vector_index import (
    ENTITY_ID_MAP_TABLE_SQL,
    AnnAcceleratorConfig,
    InMemoryEntityIdMap,
    InMemoryVectorIndex,
    TurboVecIndexAdapter,
    ann_accelerator_enabled,
    entity_ref_to_uint64,
    load_accelerator_config,
    stable_hash_uint64,
    try_build_accelerator,
    turbovec_available,
    turbovec_importable,
)


def test_config_defaults_off():
    cfg = AnnAcceleratorConfig.from_environment({})
    assert cfg.enabled is False
    assert cfg.bit_width == 4
    assert cfg.sync_mode == "sync_on_write"
    assert ann_accelerator_enabled({}) is False


def test_config_turbovec_and_bit_width():
    cfg = AnnAcceleratorConfig.from_environment(
        {
            "ASTLOOM_RAG_ANN_ACCELERATOR": "turbovec",
            "ASTLOOM_TURBOVEC_BIT_WIDTH": "2",
            "ASTLOOM_TURBOVEC_SNAPSHOT_URI": "file:///tmp/x.tvim",
            "ASTLOOM_TURBOVEC_SYNC_MODE": "async_job",
        }
    )
    assert cfg.enabled is True
    assert cfg.bit_width == 2
    assert cfg.snapshot_uri == "file:///tmp/x.tvim"
    assert cfg.sync_mode == "async_job"


def test_config_rejects_bad_accelerator():
    with pytest.raises(ValueError, match="ASTLOOM_RAG_ANN_ACCELERATOR"):
        AnnAcceleratorConfig.from_environment({"ASTLOOM_RAG_ANN_ACCELERATOR": "faiss"})


def test_entity_id_map_stable_and_reversible():
    mid = InMemoryEntityIdMap()
    a = mid.get_or_assign("sym:proj:foo")
    b = mid.get_or_assign("sym:proj:foo")
    assert a == b
    assert mid.to_entity_ref(a) == "sym:proj:foo"
    assert stable_hash_uint64("sym:proj:foo") == a
    assert entity_ref_to_uint64("x", namespace="ns") == stable_hash_uint64("ns:x")
    assert load_accelerator_config({}).accelerator == "off"
    assert turbovec_available() is turbovec_importable()
    assert "embedding_id_map" in ENTITY_ID_MAP_TABLE_SQL
    assert "uint64_id" in ENTITY_ID_MAP_TABLE_SQL


def test_inmemory_upsert_search_allowlist_and_remove(tmp_path):
    idx = InMemoryVectorIndex(dim=8)
    ids = [101, 102, 103]
    vectors = np.asarray(
        [
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    idx.upsert(ids, vectors)
    query = np.asarray([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    scores, hit_ids = idx.search(query, k=2, allowlist=[101, 103])
    assert list(hit_ids) == [101, 103]
    assert float(scores[0]) >= float(scores[1])
    assert idx.remove([102]) == 1
    assert idx.remove([102]) == 0

    snap = tmp_path / "fake.npz"
    idx.write_snapshot(str(snap))
    loaded = InMemoryVectorIndex()
    loaded.load_snapshot(str(snap))
    _, again = loaded.search(query, k=1, allowlist=[101, 103])
    assert int(again[0]) == 101


def test_inmemory_rejects_empty_allowlist():
    idx = InMemoryVectorIndex(dim=8)
    idx.upsert([1], np.ones((1, 8), dtype=np.float32))
    with pytest.raises(ValueError, match="allowlist"):
        idx.search(np.ones(8, dtype=np.float32), k=1, allowlist=[])


@pytest.mark.turbovec
@pytest.mark.skipif(not turbovec_importable(), reason="turbovec not installed")
def test_turbovec_adapter_contract_allowlist(tmp_path):
    adapter = TurboVecIndexAdapter.try_create(dim=8, bit_width=4)
    assert adapter is not None
    vectors = np.asarray(
        [
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.8, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    adapter.upsert([11, 22, 33], vectors)
    query = np.asarray([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    scores, hit_ids = adapter.search(query, k=2, allowlist=[11, 33])
    assert set(int(x) for x in hit_ids) <= {11, 33}
    assert len(hit_ids) == 2
    assert float(scores[0]) >= float(scores[1])
    assert adapter.remove([22]) == 1

    snap = tmp_path / "idx.tvim"
    adapter.write_snapshot(str(snap))
    reloaded = TurboVecIndexAdapter(dim=8, bit_width=4)
    reloaded.load_snapshot(str(snap))
    _, again = reloaded.search(query, k=1, allowlist=[11, 33])
    assert int(again[0]) in {11, 33}


def test_try_create_returns_none_when_dim_invalid():
    assert TurboVecIndexAdapter.try_create(dim=7, bit_width=4) is None


def test_try_build_accelerator_off_by_default():
    adapter, id_map = try_build_accelerator(dim=8, environ={})
    assert adapter is None and id_map is None
    adapter, id_map = try_build_accelerator(
        dim=8,
        environ={"ASTLOOM_RAG_ANN_ACCELERATOR": "turbovec"},
    )
    # Wheel optional: None when missing; both set when installed.
    if turbovec_importable():
        assert adapter is not None and id_map is not None
    else:
        assert adapter is None and id_map is None


def test_safe_table_name_and_entity_id_map_sql():
    assert "embedding_id_map" in ENTITY_ID_MAP_TABLE_SQL
    from vector_index.id_map import _safe_table_name

    assert _safe_table_name("memory.embedding_id_map")
    assert _safe_table_name("embedding_id_map")
    assert not _safe_table_name("memory;drop")


def test_promotion_gate_passes_on_synthetic_corpus():
    from vector_index import run_promotion_gate

    result = run_promotion_gate(
        n=64,
        dim=32,
        k=5,
        bit_width=4,
        prefer_turbovec=False,
        recall_delta_max=0.05,
    )
    assert result.passed
    assert result.accelerator == "in_memory"
    assert result.recall_at_k >= 0.95
    assert "corpus_size" in result.public()


@pytest.mark.turbovec
@pytest.mark.skipif(not turbovec_importable(), reason="turbovec not installed")
def test_promotion_gate_with_turbovec():
    from vector_index import run_promotion_gate

    result = run_promotion_gate(
        n=128,
        dim=64,
        k=10,
        bit_width=4,
        prefer_turbovec=True,
        recall_delta_max=0.15,
    )
    assert result.accelerator == "turbovec"
    assert result.passed, result.reason


def test_rebuild_from_rows_and_instrumented_metrics(tmp_path):
    from vector_index import (
        InstrumentedVectorIndex,
        get_accelerator_metrics,
        reset_accelerator_metrics,
    )

    reset_accelerator_metrics()
    snap = tmp_path / "replica.npz"
    idx = InstrumentedVectorIndex(
        InMemoryVectorIndex(dim=8),
        metrics=get_accelerator_metrics(),
        snapshot_uri=str(snap),
    )
    ids = [1, 2]
    vectors = np.eye(8, dtype=np.float32)[:2]
    idx.rebuild_from_rows(ids, vectors)
    query = np.asarray([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    _, hits = idx.search(query, k=1, allowlist=[1, 2])
    assert int(hits[0]) == 1
    assert snap.is_file()
    public = get_accelerator_metrics().public()
    assert public["rag.accelerator.sync_total"] >= 1
    assert public["rag.accelerator.search_count"] >= 1
    assert public["rag.accelerator.snapshot_write_total"] >= 1


def test_allowlist_isolation_rejects_foreign_ids():
    """Stage-2 allowlist must not return ids outside the authorized candidate set."""
    idx = InMemoryVectorIndex(dim=8)
    vectors = np.asarray(
        [
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.99, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    # 101/102 = project A candidates; 999 = foreign project vector also in replica.
    idx.upsert([101, 102, 999], vectors)
    query = np.asarray([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    _, hit_ids = idx.search(query, k=5, allowlist=[101, 102])
    assert set(int(x) for x in hit_ids) <= {101, 102}
    assert 999 not in {int(x) for x in hit_ids}


def test_try_build_accelerator_loads_snapshot(tmp_path, monkeypatch):
    if not turbovec_importable():
        pytest.skip("turbovec not installed")
    from vector_index import reset_accelerator_metrics

    reset_accelerator_metrics()
    snap = tmp_path / "boot.tvim"
    seed = TurboVecIndexAdapter.try_create(dim=8, bit_width=4)
    assert seed is not None
    seed.upsert(
        [7],
        np.asarray([[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]], dtype=np.float32),
    )
    seed.write_snapshot(str(snap))
    adapter, id_map = try_build_accelerator(
        dim=8,
        environ={
            "ASTLOOM_RAG_ANN_ACCELERATOR": "turbovec",
            "ASTLOOM_TURBOVEC_SNAPSHOT_URI": str(snap),
        },
    )
    assert adapter is not None and id_map is not None
    query = np.asarray([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    _, hits = adapter.search(query, k=1, allowlist=[7])
    assert int(hits[0]) == 7
