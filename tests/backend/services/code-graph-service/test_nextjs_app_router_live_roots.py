"""Next.js App Router must not mark live page trees safe_to_delete."""

from __future__ import annotations

from code_graph_service.domain.enums import CallConfidence, DocStatus, RelType, SymbolKind
from code_graph_service.domain.models import GraphEdge, GraphSymbol, Scope
from code_graph_service.domain.parsers.typescript import parse_typescript_source
from code_graph_service.domain.unused_candidates import find_unused_candidates

SCOPE = Scope("t", "w", "nextjs_live")


def _sym(
    sid: str,
    name: str,
    *,
    kind: SymbolKind = SymbolKind.FUNCTION,
    path: str,
    visibility: str = "public",
    qn: str | None = None,
) -> GraphSymbol:
    return GraphSymbol(
        id=sid,
        scope=SCOPE,
        kind=kind,
        file_path=path,
        name=name,
        qualified_name=qn or f"{path.replace('/', '.').rsplit('.', 1)[0]}.{name}",
        signature=f"function {name}()",
        body="return null",
        hash_value="h",
        ai_documentation="",
        doc_status=DocStatus.UNCHANGED,
        embedding=[],
        visibility=visibility,
    )


def test_parse_export_default_from_creates_import():
    src = 'export { default } from "../executive/ExecutiveOverviewPage";\n'
    parsed = parse_typescript_source("frontend/app/dashboard/overview/page.tsx", src)
    imports = [s for s in parsed.symbols if s.kind == SymbolKind.IMPORT]
    assert imports, "re-export must emit IMPORT so IMPORTS edges can keep the target live"
    assert any("ExecutiveOverviewPage" in (i.imports or [""])[0] for i in imports) or any(
        "ExecutiveOverviewPage" in x for i in imports for x in i.imports
    )


def test_parse_jsx_component_usage_as_call():
    src = """
import { ValueFunnelHero } from "./ValueFunnelHero";
export default function Page() {
  return <ValueFunnelHero title="x" />;
}
"""
    parsed = parse_typescript_source("frontend/app/dashboard/overview/page.tsx", src)
    page = next(s for s in parsed.symbols if s.name == "Page")
    assert "ValueFunnelHero" in page.calls


def test_app_router_reexport_target_not_safe_to_delete():
    """Fixture: overview/page.tsx only re-exports ExecutiveOverviewPage — must stay live."""
    page_file = _sym(
        "file:overview",
        "page.tsx",
        kind=SymbolKind.FILE,
        path="frontend/app/dashboard/overview/page.tsx",
    )
    overview = _sym(
        "s:overview",
        "ExecutiveOverviewPage",
        kind=SymbolKind.FUNCTION,
        path="frontend/app/dashboard/executive/ExecutiveOverviewPage.tsx",
        qn="frontend.app.dashboard.executive.ExecutiveOverviewPage.ExecutiveOverviewPage",
    )
    hero = _sym(
        "s:hero",
        "ValueFunnelHero",
        kind=SymbolKind.FUNCTION,
        path="frontend/app/dashboard/executive/components/ValueFunnelHero.tsx",
        qn="frontend.app.dashboard.executive.components.ValueFunnelHero.ValueFunnelHero",
    )
    # Re-export modeled as FILE IMPORTS overview (what ingest must emit after parser fix).
    edges = [
        GraphEdge(
            id="e1",
            scope=SCOPE,
            rel_type=RelType.IMPORTS.value,
            source_id=page_file.id,
            target_id=overview.id,
            confidence=CallConfidence.EXACT,
        ),
        GraphEdge(
            id="e2",
            scope=SCOPE,
            rel_type=RelType.IMPORTS.value,
            source_id=overview.id,
            target_id=hero.id,
            confidence=CallConfidence.EXACT,
        ),
    ]
    out = find_unused_candidates(
        [page_file, overview, hero],
        edges,
        scope_mode="changed_symbols",
        anchor_symbols=["ExecutiveOverviewPage", "ValueFunnelHero"],
        min_confidence=0.8,
    )
    ids = {r.get("symbol_id") for r in out["candidates"]}
    assert overview.id not in ids, out["candidates"]
    assert hero.id not in ids, out["candidates"]
    assert not any(r.get("safe_to_delete") for r in out["candidates"] if r.get("symbol_id") in {overview.id, hero.id})


def test_app_router_page_default_export_is_live_root_without_importers():
    """page.tsx default export with zero inbound must not be safe_to_delete."""
    page = _sym(
        "s:page",
        "Page",
        path="frontend/app/dashboard/overview/page.tsx",
        qn="frontend.app.dashboard.overview.page.Page",
    )
    out = find_unused_candidates(
        [page],
        [],
        scope_mode="changed_symbols",
        anchor_symbols=["Page"],
        min_confidence=0.5,
        include_uncertain=True,
    )
    # May appear as uncertain/low score, but never safe_to_delete.
    for row in out["candidates"] + out["skipped_uncertain"]:
        if row.get("symbol_id") == page.id:
            assert row.get("safe_to_delete") is False
            assert "entrypoint" in (row.get("blockers") or []) or row.get("score", 1) < 0.8
            break
    else:
        # Not listed at all is also OK (treated as live / filtered).
        pass


def test_symbol_safe_to_delete_demoted_when_file_verdict_blocks():
    """Symbols on App Router page.tsx must not stay safe_to_delete."""
    page_fn = _sym(
        "s:pageFn",
        "PageHelper",
        path="frontend/app/dashboard/overview/page.tsx",
        visibility="private",
        qn="frontend.app.dashboard.overview.page.PageHelper",
    )
    out = find_unused_candidates(
        [page_fn],
        [],
        scope_mode="project_scan",
        min_confidence=0.5,
        include_uncertain=True,
    )
    for r in out["candidates"]:
        if r.get("symbol_id") == page_fn.id:
            raise AssertionError("page.tsx symbols must not be safe_to_delete")
    rows = [r for r in out["skipped_uncertain"] if r.get("symbol_id") == page_fn.id]
    if rows:
        assert rows[0].get("safe_to_delete") is False
        assert "file_verdict_blocks_delete" in (rows[0].get("blockers") or []) or "entrypoint" in (
            rows[0].get("blockers") or []
        )


def test_ingest_app_router_reexport_keeps_tree_live(tmp_path):
    """Ingest-shaped graph: FILE IMPORTS + JSX CALLS must keep UI tree live."""
    from code_graph_service.application.service import CodeGraphService
    from code_graph_service.testing import InMemoryStore

    page = 'export { default } from "../executive/ExecutiveOverviewPage";\n'
    overview = (
        'import { ValueFunnelHero } from "./components/ValueFunnelHero";\n'
        "export default function ExecutiveOverviewPage() {\n"
        '  return <ValueFunnelHero title="x" />;\n'
        "}\n"
    )
    hero = (
        "export function ValueFunnelHero({ title }: { title: string }) {\n"
        "  return <section>{title}</section>;\n"
        "}\n"
    )
    dead = "export function deadOverviewHelper() { return 1; }\n"
    store = InMemoryStore()
    svc = CodeGraphService(store)
    files = [
        ("frontend/app/dashboard/overview/page.tsx", page),
        ("frontend/app/dashboard/executive/ExecutiveOverviewPage.tsx", overview),
        ("frontend/app/dashboard/executive/components/ValueFunnelHero.tsx", hero),
        ("frontend/app/dashboard/executive/deadHelper.ts", dead),
    ]
    for path, src in files:
        svc.ingest_file(
            SCOPE,
            "actor",
            "c",
            f"k:{path}",
            {"file_path": path, "language": "typescript", "source": src, "skip_embeddings": True},
        )
    for path, src in files:
        svc.ingest_file(
            SCOPE,
            "actor",
            "c2",
            f"k2:{path}",
            {"file_path": path, "language": "typescript", "source": src, "skip_embeddings": True},
        )
    out = svc.unused_candidates(
        SCOPE,
        scope_mode="project_scan",
        path_prefix="frontend/app/dashboard",
        min_confidence=0.5,
        include_uncertain=True,
    )
    safe = [r for r in (out.get("candidates") or []) if r.get("safe_to_delete")]
    assert not any("ExecutiveOverviewPage" in str(r.get("symbol")) for r in safe), safe
    assert not any("ValueFunnelHero" in str(r.get("symbol")) for r in safe), safe
    assert any(
        "deadOverviewHelper" in str(r.get("symbol"))
        for r in (out.get("candidates") or []) + (out.get("skipped_uncertain") or [])
    )


def test_disk_missing_symbol_not_safe_to_delete(tmp_path):
    """Stale graph symbols deleted on disk must not remain safe_to_delete."""
    import os
    import time

    from code_graph_service.domain.unused_candidates.disk_presence import (
        demote_rows_missing_on_disk,
    )

    root = tmp_path
    (root / "pkg").mkdir()
    target = root / "pkg" / "gone.py"
    target.write_text("# empty after delete\n", encoding="utf-8")
    old = time.time() - 60 * 60 * 24 * 400
    os.utime(target, (old, old))
    row = {
        "symbol": "formatHealthHint",
        "symbol_id": "s:gone",
        "path": "pkg/gone.py",
        "finding_kind": "unused_symbol",
        "score": 0.8,
        "safe_to_delete": True,
        "blockers": [],
    }
    cands, skipped = demote_rows_missing_on_disk(
        [row], [], repo_root=str(root), include_uncertain=True
    )
    assert not cands
    assert skipped and "disk_symbol_absent" in (skipped[0].get("blockers") or [])
