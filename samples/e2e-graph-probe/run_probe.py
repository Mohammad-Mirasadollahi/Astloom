#!/usr/bin/env python3
"""Real probe: ingest samples/e2e-graph-probe and assert graph + optional LLM docs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = Path(__file__).resolve().parent
os.chdir(ROOT)

# Ensure packages importable when run from repo root.
_paths = [
    ROOT / "backend" / "packages",
    ROOT / "backend" / "services" / "code-graph-service" / "src",
    ROOT / "backend" / "services" / "mcp-gateway-service" / "src",
    ROOT / "backend" / "services" / "core-data-service" / "src",
    ROOT / "backend" / "services" / "memory-service" / "src",
    ROOT / "backend" / "services" / "docs-sync-service" / "src",
    ROOT / "backend" / "services" / "common-context-service" / "src",
]
for path in _paths:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from code_graph_service.bootstrap import Settings, build_service
from code_graph_service.core import Scope
from code_graph_service.domain.enums import SymbolKind
from llm_gateway import ChatMessage, CompletionRequest, LiteLlmGateway, LlmGatewaySettings
from mcp_gateway_service.backends import PlatformBackends, dispatch_capability
from mcp_gateway_service.store_factory import build_stores


EXPECTED_FUNCS = {"hash_password", "verify_password", "login", "require_login"}
EXPECTED_CALLS = {
    ("verify_password", "hash_password"),
    ("login", "verify_password"),
    ("require_login", "login"),
}


def main() -> int:
    # Docs via LiteLLM ON for this probe (uses .env OpenRouter settings).
    os.environ.setdefault("ASTLOOM_MCP_GRAPH_MODE", "neo4j")
    os.environ["ASTLOOM_LITELLM_DOCS_ENABLED"] = os.environ.get(
        "ASTLOOM_LITELLM_DOCS_ENABLED", "true"
    )

    settings = Settings.from_environment()
    if settings.store_backend != "neo4j":
        print("FAIL: ASTLOOM_CODE_GRAPH_STORE must be neo4j for this probe")
        return 1

    scope = Scope("t-probe", "w-probe", "p-graph-probe")
    svc = build_service(settings)
    report: dict = {"steps": []}

    def step(name: str, ok: bool, detail: object = None) -> None:
        report["steps"].append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail is not None else ""))

    try:
        result = svc.ingest_repo(
            scope,
            "probe",
            str(uuid4()),
            f"probe-repo:{uuid4()}",
            {
                "root_path": str(SAMPLE / "src"),
                "include_extensions": [".py"],
                "max_files": 20,
                "include_outcomes": True,
            },
        )
        step(
            "ingest_repo",
            result.files_ingested >= 2 and result.files_failed == 0,
            {
                "ingested": result.files_ingested,
                "symbols": result.symbols_indexed,
                "documented": result.symbols_documented,
                "edges": result.edges_written,
            },
        )

        symbols = [
            s
            for s in svc.store.list_symbols(scope)
            if s.kind not in {SymbolKind.FILE, SymbolKind.UNRESOLVED, SymbolKind.IMPORT}
            and (
                str(s.file_path).replace("\\", "/").startswith("src/")
                or str(s.file_path).replace("\\", "/") in {"auth.py", "service.py"}
                or str(s.file_path).replace("\\", "/").endswith("/auth.py")
                or str(s.file_path).replace("\\", "/").endswith("/service.py")
            )
        ]
        by_name = {s.name: s for s in symbols}
        found = set(by_name) & EXPECTED_FUNCS
        step("symbols_present", found == EXPECTED_FUNCS, sorted(found))

        # Build name→id and inspect CALLS edges.
        name_of = {s.id: s.name for s in symbols}
        id_set = set(name_of)
        call_pairs: set[tuple[str, str]] = set()
        for edge in svc.store.list_edges(scope):
            if edge.rel_type != "CALLS":
                continue
            if edge.source_id not in id_set or edge.target_id not in id_set:
                continue
            src = name_of.get(edge.source_id)
            dst = name_of.get(edge.target_id)
            if src and dst:
                call_pairs.add((src, dst))
        missing_calls = EXPECTED_CALLS - call_pairs
        step("calls_edges", not missing_calls, {"found": sorted(call_pairs & EXPECTED_CALLS), "missing": sorted(missing_calls)})

        documented = [s.name for s in symbols if (s.ai_documentation or "").strip()]
        step(
            "ai_documentation_populated",
            len(documented) >= 2,
            {"documented_count": len(documented), "sample": documented[:4]},
        )

        hits = svc.semantic_search(scope, "verify password hash login", top_k=5)
        hit_names = {h["symbol"]["name"] for h in hits}
        step("semantic_search", bool(hit_names & EXPECTED_FUNCS), sorted(hit_names))

        seed = by_name.get("require_login") or by_name.get("login")
        if seed is not None:
            impact = svc.impact_analysis(scope, seed.id, direction="both", max_depth=3)
            step(
                "directed_impact",
                len(impact.get("blast") or []) >= 1 or len(impact.get("edges") or []) >= 1,
                f"blast={len(impact.get('blast') or [])} edges={len(impact.get('edges') or [])}",
            )
            callers = svc.callers(scope, seed.id, top_k=20)
            step("callers", "callers" in callers and "escalate_hint" in callers, f"n={callers.get('caller_count')}")
            community = svc.community_of_symbol(scope, seed.id, member_limit=20)
            step("community", "community_id" in community, f"id={community.get('community_id')}")
            ctx = svc.build_generation_context(scope, seed.id, max_symbols=8)
            step("generation_context", ctx.get("symbol_count", 0) >= 2, f"symbols={ctx.get('symbol_count')}")
        else:
            step("directed_impact", False, "seed missing")
            step("callers", False, "seed missing")
            step("community", False, "seed missing")
            step("generation_context", False, "seed missing")
    finally:
        closer = getattr(svc.store, "close", None)
        if callable(closer):
            closer()

    # MCP against same Neo4j scope
    backends = PlatformBackends(
        build_stores(
            {
                **{
                    k: v
                    for k, v in os.environ.items()
                    if k.startswith("ASTLOOM_") or k in {"OPENROUTER_API_KEY", "LITELLM_API_KEY"}
                },
                "ASTLOOM_MCP_STORE_MODE": "memory",
                "ASTLOOM_MCP_GRAPH_MODE": "neo4j",
            }
        )
    )
    try:
        mcp_scope = {
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
        }
        search = dispatch_capability(
            backends,
            "code_graph.search",
            {"query": "login password", "top_k": 5},
            scope=mcp_scope,
            usage_profile="programming-cursor-mcp",
            correlation_id=str(uuid4()),
        )
        step(
            "mcp_search",
            search.get("graph_mode") == "neo4j" and bool(search.get("symbols")),
            f"mode={search.get('graph_mode')} hits={len(search.get('symbols') or [])}",
        )
        got = dispatch_capability(
            backends,
            "code_graph.get_symbol",
            {"qualified_name": "login"},
            scope=mcp_scope,
            usage_profile="programming-cursor-mcp",
            correlation_id=str(uuid4()),
        )
        step("mcp_get_login", got.get("symbol", {}).get("name") == "login", got.get("symbol", {}).get("qualified_name"))
        impact = dispatch_capability(
            backends,
            "code_graph.impact",
            {"symbol_id": got["symbol"]["id"], "max_depth": 3, "direction": "both"},
            scope=mcp_scope,
            usage_profile="programming-cursor-mcp",
            correlation_id=str(uuid4()),
        )
        step(
            "mcp_impact",
            len(impact.get("blast") or []) >= 1 or len(impact.get("edges") or []) >= 1,
            f"blast={len(impact.get('blast') or [])} edges={len(impact.get('edges') or [])}",
        )
        callers = dispatch_capability(
            backends,
            "code_graph.callers",
            {"symbol_id": got["symbol"]["id"], "top_k": 10},
            scope=mcp_scope,
            usage_profile="programming-cursor-mcp",
            correlation_id=str(uuid4()),
        )
        step("mcp_callers", "callers" in callers and "escalate_hint" in callers, f"n={callers.get('caller_count')}")
        community = dispatch_capability(
            backends,
            "code_graph.community",
            {"symbol_id": got["symbol"]["id"]},
            scope=mcp_scope,
            usage_profile="programming-cursor-mcp",
            correlation_id=str(uuid4()),
        )
        step("mcp_community", "community_id" in community, f"id={community.get('community_id')}")
    finally:
        backends.close()

    # LiteLLM connectivity (not graph-specific)
    gw = LiteLlmGateway(LlmGatewaySettings.from_environment())
    comp = gw.complete(
        CompletionRequest(
            messages=(
                ChatMessage(role="system", content="One token only."),
                ChatMessage(role="user", content="Reply with exactly: PROBE_OK"),
            ),
            temperature=0,
        )
    )
    step("llm_complete", "PROBE_OK" in (comp.content or "").upper(), (comp.content or "")[:80])

    failed = [s for s in report["steps"] if not s["ok"]]
    print("\n=== PROBE SUMMARY ===")
    print(json.dumps({"passed": len(report["steps"]) - len(failed), "failed": len(failed), "total": len(report["steps"])}, indent=2))
    if failed:
        print(json.dumps(failed, indent=2))
        return 1
    print("GRAPH_AND_LLM_LINK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
