"""HTTP API package layout stays import-compatible after modularization."""

from code_graph_service.api import _is_loopback_request, app, build_app
from code_graph_service.core import CodeGraphService
from code_graph_service.testing import InMemoryStore


def test_build_app_registers_core_routes():
    service = CodeGraphService(InMemoryStore())
    api = build_app(service)
    paths = {route.path for route in api.routes if hasattr(route, "path")}
    assert "/health" in paths
    assert "/api/v1/projects/{project_id}/graph/ingest-file" in paths
    assert "/api/v1/projects/{project_id}/graph/reconcile-after-edit" in paths
    assert "/api/v1/projects/{project_id}/graph/edit-session/rename" in paths
    assert "/api/v1/llm/complete" in paths
    assert api.state.container.graph is service


def test_app_alias_is_build_app_factory():
    assert app is build_app


def test_is_loopback_request_exported():
    assert callable(_is_loopback_request)
