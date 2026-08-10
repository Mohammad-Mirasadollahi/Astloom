"""Short live smoke against real PostgreSQL (remember / forget path)."""

from __future__ import annotations

import os
import uuid

from fastapi.testclient import TestClient

from memory_service.api import build_app
from memory_service.core import MemoryService
from memory_service.postgres_store import PostgresStore


def main() -> None:
    database_url = os.environ.get(
        "ASTLOOM_MEMORY_SERVICE_DATABASE_URL",
        "",
    ).strip()
    if not database_url:
        raise SystemExit("ASTLOOM_MEMORY_SERVICE_DATABASE_URL is required")

    project_id = f"smoke-mem-{uuid.uuid4().hex[:10]}"
    store = PostgresStore(database_url)
    client = TestClient(build_app(service=MemoryService(store)))
    headers = {
        "X-Tenant-Id": "t-smoke",
        "X-Workspace-Id": "w-smoke",
        "X-Actor-Id": "user-smoke",
        "X-Correlation-Id": f"corr-{project_id}",
    }
    base = f"/api/v1/projects/{project_id}"
    memory_id: str | None = None

    try:
        created = client.post(
            f"{base}/memory-items",
            headers={**headers, "Idempotency-Key": f"{project_id}-create"},
            json={
                "kind": "working",
                "title": "VPN failover",
                "body": "use secondary gateway on timeout",
                "tags": ["vpn"],
                "state": "active",
            },
        )
        print(f"create [{created.status_code}] project={project_id}")
        assert created.status_code == 200, created.text
        memory_id = created.json()["memory"]["id"]
        print(f"  memory_id={memory_id} kind={created.json()['memory']['kind']}")

        listed = client.get(f"{base}/memory-items", headers=headers, params={"q": "vpn"})
        print(f"list [{listed.status_code}] count={len(listed.json()['items'])}")
        assert listed.status_code == 200
        assert any(item["id"] == memory_id for item in listed.json()["items"])

        promoted = client.post(
            f"{base}/memory-items/{memory_id}:promote",
            headers={**headers, "Idempotency-Key": f"{project_id}-promote"},
            json={"reason": "keep for runbooks"},
        )
        print(f"promote [{promoted.status_code}] {promoted.json()['memory']['kind']}/{promoted.json()['memory']['state']}")
        assert promoted.status_code == 200
        item = promoted.json()["memory"]
        assert item["kind"] == "semantic" and item["state"] == "active", item

        # Prove durability: new store connection reads the same row.
        reload_store = PostgresStore(database_url)
        from memory_service.core import Scope

        reloaded = reload_store.get_memory(memory_id, Scope("t-smoke", "w-smoke", project_id))
        assert reloaded.kind.value == "semantic" and reloaded.state.value == "active"
        print(f"reload-from-db kind={reloaded.kind.value} state={reloaded.state.value}")
        reload_store.close()

        bundle_resp = client.post(
            f"{base}/context-bundles",
            headers=headers,
            json={"query": "vpn gateway timeout"},
        )
        bundle = bundle_resp.json()["bundle"]
        print(f"retrieve-after-promote [{bundle_resp.status_code}] items={len(bundle['items'])}")
        assert bundle_resp.status_code == 200
        included = [entry["memory"]["id"] for entry in bundle["items"]]
        assert memory_id in included, bundle["excluded"]

        forgotten = client.post(
            f"{base}/memory-items/{memory_id}:deprecate",
            headers={**headers, "Idempotency-Key": f"{project_id}-forget"},
            json={"reason": "outdated"},
        )
        print(f"deprecate [{forgotten.status_code}] state={forgotten.json()['memory']['state']}")
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
        print("SMOKE_OK postgres create→list→promote→reload→retrieve→deprecate→exclude")
    finally:
        # Best-effort cleanup of this smoke project scope.
        scope_key = f"t-smoke|w-smoke|{project_id}|"
        with store._connection.cursor() as cursor:
            cursor.execute(
                """DELETE FROM memory.memory_items
                   WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s""",
                ("t-smoke", "w-smoke", project_id),
            )
            cursor.execute("DELETE FROM memory.idempotency WHERE scope_key=%s", (scope_key,))
            cursor.execute(
                """DELETE FROM memory.outbox
                   WHERE payload->>'tenant_id'=%s
                     AND payload->>'workspace_id'=%s
                     AND payload->>'project_id'=%s""",
                ("t-smoke", "w-smoke", project_id),
            )
        store.close()
        print(f"cleanup project={project_id}")


if __name__ == "__main__":
    main()
