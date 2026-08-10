"""GAP-T02 accuracy gate: corpus precision/recall + confidence_policy + runtime reconcile."""

from __future__ import annotations

import json
from pathlib import Path

from ckg_eval.cochange import precision_recall_f1
from code_graph_service.core import CodeGraphService
from code_graph_service.domain.confidence_policy import (
    clamp_confidence,
    confidence_for_evidence,
)
from code_graph_service.domain.enums import CallConfidence, RelType
from code_graph_service.domain.models import Scope
from code_graph_service.domain.runtime_traces import (
    ObservedCall,
    reconcile_runtime_traces,
)
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
        if str(tgt.id).startswith("unresolved:"):
            continue
        out.add((src.name, tgt.name))
    return out


def _gold_calls(case: dict) -> set[tuple[str, str]]:
    return {
        (str(item["caller"]), str(item["callee"]))
        for item in case.get("gold_calls") or []
    }


def _ingest_case(case: dict) -> tuple[CodeGraphService, Scope]:
    store = InMemoryStore()
    service = CodeGraphService(store)
    scope = Scope(
        tenant_id="corpus",
        workspace_id="call-graph",
        project_id=f"gate-{case['id']}",
    )
    source = (SOURCES_DIR / case["source_file"]).read_text(encoding="utf-8")
    service.ingest_file(
        scope,
        "corpus",
        f"corr-{case['id']}",
        f"idem-gate-{case['id']}",
        {
            "file_path": case["source_file"],
            "source": source,
            "language": case.get("language") or "python",
        },
    )
    return service, scope


def test_call_graph_accuracy_gate_precision_recall():
    """Corpus P/R must clear manifest thresholds (static extraction)."""
    manifest = _load_manifest()
    min_p = float(manifest["thresholds"]["precision"])
    min_r = float(manifest["thresholds"]["recall"])

    predicted: set[tuple[str, str, str]] = set()
    gold: set[tuple[str, str, str]] = set()
    for case in manifest["cases"]:
        service, scope = _ingest_case(case)
        pred = _predicted_calls(service, scope)
        case_gold = _gold_calls(case)
        predicted |= {(case["id"], a, b) for a, b in pred}
        gold |= {(case["id"], a, b) for a, b in case_gold}

    metrics = precision_recall_f1(predicted, gold)
    assert metrics["precision"] >= min_p, metrics
    assert metrics["recall"] >= min_r, metrics


def test_confidence_policy_reflection_and_monkeypatch_caps():
    """Reflection / monkeypatch must never claim EXACT (policy gate)."""
    assert confidence_for_evidence("reflection") == CallConfidence.AMBIGUOUS
    assert confidence_for_evidence("monkeypatch") == CallConfidence.AMBIGUOUS
    assert (
        clamp_confidence(CallConfidence.EXACT, via="reflection")
        == CallConfidence.AMBIGUOUS
    )
    assert (
        clamp_confidence(CallConfidence.PROBABLE, via="monkeypatch")
        == CallConfidence.AMBIGUOUS
    )
    assert (
        clamp_confidence(CallConfidence.AMBIGUOUS, via="runtime_trace")
        == CallConfidence.PROBABLE
    )


def test_runtime_traces_reconcile_boosts_gold_edge():
    """Runtime reconcile confirms a gold CALLS edge and boosts confidence."""
    case = next(c for c in _load_manifest()["cases"] if c["id"] == "exact_direct")
    service, scope = _ingest_case(case)
    symbols = {s.name: s for s in service.store.list_symbols(scope)}
    assert "run" in symbols and "helper" in symbols
    edges = [
        e
        for e in service.store.list_edges(scope)
        if e.rel_type == RelType.CALLS.value
        and e.source_id == symbols["run"].id
        and e.target_id == symbols["helper"].id
    ]
    assert edges, "expected static CALLS run→helper"
    static_edge = edges[0]

    actions = reconcile_runtime_traces(
        observed=[
            ObservedCall(
                source=symbols["run"].id,
                target=symbols["helper"].id,
                call_site="exact_direct.py:run",
                count=3,
            )
        ],
        static_edges=[static_edge],
        resolve_symbol=lambda name: name,
    )
    boosts = [a for a in actions if a.kind == "boost"]
    assert boosts, actions
    assert boosts[0].source_id == symbols["run"].id
    assert boosts[0].target_id == symbols["helper"].id
    # Policy: runtime confirmation raises confidence toward EXACT.
    assert boosts[0].confidence in {
        CallConfidence.PROBABLE,
        CallConfidence.EXACT,
    }
    assert boosts[0].metadata.get("provenance") == "runtime_trace" or boosts[
        0
    ].metadata.get("runtime_confirmed")


def test_labeled_corpus_evidence_classes_align_with_policy():
    """Manifest evidence_class labels map to confidence_policy caps."""
    for case in _load_manifest()["cases"]:
        evidence = str(case.get("evidence_class") or "unresolved")
        cap = confidence_for_evidence(evidence)
        if evidence == "exact":
            assert cap == CallConfidence.EXACT
        elif evidence == "ambiguous":
            assert cap == CallConfidence.AMBIGUOUS
        elif evidence == "unresolved":
            assert cap == CallConfidence.UNRESOLVED
