from __future__ import annotations

import pytest

from change_society.domain.models import Scope
from change_society.infrastructure.evidence_catalog import DEMO_SCENARIO_IDS, SCENARIOS

from conftest import make_service


@pytest.mark.parametrize("scenario_id", DEMO_SCENARIO_IDS)
def test_each_demo_domain_runs_orchestration_with_rules(scenario_id: str):
    catalog = {item.scenario_id: item for item in SCENARIOS}
    scenario = catalog[scenario_id]
    assert scenario.domain
    assert scenario.governance_rules
    assert "multi_agent_orchestration" in scenario.feature_demonstrations

    service = make_service()
    scope = Scope("tenant-a", "workspace-a", "project-a")
    run = service.create_run(scope, "developer-a", f"corr-{scenario_id}", f"idem-{scenario_id}", scenario_id, None)
    delivery = service.get_frontend_delivery(scope, run.run_id)
    assert delivery["frontend_work_required"] is True
    assert any(item["capability"] == "coordinate_frontend_ui_delivery" for item in delivery["tickets"])
    assert run.metrics.get("frontend_delivery_ticket_count", 0) >= 1
