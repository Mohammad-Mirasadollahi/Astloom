"""Polyglot project profile — related multi-language repositories."""

from __future__ import annotations

from code_graph_service.api import app
from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore

SCOPE = Scope("t", "w", "related-langs")

RUST_HELPER = """
pub fn check_password(password: &str) -> bool {
    password.len() > 8
}
"""

PYTHON_CALLER = """
def login(user, password):
    return check_password(password)
"""

GO_ISOLATED = """
package tools

func Ping() string { return "ok" }
"""


def test_polyglot_profile_detects_related_languages():
    store = InMemoryStore()
    service = CodeGraphService(store)
    service.ingest_file(
        SCOPE,
        "agent",
        "c1",
        "idem-rs",
        {"file_path": "src/auth.rs", "source": RUST_HELPER, "language": "rust"},
    )
    service.ingest_file(
        SCOPE,
        "agent",
        "c2",
        "idem-py",
        {"file_path": "src/login.py", "source": PYTHON_CALLER, "language": "python"},
    )
    profile = service.get_polyglot_profile(SCOPE)
    assert profile.is_polyglot is True
    assert set(profile.languages) == {"python", "rust"}
    assert profile.cross_language_edge_count >= 1
    assert profile.relatedness == "polyglot_fully_related"
    assert any(
        {link.source_language, link.target_language} == {"python", "rust"}
        for link in profile.language_links
    )
    assert "related" in profile.summary.lower() or "Polyglot related" in profile.summary

    events = store.outbox()
    assert any(event["event_type"] == "ProjectLanguageProfileUpdated" for event in events)
    ingested = [event for event in events if event["event_type"] == "FileIngested"][-1]
    assert ingested["payload"]["polyglot"]["is_polyglot"] is True


def test_polyglot_partial_relatedness_with_isolated_language():
    store = InMemoryStore()
    service = CodeGraphService(store)
    service.ingest_file(
        SCOPE,
        "agent",
        "c1",
        "idem-rs",
        {"file_path": "src/auth.rs", "source": RUST_HELPER, "language": "rust"},
    )
    service.ingest_file(
        SCOPE,
        "agent",
        "c2",
        "idem-py",
        {"file_path": "src/login.py", "source": PYTHON_CALLER, "language": "python"},
    )
    service.ingest_file(
        SCOPE,
        "agent",
        "c3",
        "idem-go",
        {"file_path": "tools/ping.go", "source": GO_ISOLATED, "language": "go"},
    )
    profile = service.get_polyglot_profile(SCOPE)
    assert profile.is_polyglot is True
    assert set(profile.languages) == {"go", "python", "rust"}
    assert profile.relatedness == "polyglot_partially_related"
    assert ["python", "rust"] in profile.related_language_groups or any(
        set(group) == {"python", "rust"} for group in profile.related_language_groups
    )


def test_generation_context_includes_polyglot_profile_and_api_route():
    store = InMemoryStore()
    service = CodeGraphService(store)
    service.ingest_file(
        SCOPE,
        "agent",
        "c1",
        "idem-rs",
        {"file_path": "src/auth.rs", "source": RUST_HELPER, "language": "rust"},
    )
    service.ingest_file(
        SCOPE,
        "agent",
        "c2",
        "idem-py",
        {"file_path": "src/login.py", "source": PYTHON_CALLER, "language": "python"},
    )
    login_id = f"sym:{SCOPE.project_id}:src.login.login"
    context = service.build_generation_context(SCOPE, login_id)
    assert context["polyglot"]["is_polyglot"] is True
    assert "polyglot" in context["prompt_context"].lower()

    routes = {route.path for route in app(CodeGraphService(InMemoryStore())).routes}
    assert "/api/v1/projects/{project_id}/graph/language-profile" in routes
