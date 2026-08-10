"""Short real smoke: API → modular MemoryService remember/forget path."""

from __future__ import annotations

from fastapi.testclient import TestClient

from memory_service.api import build_app
from memory_service.core import MemoryService
from memory_service.testing import InMemoryStore


def main() -> None:
    client = TestClient(build_app(service=MemoryService(InMemoryStore())))
    headers = {
        "X-Tenant-Id": "t1",
        "X-Workspace-Id": "w1",
        "X-Actor-Id": "user-1",
        "X-Correlation-Id": "corr-smoke",
    }
    base = "/api/v1/projects/p1"

    created = client.post(
        f"{base}/memory-items",
        headers={**headers, "Idempotency-Key": "smoke-create"},
        json={
            "kind": "working",
            "title": "VPN failover",
            "body": "use secondary gateway on timeout",
            "tags": ["vpn"],
            "state": "active",
        },
    )
    print(f"create [{created.status_code}] {created.json()}")
    assert created.status_code == 200, created.text
    memory_id = created.json()["memory"]["id"]

    listed = client.get(f"{base}/memory-items", headers=headers, params={"q": "vpn"})
    print(f"list [{listed.status_code}] count={len(listed.json()['items'])}")
    assert listed.status_code == 200
    assert any(item["id"] == memory_id for item in listed.json()["items"])

    promoted = client.post(
        f"{base}/memory-items/{memory_id}:promote",
        headers={**headers, "Idempotency-Key": "smoke-promote"},
        json={"reason": "keep for runbooks"},
    )
    print(f"promote [{promoted.status_code}] {promoted.json()}")
    assert promoted.status_code == 200
    item = promoted.json()["memory"]
    assert item["kind"] == "semantic" and item["state"] == "active", item

    bundle_resp = client.post(
        f"{base}/context-bundles",
        headers=headers,
        json={"query": "vpn gateway timeout"},
    )
    print(
        f"retrieve-after-promote [{bundle_resp.status_code}] "
        f"items={len(bundle_resp.json()['bundle']['items'])}"
    )
    assert bundle_resp.status_code == 200
    bundle = bundle_resp.json()["bundle"]
    included = [entry["memory"]["id"] for entry in bundle["items"]]
    assert memory_id in included, bundle["excluded"]

    forgotten = client.post(
        f"{base}/memory-items/{memory_id}:deprecate",
        headers={**headers, "Idempotency-Key": "smoke-forget"},
        json={"reason": "outdated"},
    )
    print(f"deprecate [{forgotten.status_code}] {forgotten.json()}")
    assert forgotten.status_code == 200
    assert forgotten.json()["memory"]["state"] == "deprecated"

    after_resp = client.post(
        f"{base}/context-bundles",
        headers=headers,
        json={"query": "vpn gateway timeout"},
    )
    after = after_resp.json()["bundle"]
    print(
        f"retrieve-after-forget [{after_resp.status_code}] "
        f"items={len(after['items'])} excluded={after['excluded']}"
    )
    assert after_resp.status_code == 200
    included = [entry["memory"]["id"] for entry in after["items"]]
    excluded = {entry["id"]: entry["reason"] for entry in after["excluded"]}
    assert memory_id not in included
    assert memory_id in excluded and "inactive" in excluded[memory_id]
    print("SMOKE_OK create→list→promote→retrieve→deprecate→exclude")


if __name__ == "__main__":
    main()
