"""GAP-T02 labeled call-graph accuracy corpus gate (precision / recall)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ckg_eval.cochange import precision_recall_f1
from code_graph_service.core import CodeGraphService
from code_graph_service.domain.enums import RelType
from code_graph_service.domain.models import Scope
from code_graph_service.testing import InMemoryStore

CORPUS_DIR = Path(__file__).resolve().parent / "call_graph_corpus"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"
SOURCES_DIR = CORPUS_DIR / "sources"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _predicted_calls(service: CodeGraphService, scope: Scope) -> set[tuple[str, str]]:
    symbols = {s.id: s for s in service.store.list_symbols(scope)}
    out: set[tuple[str, str]] = set()
    for edge in service.store.list_edges(scope):
        if edge.rel_type != RelType.CALLS.value:
            continue
        src = symbols.get(edge.source_id)
        tgt = symbols.get(edge.target_id)
        if src is None or tgt is None:
            continue
        # Skip unresolved placeholders from precision gold comparison unless named.
        if str(tgt.id).startswith("unresolved:"):
            continue
        out.add((src.name, tgt.name))
    return out


def _gold_calls(case: dict) -> set[tuple[str, str]]:
    return {
        (str(item["caller"]), str(item["callee"]))
        for item in case.get("gold_calls") or []
    }


def test_call_graph_corpus_precision_recall_gate():
    manifest = _load_manifest()
    thresholds = manifest["thresholds"]
    min_p = float(thresholds["precision"])
    min_r = float(thresholds["recall"])

    predicted: set[tuple[str, str]] = set()
    gold: set[tuple[str, str]] = set()

    for case in manifest["cases"]:
        source_path = SOURCES_DIR / case["source_file"]
        assert source_path.is_file(), f"missing corpus source {source_path}"
        source = source_path.read_text(encoding="utf-8")
        store = InMemoryStore()
        service = CodeGraphService(store)
        scope = Scope(
            tenant_id="corpus",
            workspace_id="call-graph",
            project_id=f"case-{case['id']}",
        )
        service.ingest_file(
            scope,
            "corpus",
            f"corr-{case['id']}",
            f"idem-{case['id']}",
            {
                "file_path": case["source_file"],
                "source": source,
                "language": case.get("language") or "python",
            },
        )
        case_pred = _predicted_calls(service, scope)
        case_gold = _gold_calls(case)
        # Namespace pairs by case id so identical names across cases do not collide.
        predicted |= {(case["id"], a, b) for a, b in case_pred}
        gold |= {(case["id"], a, b) for a, b in case_gold}

    # Compare on (case, caller, callee) triples.
    pred_keys = {(c, a, b) for c, a, b in predicted}
    gold_keys = {(c, a, b) for c, a, b in gold}
    metrics = precision_recall_f1(pred_keys, gold_keys)
    assert metrics["precision"] >= min_p, metrics
    assert metrics["recall"] >= min_r, metrics


def test_call_graph_corpus_manifest_sources_exist():
    manifest = _load_manifest()
    for case in manifest["cases"]:
        path = SOURCES_DIR / case["source_file"]
        assert path.is_file()
        assert path.stat().st_size > 0


@pytest.mark.parametrize(
    "case_id",
    ["exact_direct", "exact_chain"],
)
def test_exact_cases_resolve_gold_edges(case_id: str):
    manifest = _load_manifest()
    case = next(c for c in manifest["cases"] if c["id"] == case_id)
    store = InMemoryStore()
    service = CodeGraphService(store)
    scope = Scope(tenant_id="t", workspace_id="w", project_id=case_id)
    source = (SOURCES_DIR / case["source_file"]).read_text(encoding="utf-8")
    service.ingest_file(
        scope,
        "actor",
        "corr",
        f"idem-{case_id}",
        {
            "file_path": case["source_file"],
            "source": source,
            "language": "python",
        },
    )
    pred = _predicted_calls(service, scope)
    gold = _gold_calls(case)
    assert gold <= pred, {"predicted": pred, "gold": gold}
