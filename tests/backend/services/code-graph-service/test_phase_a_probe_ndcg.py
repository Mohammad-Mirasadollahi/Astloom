"""A2 offline nDCG on the real sample repo samples/e2e-graph-probe (backlog 34)."""

from __future__ import annotations

from pathlib import Path

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore

from ckg_eval.harness import score_retrieval_ndcg

SAMPLE = Path(__file__).resolve().parents[4] / "samples" / "e2e-graph-probe" / "src"

# Gold labels are human-chosen names for the sample probe — not graph self-walk.
GOLD = [
    {"query": "hash_password", "relevant_names": ["hash_password"]},
    {"query": "verify password", "relevant_names": ["verify_password", "hash_password"]},
    {"query": "login session", "relevant_names": ["login", "require_login"]},
]


def test_ndcg_on_e2e_graph_probe_sample_repo():
    assert SAMPLE.is_dir(), f"missing sample repo {SAMPLE}"
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("probe-t", "probe-w", "probe-p")
    result = svc.ingest_repo(
        scope,
        "eval",
        "eval-probe",
        "eval-probe-key",
        {
            "root_path": str(SAMPLE),
            "include_extensions": [".py"],
            "max_files": 20,
            "include_outcomes": True,
        },
    )
    assert result.files_ingested >= 2

    by_name: dict[str, str] = {}
    for s in store.list_symbols(scope):
        if s.kind.value in {"function", "method", "class"} and s.name not in by_name:
            by_name[s.name] = s.qualified_name

    resolved = []
    for item in GOLD:
        qns = [by_name[n] for n in item["relevant_names"] if n in by_name]
        assert qns, f"gold names missing after ingest: {item}"
        resolved.append({"query": item["query"], "relevant_qualified_names": qns})

    report = score_retrieval_ndcg(svc, scope, resolved, k=10, threshold=0.5)
    assert report["mean_ndcg"] >= 0.5
    assert report["passes_threshold"] is True
    assert report["label_source"] == "gold_queries"
