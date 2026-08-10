import asyncio

from httpx import ASGITransport, AsyncClient

from docs_sync_service.api import app
from docs_sync_service.core import ConflictError, DocsSyncService, NotFoundError, Scope, digest, normalize_source
from docs_sync_service.testing import InMemoryStore


SCOPE = Scope("t", "w", "p")
H = {"X-Tenant-Id": "t", "X-Workspace-Id": "w", "X-Actor-Id": "agent", "Idempotency-Key": "one"}


class ApiClient:
    def __init__(self, api):
        self.api = api

    def request(self, method: str, url: str, **kwargs):
        async def execute():
            async with AsyncClient(transport=ASGITransport(app=self.api), base_url="http://test") as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(execute())

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)


def symbol_payload(path="auth.login", kind="function", body="def login():\n    return True\n", **extra):
    return {
        "repo": "astloom",
        "file_path": "src/auth.py",
        "symbol_path": path,
        "kind": kind,
        "body": body,
        "doc_required": extra.pop("doc_required", True),
        "tags": extra.pop("tags", ["auth", "security"]),
        **extra,
    }


def frontmatter(doc_id="doc-login", symbols=None):
    return {
        "doc_id": doc_id,
        "title": "Login documentation",
        "owner": "platform",
        "status": "active",
        "schema_version": "1.0.0",
        "linked_symbols": symbols or ["auth.login"],
        "decision_refs": ["decision-1"],
    }


def test_stale_doc_drift_ci_gate_and_issue_task_refs():
    store = InMemoryStore()
    service = DocsSyncService(store)

    original = "def login():\n    return check_password()\n"
    symbol = service.index_symbol(SCOPE, "agent", "corr", "sym-1", symbol_payload(body=original))
    document = service.index_document(
        SCOPE,
        "agent",
        "corr",
        "doc-1",
        {"path": "docs/login.md", "frontmatter": frontmatter(), "body": "Login flow."},
    )
    assert service.index_document(
        SCOPE,
        "agent",
        "corr",
        "doc-1",
        {"path": "docs/login.md", "frontmatter": frontmatter(), "body": "Login flow."},
    ).id == document.id

    service.register_anchor(
        SCOPE,
        "agent",
        "corr",
        "anchor-1",
        {"doc_id": document.id, "symbol_id": symbol.id, "recorded_hash": symbol.body_hash},
    )

    changed = service.index_symbol(
        SCOPE,
        "agent",
        "corr",
        "sym-2",
        symbol_payload(body="def login():\n    return check_password() and mfa()\n"),
    )
    findings = service.detect_drift(SCOPE, "agent", "corr", "drift-1", [changed.id])
    assert len(findings) == 1
    assert findings[0].drift_type.value == "stale_doc"
    assert findings[0].severity.value == "critical"
    assert findings[0].issue_ref.startswith("issue:")
    assert findings[0].task_ref.startswith("task:docs-agent:")
    assert store.outbox()[-1]["event_type"] == "DocumentationDriftDetected"

    gate = service.evaluate_ci_gate(SCOPE)
    assert gate["decision"] == "fail"
    assert gate["blockers"][0]["id"] == findings[0].id

    waived = service.evaluate_ci_gate(SCOPE, [findings[0].id])
    assert waived["decision"] == "pass"

    other = service.list_drift_findings(Scope("other", "w", "p"))
    assert other == []


def test_get_doc_coverage_empty_is_not_perfect():
    store = InMemoryStore()
    service = DocsSyncService(store)
    coverage = service.get_doc_coverage(SCOPE)
    assert coverage["required_symbols"] == 0
    assert coverage["documented_symbols"] == 0
    assert coverage["coverage_ratio"] is None
    assert coverage["empty_reason"] == "no_required_symbols_registered"


def test_document_update_increments_version_and_anchor_update_is_unique():
    store = InMemoryStore()
    service = DocsSyncService(store)
    symbol = service.index_symbol(SCOPE, "agent", "corr", "sym-v1", symbol_payload())
    first = service.index_document(
        SCOPE,
        "agent",
        "corr",
        "doc-v1",
        {"path": "docs/login.md", "frontmatter": frontmatter(), "body": "Version one"},
    )
    second = service.index_document(
        SCOPE,
        "agent",
        "corr-2",
        "doc-v2",
        {"path": "docs/login.md", "frontmatter": frontmatter(), "body": "Version two"},
    )
    assert second.id == first.id
    assert second.version == 2
    assert second.body == "Version two"

    initial = service.register_anchor(
        SCOPE,
        "agent",
        "corr",
        "anchor-v1",
        {"doc_id": second.id, "symbol_id": symbol.id, "recorded_hash": symbol.body_hash},
    )
    changed = service.index_symbol(
        SCOPE,
        "agent",
        "corr-3",
        "sym-v2",
        symbol_payload(body="def login():\n    return mfa()\n"),
    )
    current = service.register_anchor(
        SCOPE,
        "agent",
        "corr-3",
        "anchor-v2",
        {"doc_id": second.id, "symbol_id": changed.id, "recorded_hash": changed.body_hash},
    )
    anchors = store.list_anchors(SCOPE, changed.id)
    assert current.id == initial.id
    assert current.version == 2
    assert current.status == "synced"
    assert len(anchors) == 1


def test_get_doc_coverage_counts_only_required_documented():
    store = InMemoryStore()
    service = DocsSyncService(store)
    required = service.index_symbol(
        SCOPE, "agent", "corr", "sym-req", symbol_payload(path="auth.a", doc_required=True)
    )
    service.index_symbol(
        SCOPE,
        "agent",
        "corr",
        "sym-opt",
        symbol_payload(path="auth.b", body="def b():\n    return 1\n", doc_required=False),
    )
    document = service.index_document(
        SCOPE,
        "agent",
        "corr",
        "doc-cov",
        {"path": "docs/a.md", "frontmatter": frontmatter(symbols=["auth.a"]), "body": "A"},
    )
    service.register_anchor(
        SCOPE,
        "agent",
        "corr",
        "anchor-cov",
        {"doc_id": document.id, "symbol_id": required.id, "recorded_hash": required.body_hash},
    )
    coverage = service.get_doc_coverage(SCOPE)
    assert coverage["required_symbols"] == 1
    assert coverage["documented_symbols"] == 1
    assert coverage["coverage_ratio"] == 1.0
    assert coverage.get("empty_reason") is None


def test_missing_doc_bloom_frontmatter_and_draft_approval():
    store = InMemoryStore()
    service = DocsSyncService(store)

    symbol = service.index_symbol(SCOPE, "agent", "corr", "sym-1", symbol_payload(tags=["api", "route"], kind="route"))
    assert service.find_missing_docs(SCOPE)[0]["symbol"]["id"] == symbol.id

    bloom = service.bloom_lookup(SCOPE, symbol.id)
    assert bloom["definite_no_doc"] is True
    assert bloom["maybe_documented"] is False

    errors = service.validate_frontmatter({"title": "x"})
    assert "missing required field: doc_id" in errors

    findings = service.detect_drift(SCOPE, "agent", "corr", "drift-missing", [symbol.id])
    assert findings[0].drift_type.value == "missing_doc"
    assert findings[0].severity.value == "high"

    draft = service.create_draft(
        SCOPE,
        "agent",
        "corr",
        "draft-1",
        {"symbol_id": symbol.id, "title": "Route docs", "body": "Describe the route.", "finding_id": findings[0].id},
    )
    approved = service.approve_draft(SCOPE, "agent", "corr", "approve-1", draft.id)
    assert approved.state.value == "approved"
    assert store.outbox()[-1]["event_type"] == "DocumentationDraftApproved"


def test_normalization_ignores_formatting_noise():
    left = normalize_source("def login():\n    return True  # note\n")
    right = normalize_source("def login():\n\n    return    True\n")
    assert left == right
    assert digest(left) == digest(right)


def test_in_memory_store_scope_idempotency_and_not_found():
    store = InMemoryStore()
    service = DocsSyncService(store)
    symbol = service.index_symbol(SCOPE, "agent", "corr", "sym-1", symbol_payload())
    loaded = store.get_symbol(symbol.id, SCOPE)
    assert loaded.symbol_path == "auth.login"
    assert store.list_symbols(Scope("other", "w", "p")) == []

    store.remember(SCOPE, "index_symbol", "dup", {"body": "a"}, symbol.id)
    assert store.idempotent(SCOPE, "index_symbol", "dup", {"body": "a"}) == symbol.id
    try:
        store.idempotent(SCOPE, "index_symbol", "dup", {"body": "b"})
        raise AssertionError("expected idempotency conflict")
    except ConflictError:
        pass

    try:
        store.get_symbol("missing", SCOPE)
        raise AssertionError("expected not found")
    except NotFoundError:
        pass

    event = store.outbox()[0]
    assert event["event_type"] == "SymbolIndexed"
    assert event["event_version"] == 1
    assert event["producer"] == "docs-sync-service"
    assert event["tenant_id"] == "t"
    assert event["project_id"] == "p"


def test_api_drift_ci_gate_and_coverage_smoke():
    store = InMemoryStore()
    client = ApiClient(app(DocsSyncService(store)))
    symbol = client.post(
        "/api/v1/projects/p/symbols",
        headers={**H, "Idempotency-Key": "api-sym"},
        json=symbol_payload(body="def login():\n    return True\n"),
    )
    assert symbol.status_code == 200
    symbol_id = symbol.json()["symbol"]["id"]
    body_hash = symbol.json()["symbol"]["body_hash"]

    document = client.post(
        "/api/v1/projects/p/documents",
        headers={**H, "Idempotency-Key": "api-doc"},
        json={"path": "docs/login.md", "frontmatter": frontmatter(), "body": "Login."},
    )
    assert document.status_code == 200
    doc_id = document.json()["document"]["id"]

    anchor = client.post(
        "/api/v1/projects/p/anchors",
        headers={**H, "Idempotency-Key": "api-anchor"},
        json={"doc_id": doc_id, "symbol_id": symbol_id, "recorded_hash": body_hash},
    )
    assert anchor.status_code == 200

    changed = client.post(
        "/api/v1/projects/p/symbols",
        headers={**H, "Idempotency-Key": "api-sym-2"},
        json=symbol_payload(body="def login():\n    return True and mfa()\n"),
    )
    changed_id = changed.json()["symbol"]["id"]
    drift = client.post(
        "/api/v1/projects/p/drift-detections",
        headers={**H, "Idempotency-Key": "api-drift"},
        json={"symbol_ids": [changed_id]},
    )
    assert drift.status_code == 200
    assert drift.json()["findings"][0]["issue_ref"].startswith("issue:")
    assert drift.json()["findings"][0]["task_ref"].startswith("task:docs-agent:")

    gate = client.post("/api/v1/projects/p/ci-gate", headers=H, json={})
    assert gate.json()["gate"]["decision"] == "fail"
    coverage = client.get("/api/v1/projects/p/coverage", headers=H)
    assert coverage.json()["coverage"]["documented_symbols"] == 1
    assert client.get("/api/v1/projects/p/symbols/" + symbol_id + "/docs", headers=H).json()["items"][0]["id"] == doc_id
    assert client.post("/api/v1/projects/p/symbols", json=symbol_payload()).status_code == 400


def test_unregister_symbol_removes_registry_row_and_anchors():
    store = InMemoryStore()
    service = DocsSyncService(store)
    symbol = service.index_symbol(SCOPE, "agent", "corr", "sym-del", symbol_payload())
    document = service.index_document(
        SCOPE,
        "agent",
        "corr",
        "doc-del",
        {"path": "docs/login.md", "frontmatter": frontmatter(), "body": "Login flow."},
    )
    service.register_anchor(
        SCOPE,
        "agent",
        "corr",
        "anchor-del",
        {"doc_id": document.id, "symbol_id": symbol.id, "recorded_hash": symbol.body_hash},
    )
    assert store.list_anchors(SCOPE, symbol.id)
    service.unregister_symbol(SCOPE, symbol.id)
    assert store.list_symbols(SCOPE) == []
    assert store.list_anchors(SCOPE, symbol.id) == []


def test_api_contract_routes_are_registered():
    routes = {route.path for route in app(DocsSyncService(InMemoryStore())).routes}
    assert "/api/v1/projects/{project_id}/symbols" in routes
    assert "/api/v1/projects/{project_id}/documents" in routes
    assert "/api/v1/projects/{project_id}/documents:validate-frontmatter" in routes
    assert "/api/v1/projects/{project_id}/anchors" in routes
    assert "/api/v1/projects/{project_id}/drift-detections" in routes
    assert "/api/v1/projects/{project_id}/drift-findings" in routes
    assert "/api/v1/projects/{project_id}/symbols/{symbol_id}/docs" in routes
    assert "/api/v1/projects/{project_id}/coverage" in routes
    assert "/api/v1/projects/{project_id}/missing-docs" in routes
    assert "/api/v1/projects/{project_id}/impact:explain" in routes
    assert "/api/v1/projects/{project_id}/bloom-lookups" in routes
    assert "/api/v1/projects/{project_id}/drafts" in routes
    assert "/api/v1/projects/{project_id}/drafts/{draft_id}:approve" in routes
    assert "/api/v1/projects/{project_id}/ci-gate" in routes
