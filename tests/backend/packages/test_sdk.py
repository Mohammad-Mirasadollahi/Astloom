from __future__ import annotations

import httpx

from sdk import AstloomClient


def test_client_builds_url_and_headers():
    client = AstloomClient(
        "http://127.0.0.1:32100",
        default_headers={"X-Tenant-Id": "t"},
    )
    request = client.build_request(
        "POST",
        "/projects/p/tasks",
        correlation_id="corr_1",
        idempotency_key="idem_1",
    )
    assert request["method"] == "POST"
    assert request["url"] == "http://127.0.0.1:32100/api/v1/projects/p/tasks"
    assert request["headers"]["X-Tenant-Id"] == "t"
    assert request["headers"]["X-Correlation-Id"] == "corr_1"
    assert request["headers"]["Idempotency-Key"] == "idem_1"


def test_client_http_transport_get_and_post():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(201, json={"id": "task_1"})

    transport = httpx.MockTransport(handler)
    client = AstloomClient(
        "http://127.0.0.1:32100",
        default_headers={"X-Tenant-Id": "t"},
        http_client=httpx.Client(transport=transport),
    )

    get_resp = client.get("/projects/p", correlation_id="corr_get")
    assert get_resp.status_code == 200
    assert get_resp.json() == {"ok": True}
    assert seen[0].url == "http://127.0.0.1:32100/api/v1/projects/p"
    assert seen[0].headers["X-Tenant-Id"] == "t"
    assert seen[0].headers["X-Correlation-Id"] == "corr_get"

    post_resp = client.post(
        "/projects/p/tasks",
        json={"title": "x"},
        correlation_id="corr_post",
        idempotency_key="idem_1",
    )
    assert post_resp.status_code == 201
    assert post_resp.json() == {"id": "task_1"}
    assert seen[1].method == "POST"
    assert seen[1].url == "http://127.0.0.1:32100/api/v1/projects/p/tasks"
    assert seen[1].headers["X-Correlation-Id"] == "corr_post"
    assert seen[1].headers["Idempotency-Key"] == "idem_1"
