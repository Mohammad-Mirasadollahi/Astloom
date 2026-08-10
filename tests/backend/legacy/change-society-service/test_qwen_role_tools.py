from change_society.application.qwen_role_tools import RoleToolExecutor, parse_evidence_catalog, qwen_tool_definitions_for_role


def test_parse_evidence_catalog_from_user_prompt():
    prompt = "REQUEST:\nx\nEVIDENCE:\n[ev_a] Title A: body a\n[ev_b] Title B: body b\nPRIOR STRUCTURED FINDINGS:\n{}"
    catalog = parse_evidence_catalog(prompt)
    assert catalog["ev_a"]["title"] == "Title A"
    assert "body b" in catalog["ev_b"]["content"]


def test_role_tools_for_context_scout_and_policy_guardian():
    assert qwen_tool_definitions_for_role("context_scout")[0]["function"]["name"] == "fetch_evidence_by_id"
    assert qwen_tool_definitions_for_role("policy_guardian")[0]["function"]["name"] == "validate_policy_tags"
    assert qwen_tool_definitions_for_role("change_analyst") == []


def test_local_tool_executor_fetch_and_validate():
    prompt = "EVIDENCE:\n[ev_policy_revenue] Revenue policy: billing changes need approval."
    executor = RoleToolExecutor()
    fetched = executor.invoke("context_scout", "fetch_evidence_by_id", {"evidence_id": "ev_policy_revenue"}, prompt)
    assert fetched.output["found"] is True
    validated = executor.invoke(
        "policy_guardian",
        "validate_policy_tags",
        {"tags": ["revenue-impacting-change"], "scenario_required_policies": ["revenue-impacting-change"]},
        prompt,
    )
    assert validated.output["matched"] == ["revenue-impacting-change"]
