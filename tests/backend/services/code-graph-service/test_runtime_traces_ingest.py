"""GAP-T02: runtime-trace HTTP / service ingest wiring."""

from __future__ import annotations

from code_graph_service.api import build_app
from code_graph_service.core import CodeGraphService
from code_graph_service.domain.enums import CallConfidence, RelType
from code_graph_service.domain.models import Scope
from code_graph_service.testing import InMemoryStore
from fastapi.testclient import TestClient


def test_ingest_runtime_traces_service_boosts_static_edge():
    store = InMemoryStore()
    service = CodeGraphService(store)
    scope = Scope(tenant_id="t", workspace_id="w", project_id="rt")
    service.ingest_file(
        scope,
        "actor",
        "c1",
        "file-1",
        {
            "file_path": "mod.py",
            "source": "def helper():\n    return 1\n\ndef run():\n    return helper()\n",
            "language": "python",
        },
    )
    symbols = {s.name: s for s in store.list_symbols(scope) if s.kind.value in {"function", "method"}}
    result = service.ingest_runtime_traces(
        scope,
        "actor",
        "c2",
        "rt-1",
        {
            "calls": [
                {
                    "source": symbols["run"].qualified_name,
                    "target": symbols["helper"].qualified_name,
                    "count": 4,
                }
            ]
        },
    )
    assert result["boosted"] >= 1 or result["emitted"] >= 1
    edges = [
        e
        for e in store.list_edges(scope)
        if e.rel_type == RelType.CALLS.value
        and e.source_id == symbols["run"].id
        and e.target_id == symbols["helper"].id
    ]
    assert edges
    assert edges[0].confidence in {CallConfidence.EXACT, CallConfidence.PROBABLE}
    if edges[0].metadata.get("runtime_confirmed"):
        assert edges[0].metadata.get("provenance") == "runtime_trace"


def test_ingest_runtime_traces_http_route():
    store = InMemoryStore()
    service = CodeGraphService(store)
    scope = Scope(tenant_id="t", workspace_id="w", project_id="http-rt")
    service.ingest_file(
        scope,
        "actor",
        "c1",
        "file-1",
        {
            "file_path": "mod.py",
            "source": "def a():\n    return 1\n\ndef b():\n    return a()\n",
            "language": "python",
        },
    )
    symbols = {s.name: s for s in store.list_symbols(scope)}
    api = build_app(service)
    client = TestClient(api)
    paths = {route.path for route in api.routes if hasattr(route, "path")}
    assert "/api/v1/projects/{project_id}/graph/ingest-runtime-traces" in paths
    resp = client.post(
        "/api/v1/projects/http-rt/graph/ingest-runtime-traces",
        headers={
            "X-Tenant-Id": "t",
            "X-Workspace-Id": "w",
            "X-Actor-Id": "actor",
            "Idempotency-Key": "http-rt-1",
        },
        json={
            "calls": [
                {
                    "caller": symbols["b"].qualified_name,
                    "callee": symbols["a"].qualified_name,
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["observed"] == 1
    assert body["boosted"] + body["emitted"] >= 1


def test_build_app_registers_runtime_traces_route():
    service = CodeGraphService(InMemoryStore())
    api = build_app(service)
    paths = {route.path for route in api.routes if hasattr(route, "path")}
    assert "/api/v1/projects/{project_id}/graph/ingest-runtime-traces" in paths
