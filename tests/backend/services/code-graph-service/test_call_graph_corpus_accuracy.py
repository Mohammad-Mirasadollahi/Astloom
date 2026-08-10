"""GAP-T02: labeled call-graph corpus accuracy gate (precision/recall thresholds)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore

CORPUS = Path(__file__).resolve().parent / "call_graph_corpus"
MANIFEST = CORPUS / "manifest.json"
SOURCES = CORPUS / "sources"
SCOPE = Scope("t", "w", "p")


def _short_name(qualified: str) -> str:
    return qualified.rsplit(".", 1)[-1]


def _predicted_calls(service: CodeGraphService, scope: Scope) -> set[tuple[str, str]]:
    edges = [e for e in service.store.list_edges(scope) if e.rel_type == "CALLS"]
    symbols = {s.id: s for s in service.store.list_symbols(scope)}
    out: set[tuple[str, str]] = set()
    for edge in edges:
        src = symbols.get(edge.source_id)
        tgt = symbols.get(edge.target_id)
        if src is None or tgt is None:
            continue
        out.add((_short_name(src.qualified_name or src.name), _short_name(tgt.qualified_name or tgt.name)))
    return out


def test_call_graph_corpus_accuracy_gate():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    thresholds = manifest["thresholds"]
    cases = manifest["cases"]
    true_pos = 0
    false_pos = 0
    false_neg = 0
    details: list[dict] = []

    for case in cases:
        store = InMemoryStore()
        service = CodeGraphService(store)
        source = (SOURCES / case["source_file"]).read_text(encoding="utf-8")
        service.ingest_file(
            SCOPE,
            "agent",
            "corr",
            f"k-{case['id']}",
            {
                "file_path": f"corpus/{case['source_file']}",
                "source": source,
                "language": case.get("language", "python"),
            },
        )
        predicted = _predicted_calls(service, SCOPE)
        gold = {(g["caller"], g["callee"]) for g in case.get("gold_calls", [])}
        allow_unresolved = set(case.get("allow_unresolved_refs") or [])

        # Drop predicted edges that only name unresolved external stubs when allowed.
        filtered_pred = set()
        for caller, callee in predicted:
            if callee in allow_unresolved or callee.startswith("missing_"):
                continue
            filtered_pred.add((caller, callee))

        if case.get("evidence_class") == "ambiguous":
            # Accept any predicted edge whose caller matches gold caller and callee name matches.
            gold_callers = {c for c, _ in gold}
            matched = {(c, t) for c, t in filtered_pred if c in gold_callers and any(t == g for _, g in gold)}
            tp = len(matched) if matched else 0
            fp = max(0, len(filtered_pred) - tp)
            fn = 0 if matched else len(gold)
        elif case.get("evidence_class") == "unresolved":
            # Gold is empty; unresolved refs should not invent project callees.
            tp = 0
            fp = len(filtered_pred)
            fn = 0
        else:
            tp = len(filtered_pred & gold)
            fp = len(filtered_pred - gold)
            fn = len(gold - filtered_pred)

        true_pos += tp
        false_pos += fp
        false_neg += fn
        details.append(
            {
                "id": case["id"],
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "predicted": sorted(filtered_pred),
                "gold": sorted(gold),
            }
        )

    precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) else 1.0
    recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) else 1.0
    assert precision >= float(thresholds["precision"]), (precision, details)
    assert recall >= float(thresholds["recall"]), (recall, details)
