from change_society.application.judging_engineering_profile import build_judging_engineering_profile


def test_judging_profile_maps_four_criteria_with_code_modules():
    profile = build_judging_engineering_profile(model_health={"provider": "deterministic_fake"})
    assert len(profile["criteria"]) == 4
    weights = sorted(item["weight_percent"] for item in profile["criteria"])
    assert weights == [15, 25, 30, 30]
    technical = next(item for item in profile["criteria"] if item["id"] == "technical_depth_engineering")
    modules = {entry["modules"][0] for entry in technical["implemented_in_code"]}
    assert "infrastructure/qwen_client.py" in modules
    assert "infrastructure/mcp_tool_gateway.py" in modules
