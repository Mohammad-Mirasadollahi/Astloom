"""Unit tests for the reference LangGraph change-analyst pipeline (integrator example worker)."""

from __future__ import annotations

from integrator_worker_support import ensure_worker_import_path

ensure_worker_import_path()

from worker.graph.change_analyst_graph import build_change_analyst_graph, run_graph  # noqa: E402
from worker.graph.nodes import assess_risk, parse_inputs  # noqa: E402


def test_parse_inputs_extracts_evidence_refs():
    state = parse_inputs(
        {
            "user_prompt": "EVIDENCE:\n[ev_api_diff] removed taxIncluded\nmemory_ctx_1",
            "system_prompt": "sys",
            "role": "change_analyst",
        }
    )
    assert "ev_api_diff" in state["evidence_refs"]
    assert state["is_rebuttal"] is False


def test_assess_risk_low_on_breaking_evidence_without_rebuttal():
    base = {
        "user_prompt": "OpenAPI ev_api_diff taxIncluded mobile clients",
        "is_rebuttal": False,
        "evidence_refs": ["ev_api_diff"],
    }
    state = assess_risk(base)
    assert state["risk_level"] == "low"
    assert "refactor" in state["summary"].lower() or "internal" in state["summary"].lower()


def test_assess_risk_high_on_rebuttal_with_breaking_evidence():
    base = {
        "user_prompt": "ONE BOUNDED REBUTTAL taxIncluded ev_api_diff OpenAPI",
        "is_rebuttal": True,
        "evidence_refs": ["ev_api_diff"],
    }
    state = assess_risk(base)
    assert state["risk_level"] == "high"
    assert "taxIncluded" in state["summary"]


def test_run_graph_produces_valid_role_output_shape():
    compiled = build_change_analyst_graph()
    payload = run_graph(
        compiled,
        role="change_analyst",
        system_prompt="Return RoleOutput JSON",
        user_prompt="REQUEST:\nRefactor\nEVIDENCE:\n[ev_api_diff] taxIncluded OpenAPI",
        schema_title="RoleOutput",
    )
    required = {
        "summary",
        "risk_level",
        "findings",
        "impacts",
        "policies",
        "tasks",
        "evidence_refs",
        "assumptions",
        "unresolved_questions",
        "confidence",
        "recommended_action",
    }
    assert required <= set(payload.keys())
    assert 0 <= payload["confidence"] <= 1
