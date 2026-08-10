import json
import httpx

from change_society_sdk import ChangeSocietyClient, Scope


def test_python_sdk_propagates_scope_and_idempotency():
    seen = {}
    def handler(request):
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"society_run": {"run_id": "run_1", "state": "awaiting_approval"}, "correlation_id": "corr_1"})
    client = ChangeSocietyClient("https://example.test", Scope("t", "w", "p", "actor"), transport=httpx.MockTransport(handler))
    try:
        run = client.create_run("pricing-refactor", idempotency_key="idem-1")
        assert run["run_id"] == "run_1"
        assert seen["headers"]["x-tenant-id"] == "t"
        assert seen["headers"]["idempotency-key"] == "idem-1"
    finally:
        client.close()
