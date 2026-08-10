from change_society.application.frontend_delivery import FRONTEND_DELIVERY_CAPABILITY, analyze_frontend_signals


def test_analyze_frontend_signals_for_api_refactor_scenario():
    signals = analyze_frontend_signals(
        scenario_id="checkout-api-refactor",
        impacts=["mobile clients", "taxIncluded field"],
        tasks=["restore backward compatible field"],
        policies=["api-breaking-change"],
        evidence_refs=["ev_api_diff"],
    )
    assert signals["frontend_work_required"] is True
    assert signals["team_queue"] == "frontend"
    assert "mobile" in signals["matched_keywords"]


def test_frontend_delivery_capability_constant():
    assert FRONTEND_DELIVERY_CAPABILITY == "coordinate_frontend_ui_delivery"
