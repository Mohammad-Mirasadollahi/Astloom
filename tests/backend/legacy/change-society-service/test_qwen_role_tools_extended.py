from __future__ import annotations

from change_society.application.qwen_role_tools import RoleToolExecutor, qwen_tool_definitions_for_role


def test_rank_impact_keywords_orders_by_evidence_frequency():
    prompt = (
        "EVIDENCE:\n"
        "[ev_a] A: customer price checkout base_price\n"
        "[ev_b] B: billing tests only"
    )
    executor = RoleToolExecutor()
    result = executor.invoke(
        "impact_analyst",
        "rank_impact_keywords",
        {"keywords": ["billing", "customer price", "missing"]},
        prompt,
    )
    ranked = result.output["ranked_keywords"]
    assert ranked[0] == "customer price"
    assert "missing" in ranked


def test_unknown_tool_returns_error_payload():
    executor = RoleToolExecutor()
    result = executor.invoke("change_analyst", "not_a_tool", {}, "EVIDENCE:\n")
    assert result.output["error"] == "unknown_tool"


def test_mcp_gateway_delegate_used_when_configured():
    calls = []

    def gateway(name, args):
        calls.append((name, args))
        return {"delegated": True}

    executor = RoleToolExecutor(mcp_gateway=gateway)
    out = executor.invoke("policy_guardian", "validate_policy_tags", {"tags": ["a"]}, "")
    assert out.output["delegated"] is True
    assert calls[0][0] == "validate_policy_tags"


def test_impact_analyst_has_tool_definition():
    assert qwen_tool_definitions_for_role("impact_analyst")[0]["function"]["name"] == "rank_impact_keywords"
