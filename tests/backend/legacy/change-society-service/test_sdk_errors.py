from __future__ import annotations

import httpx

from change_society_sdk import ChangeSocietyClient, ChangeSocietySdkError, Scope


def test_sdk_surfaces_structured_api_errors():
    def handler(request):
        return httpx.Response(404, json={"error": {"error_code": "society_run_not_found", "message": "missing", "retryable": False}})

    client = ChangeSocietyClient("https://example.test", Scope("t", "w", "p", "actor"), transport=httpx.MockTransport(handler))
    try:
        client.get_run("missing")
        raise AssertionError("expected sdk error")
    except ChangeSocietySdkError as exc:
        assert exc.code == "society_run_not_found"
        assert exc.retryable is False
    finally:
        client.close()


def test_sdk_lists_scenarios_and_tickets():
    def handler(request):
        if request.url.path.endswith("/demo-scenarios"):
            return httpx.Response(200, json={"items": [{"scenario_id": "pricing-refactor"}], "page": {}, "correlation_id": "c"})
        if "/agent-tickets" in request.url.path:
            return httpx.Response(200, json={"items": [{"ticket_id": "ticket_1"}], "page": {}, "correlation_id": "c"})
        return httpx.Response(500, json={"error": {"error_code": "internal_error", "message": "fail"}})

    client = ChangeSocietyClient("https://example.test", Scope("t", "w", "p", "actor"), transport=httpx.MockTransport(handler))
    try:
        assert client.list_scenarios()[0]["scenario_id"] == "pricing-refactor"
        assert client.list_agent_tickets("run_1")[0]["ticket_id"] == "ticket_1"
    finally:
        client.close()
