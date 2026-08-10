from __future__ import annotations

from change_society.domain.models import RunState
from test_change_society import SCOPE, make_service


def test_reject_and_request_changes_transition_run_state():
    service = make_service()
    run = service.create_run(SCOPE, "developer-a", "corr-reject", "reject-1", "pricing-refactor", None)
    rejected = service.decide(SCOPE, run.run_id, "reviewer", "corr-2", "reject-key", "reject", "Not acceptable.", run.version)
    assert rejected.state == RunState.REJECTED

    run2 = service.create_run(SCOPE, "developer-a", "corr-rework", "rework-1", "password-migration", None)
    rework = service.decide(SCOPE, run2.run_id, "reviewer", "corr-3", "rework-key", "request_changes", "Need more evidence.", run2.version)
    assert rework.state == RunState.REWORK_REQUESTED
