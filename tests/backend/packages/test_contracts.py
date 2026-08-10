from __future__ import annotations

from contracts import make_error_envelope, make_page, validate_error_envelope, validate_page
from contracts.api import load_example


def test_error_envelope_round_trip():
    payload = make_error_envelope(
        error_code="task_not_found",
        category="not_found_error",
        message="Task was not found.",
        correlation_id="corr_1",
    )
    assert validate_error_envelope(payload) == []


def test_page_round_trip():
    payload = make_page([{"id": "1"}], page_size=50, correlation_id="corr_1")
    assert validate_page(payload) == []
    assert payload["page"]["has_more"] is False


def test_bundled_examples_validate():
    assert validate_error_envelope(load_example("error.json")) == []
    assert validate_page(load_example("page.json")) == []
