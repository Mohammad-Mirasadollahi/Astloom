"""HTTP content-push routes: auth, ingest-push, file-hashes, typed docs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from code_graph_service.api import build_app
from code_graph_service.core import CodeGraphService
from code_graph_service.testing import InMemoryStore


def _headers(*, token: str | None = None) -> dict[str, str]:
    headers = {
        "X-Tenant-Id": "t",
        "X-Workspace-Id": "w",
        "X-Actor-Id": "tester",
        "Idempotency-Key": "key-1",
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def test_ingest_push_and_file_hashes_roundtrip(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    service = CodeGraphService(InMemoryStore())
    client = TestClient(build_app(service))
    headers = _headers(token="secret-token-123456")

    push = client.post(
        "/api/v1/projects/demo/graph/ingest-push",
        headers=headers,
        json={
            "files": [
                {
                    "file_path": "src/a.py",
                    "source": "def alpha():\n    return 1\n",
                    "language": "python",
                }
            ],
            "present_paths": ["src/a.py"],
            "docs": [
                {
                    "doc_id": "as.doc.test.a",
                    "relative_path": "docs/a.md",
                    "body": "# A\n",
                    "title": "A",
                    "linked_symbol_tokens": [],
                }
            ],
        },
    )
    assert push.status_code == 200, push.text
    body = push.json()
    assert body["files_ingested"] == 1
    assert body["docs"]["docs_upserted"] == 1

    hashes = client.get(
        "/api/v1/projects/demo/graph/file-hashes",
        headers={
            "X-Tenant-Id": "t",
            "X-Workspace-Id": "w",
            "Authorization": "Bearer secret-token-123456",
        },
    )
    assert hashes.status_code == 200
    assert "src/a.py" in hashes.json()["hashes"]
    assert hashes.json()["doc_hashes"]["docs/a.md"]


def test_failed_ingest_does_not_publish_file_hash(monkeypatch):
    from code_graph_service.domain.embeddings import LocalEmbeddingStub

    class _BoomMany(LocalEmbeddingStub):
        def embed_many(self, texts, *, is_query: bool = False):
            raise RuntimeError("boom-embed-many")

    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    service = CodeGraphService(InMemoryStore(), embeddings=_BoomMany())
    client = TestClient(build_app(service))
    headers = _headers(token="secret-token-123456")
    push = client.post(
        "/api/v1/projects/demo/graph/ingest-push",
        headers=headers,
        json={
            "files": [
                {
                    "file_path": "src/a.py",
                    "source": "def alpha():\n    return 1\n",
                    "language": "python",
                }
            ],
            "include_outcomes": True,
        },
    )
    assert push.status_code == 200, push.text
    assert push.json()["files_failed"] == 1
    hashes = client.get(
        "/api/v1/projects/demo/graph/file-hashes",
        headers={
            "X-Tenant-Id": "t",
            "X-Workspace-Id": "w",
            "Authorization": "Bearer secret-token-123456",
        },
    )
    assert hashes.json()["hashes"] == {}


def test_ingest_push_rejects_bad_token(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    client = TestClient(build_app(CodeGraphService(InMemoryStore())))
    response = client.post(
        "/api/v1/projects/demo/graph/ingest-push",
        headers=_headers(token="wrong-token-xxxxxx"),
        json={"files": []},
    )
    assert response.status_code == 401


def test_ingest_push_rejects_missing_token_when_configured(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    client = TestClient(build_app(CodeGraphService(InMemoryStore())))
    response = client.post(
        "/api/v1/projects/demo/graph/ingest-push",
        headers=_headers(token=None),
        json={"files": []},
    )
    assert response.status_code == 401


def test_ingest_push_accepts_ac1_access_token(monkeypatch):
    from usage_profile.mcp_tokens import mint_connect_token

    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    monkeypatch.delenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", raising=False)
    token = mint_connect_token(tenant_id="t", workspace_id="w", project_id="demo")
    client = TestClient(build_app(CodeGraphService(InMemoryStore())))

    response = client.post(
        "/api/v1/projects/demo/graph/ingest-push",
        headers=_headers(token=token),
        json={"files": []},
    )
    assert response.status_code == 200, response.text


def test_ingest_push_rejects_ac1_token_wrong_scope(monkeypatch):
    from usage_profile.mcp_tokens import mint_connect_token

    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    monkeypatch.delenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", raising=False)
    token = mint_connect_token(tenant_id="other-tenant", workspace_id="w", project_id="demo")
    client = TestClient(build_app(CodeGraphService(InMemoryStore())))

    response = client.post(
        "/api/v1/projects/demo/graph/ingest-push",
        headers=_headers(token=token),
        json={"files": []},
    )
    assert response.status_code == 401


def test_ingest_push_rejects_doc_path_traversal(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    client = TestClient(build_app(CodeGraphService(InMemoryStore())))
    response = client.post(
        "/api/v1/projects/demo/graph/ingest-push",
        headers=_headers(token="secret-token-123456"),
        json={
            "files": [],
            "docs": [
                {
                    "doc_id": "as.doc.bad",
                    "relative_path": "../etc/passwd",
                    "body": "x",
                    "title": "bad",
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["docs"]["docs_failed"] == 1


def test_build_app_registers_content_push_routes():
    api = build_app(CodeGraphService(InMemoryStore()))
    paths = {route.path for route in api.routes if hasattr(route, "path")}
    assert "/api/v1/projects/{project_id}/graph/ingest-push" in paths
    assert "/api/v1/projects/{project_id}/graph/ingest-push/cancel" in paths
    assert "/api/v1/projects/{project_id}/graph/file-hashes" in paths
    assert "/api/v1/projects/{project_id}/graph/purge" in paths


def test_purge_wipes_scope(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    service = CodeGraphService(InMemoryStore())
    client = TestClient(build_app(service))
    headers = _headers(token="secret-token-123456")

    client.post(
        "/api/v1/projects/demo/graph/ingest-push",
        headers=headers,
        json={
            "files": [
                {"file_path": "src/a.py", "source": "def a():\n    return 1\n", "language": "python"}
            ],
        },
    )
    response = client.post(
        "/api/v1/projects/demo/graph/purge",
        headers=headers,
        json={"yes": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["purge"]["symbols_before"] > 0

    hashes = client.get("/api/v1/projects/demo/graph/file-hashes", headers=headers)
    assert hashes.json()["hashes"] == {}


def test_purge_requires_yes_confirmation(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    client = TestClient(build_app(CodeGraphService(InMemoryStore())))
    response = client.post(
        "/api/v1/projects/demo/graph/purge",
        headers=_headers(token="secret-token-123456"),
        json={},
    )
    assert response.status_code == 400


def test_purge_rejects_missing_token_when_configured(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CODE_GRAPH_HTTP_TOKEN", "secret-token-123456")
    client = TestClient(build_app(CodeGraphService(InMemoryStore())))
    response = client.post(
        "/api/v1/projects/demo/graph/purge",
        headers=_headers(token=None),
        json={"yes": True},
    )
    assert response.status_code == 401
