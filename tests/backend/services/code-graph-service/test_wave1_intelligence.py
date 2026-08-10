"""Wave 1 domain unit tests: routes, tests links, risk, explore, flows."""

from __future__ import annotations

from code_graph_service.domain.explore import (
    ExploreSymbol,
    build_explore_pack,
    extract_query_terms,
)
from code_graph_service.domain.flows import FlowNode, detect_entry_points, trace_flow
from code_graph_service.domain.framework_routes import extract_routes
from code_graph_service.domain.risk import RiskFactors, compute_risk_score, risk_level
from code_graph_service.domain.test_links import is_test_path, suggest_test_links
from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore


def test_extract_fastapi_routes():
    src = '''
from fastapi import APIRouter
router = APIRouter()

@router.get("/users/{id}")
async def get_user(id: str):
    return id

@router.post("/users")
def create_user():
    return {}
'''
    routes = extract_routes(src, language="python", file_path="app/api.py")
    assert len(routes) >= 2
    paths = {r.path for r in routes}
    assert "/users/{id}" in paths
    assert any(r.handler_name == "get_user" for r in routes)


def test_extract_express_routes():
    src = '''
app.get("/health", healthCheck);
router.post('/login', loginHandler);
'''
    routes = extract_routes(src, language="javascript")
    assert len(routes) == 2
    assert routes[0].framework == "express"


def test_test_path_and_links():
    assert is_test_path("tests/test_auth.py")
    assert is_test_path("src/auth.test.ts")
    assert not is_test_path("src/contest.py")
    links = suggest_test_links(
        [
            ("pkg.auth.login", "login", "src/auth.py"),
            ("pkg.tests.test_auth", "test_login", "tests/test_auth.py"),
        ]
    )
    assert any(l.production_name == "pkg.auth.login" for l in links)


def test_risk_score_security_and_untested():
    score = compute_risk_score(
        RiskFactors(
            name="login",
            qualified_name="auth.login",
            test_count=0,
            caller_count=10,
            flow_criticalities=(0.2, 0.1),
        )
    )
    assert score >= 0.5
    assert risk_level(score) in {"medium", "high", "critical"}


def test_explore_skeletonizes_siblings_under_budget():
    syms = [
        ExploreSymbol(
            id=f"i{i}",
            name=f"Foo{i}Interceptor",
            qualified_name=f"pkg.Foo{i}Interceptor",
            file_path=f"a{i}.py",
            signature=f"class Foo{i}Interceptor:",
            body="x" * 500,
            kind="class",
            score=1.0,
        )
        for i in range(4)
    ]
    # Mark first on spine
    pack = build_explore_pack(
        "interceptor chain",
        syms,
        call_path_ids=["i0"],
        budget_chars=2000,
    )
    renders = [s["render"] for sec in pack.sections for s in sec.symbols]
    assert "full" in renders
    assert "signature" in renders or pack.used_chars <= 2000


def test_flow_trace_and_entry():
    nodes = {
        "main": FlowNode("main", "main", "mod.main", "a.py"),
        "login": FlowNode("login", "login", "mod.login", "a.py"),
        "check": FlowNode("check", "check_password", "mod.check_password", "a.py"),
    }
    edges = [("main", "login"), ("login", "check")]
    entries = detect_entry_points(nodes.values(), edges)
    assert any(e.id == "main" for e in entries)
    flow = trace_flow(nodes["main"], nodes, {"main": ["login"], "login": ["check"]})
    assert flow.path_ids[0] == "main"
    assert "check" in flow.path_ids
    assert 0.0 <= flow.criticality <= 1.0


def test_explore_and_detect_changes_via_service():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "p")
    auth = '''
def check_password(password):
    return len(password) > 8

def login(user, password):
    return check_password(password)
'''
    tests = '''
def test_login():
    assert True
'''
    routes = '''
from fastapi import APIRouter
router = APIRouter()

@router.post("/login")
def login(user, password):
    return True
'''
    svc.ingest_file(scope, "a", "c1", "k1", {"file_path": "src/auth.py", "source": auth, "language": "python"})
    svc.ingest_file(scope, "a", "c2", "k2", {"file_path": "tests/test_auth.py", "source": tests, "language": "python"})
    svc.ingest_file(scope, "a", "c3", "k3", {"file_path": "src/api.py", "source": routes, "language": "python"})

    edges = store.list_edges(scope)
    assert any(e.rel_type == "ROUTES_TO" for e in edges)
    assert any(e.rel_type == "TESTED_BY" for e in edges)

    pack = svc.explore(scope, "how does login work")
    assert pack["sections"]
    assert pack["budget_chars"] > 0
    assert any(sec.get("file_path") for sec in pack["sections"])
    assert any(s.get("file_path") for sec in pack["sections"] for s in sec.get("symbols") or [])

    report = svc.detect_changes(scope, ["src/auth.py"])
    assert "risk_score" in report
    assert report["changed_functions"]
    assert "summary" in report


def test_extract_query_terms_filters_stopwords():
    terms = extract_query_terms("How does AuthService login flow work?")
    lowered = {t.lower() for t in terms}
    assert "authservice" in lowered or "AuthService" in terms
    assert "login" in lowered
    assert "how" not in lowered
    assert "does" not in lowered
