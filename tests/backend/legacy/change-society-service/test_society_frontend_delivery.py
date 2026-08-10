from change_society.domain.models import Scope

from conftest import make_service


def test_society_run_creates_frontend_delivery_ticket_and_handoff():
    service = make_service()
    scope = Scope("tenant-a", "workspace-a", "project-a")
    run = service.create_run(scope, "developer-a", "corr-fe", "idem-fe", "checkout-api-refactor", None)
    delivery = service.get_frontend_delivery(scope, run.run_id)
    assert delivery["frontend_work_required"] is True
    assert delivery["team_queue"] == "frontend"
    assert len(delivery["tickets"]) == 1
    assert delivery["tickets"][0]["capability"] == "coordinate_frontend_ui_delivery"
    handoff = delivery["handoff_message"]
    assert handoff is not None
    assert handoff["message_type"] == "frontend_delivery_handoff"
    assert handoff["payload"]["ui_changes"]
