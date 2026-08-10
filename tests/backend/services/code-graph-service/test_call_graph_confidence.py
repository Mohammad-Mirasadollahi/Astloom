"""GAP-T02: reflection / monkeypatch confidence caps and runtime-trace boosts."""

from __future__ import annotations

from code_graph_service.domain.confidence_policy import (
    clamp_confidence,
    confidence_for_evidence,
    impact_eligible,
    parse_call_confidence,
)
from code_graph_service.domain.enums import CallConfidence
from code_graph_service.domain.models import GraphEdge, Scope
from code_graph_service.domain.runtime_traces import (
    ObservedCall,
    parse_runtime_trace_payload,
    reconcile_runtime_traces,
)


def test_parse_call_confidence_null_and_blank_default_exact():
    assert parse_call_confidence(None) == CallConfidence.EXACT
    assert parse_call_confidence("") == CallConfidence.EXACT
    assert parse_call_confidence("   ") == CallConfidence.EXACT


def test_parse_call_confidence_invalid_token_probable():
    assert parse_call_confidence("not-a-confidence") == CallConfidence.PROBABLE
    assert parse_call_confidence("None") == CallConfidence.PROBABLE


def test_parse_call_confidence_preserves_valid():
    assert parse_call_confidence("exact") == CallConfidence.EXACT
    assert parse_call_confidence(CallConfidence.AMBIGUOUS) == CallConfidence.AMBIGUOUS
    assert parse_call_confidence("unresolved") == CallConfidence.UNRESOLVED


def test_reflection_caps_exact_to_ambiguous():
    assert (
        clamp_confidence(CallConfidence.EXACT, via="reflection")
        == CallConfidence.AMBIGUOUS
    )


def test_monkeypatch_caps_probable_to_ambiguous():
    assert (
        clamp_confidence(CallConfidence.PROBABLE, via="monkeypatch")
        == CallConfidence.AMBIGUOUS
    )


def test_monkey_patch_alias_caps_exact():
    assert (
        clamp_confidence(CallConfidence.EXACT, via="monkey_patch")
        == CallConfidence.AMBIGUOUS
    )


def test_reflection_keeps_unresolved():
    assert (
        clamp_confidence(CallConfidence.UNRESOLVED, via="reflection")
        == CallConfidence.UNRESOLVED
    )


def test_runtime_trace_boosts_probable_to_exact():
    assert (
        clamp_confidence(CallConfidence.PROBABLE, via="runtime_trace")
        == CallConfidence.EXACT
    )


def test_runtime_trace_boosts_ambiguous_to_probable():
    assert (
        clamp_confidence(CallConfidence.AMBIGUOUS, via="runtime_trace")
        == CallConfidence.PROBABLE
    )


def test_evidence_class_caps():
    assert confidence_for_evidence("reflection") == CallConfidence.AMBIGUOUS
    assert confidence_for_evidence("di") == CallConfidence.PROBABLE
    assert confidence_for_evidence("runtime_trace") == CallConfidence.EXACT


def test_impact_eligibility_default_floor():
    assert impact_eligible(CallConfidence.EXACT) is True
    assert impact_eligible(CallConfidence.PROBABLE) is True
    assert impact_eligible(CallConfidence.AMBIGUOUS) is False
    assert impact_eligible(CallConfidence.UNRESOLVED) is False
    assert impact_eligible(CallConfidence.AMBIGUOUS, min_confidence="ambiguous") is True


def test_directed_impact_default_floor_excludes_ambiguous():
    """GAP-T02: default impact floor is probable — ambiguous edges stay out."""
    from code_graph_service.domain.enums import DocStatus, SymbolKind
    from code_graph_service.domain.impact import directed_impact
    from code_graph_service.domain.models import GraphEdge, GraphSymbol, Scope

    scope = Scope(tenant_id="t", workspace_id="w", project_id="p")

    def _sym(sid: str) -> GraphSymbol:
        return GraphSymbol(
            id=sid,
            scope=scope,
            kind=SymbolKind.FUNCTION,
            file_path="a.py",
            name=sid,
            qualified_name=sid,
            signature=f"{sid}()",
            body="",
            hash_value=sid,
            ai_documentation="",
            doc_status=DocStatus.UNCHANGED,
            embedding=[],
        )

    symbols = {s: _sym(s) for s in ("seed", "good", "weak")}
    edges = [
        GraphEdge(
            id="e1",
            scope=scope,
            rel_type="CALLS",
            source_id="seed",
            target_id="good",
            confidence=CallConfidence.PROBABLE,
        ),
        GraphEdge(
            id="e2",
            scope=scope,
            rel_type="CALLS",
            source_id="seed",
            target_id="weak",
            confidence=CallConfidence.AMBIGUOUS,
        ),
    ]
    out = directed_impact("seed", symbols, edges, direction="downstream", max_depth=1)
    ids = {r["symbol_id"] for r in out["blast"]}
    assert "good" in ids
    assert "weak" not in ids
    wide = directed_impact(
        "seed",
        symbols,
        edges,
        direction="downstream",
        max_depth=1,
        min_confidence="ambiguous",
    )
    assert "weak" in {r["symbol_id"] for r in wide["blast"]}


def test_parse_runtime_trace_payload_aliases():
    calls = parse_runtime_trace_payload(
        {"calls": [{"caller": "a.fn", "callee": "b.fn", "count": 2}]}
    )
    assert len(calls) == 1
    assert calls[0].source == "a.fn"
    assert calls[0].target == "b.fn"
    assert calls[0].count == 2


def test_reconcile_boosts_matching_static_and_demotes_contradiction():
    scope = Scope(tenant_id="t", workspace_id="w", project_id="p")
    static = [
        GraphEdge(
            id="e1",
            scope=scope,
            rel_type="CALLS",
            source_id="sym:a",
            target_id="sym:wrong",
            confidence=CallConfidence.EXACT,
            metadata={"file_path": "a.py", "call_site": "site-1", "call": "wrong"},
        ),
        GraphEdge(
            id="e2",
            scope=scope,
            rel_type="CALLS",
            source_id="sym:a",
            target_id="sym:right",
            confidence=CallConfidence.AMBIGUOUS,
            metadata={"file_path": "a.py", "call_site": "site-1", "call": "right"},
        ),
    ]
    observed = [
        ObservedCall(source="sym:a", target="sym:right", call_site="site-1", count=3),
    ]
    actions = reconcile_runtime_traces(
        observed=observed,
        static_edges=static,
        resolve_symbol=lambda tok: tok,
    )
    kinds = {a.kind for a in actions}
    assert "boost" in kinds
    assert "demote" in kinds
    boost = next(a for a in actions if a.kind == "boost")
    demote = next(a for a in actions if a.kind == "demote")
    assert boost.confidence == CallConfidence.PROBABLE  # ambiguous + runtime boost
    assert boost.metadata.get("runtime_confirmed") is True
    assert demote.target_id == "sym:wrong"
    assert demote.confidence in {CallConfidence.AMBIGUOUS, CallConfidence.UNRESOLVED}
    assert demote.metadata.get("runtime_contradicted") is True


def test_reconcile_emits_new_runtime_edge():
    scope = Scope(tenant_id="t", workspace_id="w", project_id="p")
    actions = reconcile_runtime_traces(
        observed=[ObservedCall(source="s1", target="t1")],
        static_edges=[],
        resolve_symbol=lambda tok: tok,
    )
    assert len(actions) == 1
    assert actions[0].kind == "emit"
    assert actions[0].confidence == CallConfidence.EXACT  # probable + boost
    assert actions[0].metadata.get("provenance") == "runtime_trace"
