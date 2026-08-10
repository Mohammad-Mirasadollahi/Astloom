"""Unit tests for stale-documentation candidates (doc 78)."""

from __future__ import annotations

from docs_sync_service.domain.stale_docs import find_stale_doc_candidates
from docs_sync_service.domain.stale_docs.scoring import ScoreInput, score_candidate
from docs_sync_service.enums import DocumentState
from docs_sync_service.models import CodeSymbol, DocAnchor, Document, Scope

SCOPE = Scope("t", "w", "p")


def _sym(
    sid: str,
    path: str = "pkg/mod.py",
    symbol_path: str = "pkg.mod.fn",
    *,
    body_hash: str = "hash-a",
    doc_required: bool = False,
) -> CodeSymbol:
    return CodeSymbol(
        id=sid,
        scope=SCOPE,
        actor_id="a",
        correlation_id="c",
        repo="r",
        file_path=path,
        symbol_path=symbol_path,
        kind="function",
        signature_hash="s",
        body_hash=body_hash,
        doc_required=doc_required,
        tags=[],
        created_at="2020-01-01T00:00:00+00:00",
        updated_at="2020-01-01T00:00:00+00:00",
    )


def _doc(
    did: str,
    path: str,
    *,
    linked: list[str] | None = None,
    fm: dict | None = None,
    updated_at: str = "2020-01-01T00:00:00+00:00",
    state: DocumentState = DocumentState.INDEXED,
) -> Document:
    frontmatter = {
        "doc_id": f"as.doc.test.{did}",
        "title": did,
        "owner": "test",
        "status": "active",
        "schema_version": "1.0",
        "linked_symbols": linked or [],
        "decision_refs": [],
        "concern_lane": "product",
        "lifecycle_lane": "current",
        "authority": "informative",
        "updated_at": "2020-01-01",
        **(fm or {}),
    }
    return Document(
        id=did,
        scope=SCOPE,
        actor_id="a",
        correlation_id="c",
        path=path,
        title=did,
        owner="test",
        state=state,
        schema_version="1.0",
        linked_symbols=list(linked or []),
        decision_refs=[],
        frontmatter=frontmatter,
        body="# hi\n",
        created_at=updated_at,
        updated_at=updated_at,
    )


def test_orphan_doc_project_scan():
    doc = _doc("orphan", "docs/example/orphan.md", linked=[])
    out = find_stale_doc_candidates(
        [doc],
        [],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.5,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert rows
    assert rows[0]["finding_kind"] == "orphan_doc"
    assert out["kpi_hints"]["stale_docs_candidates_resolved"] == 0


def test_ghost_link_missing_symbol():
    doc = _doc("ghost", "docs/example/ghost.md", linked=["pkg.mod.gone"])
    out = find_stale_doc_candidates(
        [doc],
        [],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.5,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert any(r["finding_kind"] == "ghost_link" for r in rows)
    assert any(
        e.get("kind") == "linked_symbol_missing"
        for r in rows
        for e in (r.get("evidence") or [])
    )


def test_stale_anchor_prefers_update():
    sym = _sym("s1", symbol_path="pkg.mod.live", body_hash="new")
    doc = _doc("stale", "docs/example/stale.md", linked=["pkg.mod.live"])
    anc = DocAnchor(
        "a1",
        SCOPE,
        doc.id,
        sym.id,
        "old",
        "stale",
        "2020-01-01T00:00:00+00:00",
        "2020-01-01T00:00:00+00:00",
    )
    out = find_stale_doc_candidates(
        [doc],
        [sym],
        [anc],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    stale = [r for r in rows if r["finding_kind"] == "stale_anchor"]
    assert stale
    assert stale[0]["safe_to_update"] is True
    assert stale[0]["safe_to_delete"] is not True


def test_path_prefix_filters():
    a = _doc("a", "docs/keep/a.md", linked=[])
    b = _doc("b", "docs/other/b.md", linked=[])
    out = find_stale_doc_candidates(
        [a, b],
        [],
        [],
        scope_mode="project_scan",
        path_prefix="docs/keep",
        include_uncertain=True,
        min_confidence=0.0,
    )
    assert out["path_prefix"] == "docs/keep"
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert rows
    assert all(str(r.get("path") or "").startswith("docs/keep") for r in rows)


def test_superseded_retrieval_risk_historical():
    doc = _doc(
        "old",
        "docs/example/old.md",
        linked=["pkg.mod.live"],
        fm={"lifecycle_lane": "historical", "superseded_by": "as.doc.test.newer"},
    )
    sym = _sym("s1", symbol_path="pkg.mod.live")
    out = find_stale_doc_candidates(
        [doc],
        [sym],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert any(r["finding_kind"] == "superseded_retrieval_risk" for r in rows)


def test_normative_current_blocks_delete():
    scored = score_candidate(
        ScoreInput(
            finding_kind="orphan_doc",
            authority="normative",
            lifecycle_lane="current",
            all_links_missing=True,
            no_documented_by=True,
        )
    )
    assert scored.safe_to_delete is False
    assert "needs_human_task" in scored.blockers


def test_coverage_gap_opt_in():
    sym = _sym("s2", symbol_path="pkg.mod.need", doc_required=True)
    out = find_stale_doc_candidates(
        [],
        [sym],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        include_coverage_gaps=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert any(r["finding_kind"] == "coverage_gap" for r in rows)


def test_index_docs_skipped():
    doc = _doc("idx", "docs/example/00-index.md", linked=[])
    out = find_stale_doc_candidates(
        [doc],
        [],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert not rows


def test_score_only_decreases_with_recent_cap():
    young = score_candidate(ScoreInput(finding_kind="orphan_doc", days_since_touch=1))
    old = score_candidate(ScoreInput(finding_kind="orphan_doc", days_since_touch=400))
    assert young.score <= 0.55
    assert old.score >= young.score


def test_wiki_orphan_under_wiki_path():
    doc = _doc(
        "wiki1",
        "docs/wiki/modules/auth.md",
        linked=[],
        fm={"authority": "informative", "lifecycle_lane": "current", "updated_at": "2020-01-01"},
    )
    out = find_stale_doc_candidates(
        [doc],
        [],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    wiki = [r for r in rows if r["finding_kind"] == "wiki_orphan"]
    assert wiki
    assert wiki[0]["safe_to_delete"] is False
    assert wiki[0]["safe_to_update"] is True


def test_wiki_orphan_via_tag():
    doc = _doc(
        "wiki2",
        "docs/generated/auth.md",
        linked=[],
        fm={
            "authority": "informative",
            "lifecycle_lane": "current",
            "tags": ["repository-code-wiki"],
            "updated_at": "2020-01-01",
        },
    )
    out = find_stale_doc_candidates(
        [doc],
        [],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert any(r["finding_kind"] == "wiki_orphan" for r in rows)


def test_duplicate_authority_shared_symbol_without_relation():
    a = _doc(
        "dup-a",
        "docs/example/a.md",
        linked=["pkg.mod.Shared"],
        fm={
            "authority": "normative",
            "lifecycle_lane": "current",
            "doc_id": "as.doc.test.dup-a",
            "updated_at": "2020-01-01",
        },
    )
    b = _doc(
        "dup-b",
        "docs/example/b.md",
        linked=["pkg.mod.Shared"],
        fm={
            "authority": "normative",
            "lifecycle_lane": "current",
            "doc_id": "as.doc.test.dup-b",
            "updated_at": "2020-01-01",
        },
    )
    sym = _sym("s1", symbol_path="pkg.mod.Shared")
    # Anchors so they are not orphan_doc; still claim same SoT topic.
    anc_a = DocAnchor(
        "aa",
        SCOPE,
        a.id,
        sym.id,
        "hash-a",
        "ok",
        "2020-01-01T00:00:00+00:00",
        "2020-01-01T00:00:00+00:00",
    )
    anc_b = DocAnchor(
        "ab",
        SCOPE,
        b.id,
        sym.id,
        "hash-a",
        "ok",
        "2020-01-01T00:00:00+00:00",
        "2020-01-01T00:00:00+00:00",
    )
    out = find_stale_doc_candidates(
        [a, b],
        [sym],
        [anc_a, anc_b],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    dups = [r for r in rows if r["finding_kind"] == "duplicate_authority"]
    assert len(dups) == 2
    assert all(r["safe_to_delete"] is False for r in dups)
    assert all("needs_human_task" in (r.get("blockers") or []) for r in dups)


def test_duplicate_authority_skipped_when_related_docs():
    a = _doc(
        "rel-a",
        "docs/example/rel-a.md",
        linked=["pkg.mod.Shared"],
        fm={
            "authority": "normative",
            "lifecycle_lane": "current",
            "doc_id": "as.doc.test.rel-a",
            "related_docs": ["as.doc.test.rel-b"],
            "updated_at": "2020-01-01",
        },
    )
    b = _doc(
        "rel-b",
        "docs/example/rel-b.md",
        linked=["pkg.mod.Shared"],
        fm={
            "authority": "normative",
            "lifecycle_lane": "current",
            "doc_id": "as.doc.test.rel-b",
            "related_docs": ["as.doc.test.rel-a"],
            "updated_at": "2020-01-01",
        },
    )
    sym = _sym("s1", symbol_path="pkg.mod.Shared")
    anc_a = DocAnchor(
        "aa",
        SCOPE,
        a.id,
        sym.id,
        "hash-a",
        "ok",
        "2020-01-01T00:00:00+00:00",
        "2020-01-01T00:00:00+00:00",
    )
    anc_b = DocAnchor(
        "ab",
        SCOPE,
        b.id,
        sym.id,
        "hash-a",
        "ok",
        "2020-01-01T00:00:00+00:00",
        "2020-01-01T00:00:00+00:00",
    )
    out = find_stale_doc_candidates(
        [a, b],
        [sym],
        [anc_a, anc_b],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert not any(r["finding_kind"] == "duplicate_authority" for r in rows)


def test_duplicate_authority_via_primary_entities():
    a = _doc(
        "ent-a",
        "docs/example/ent-a.md",
        linked=[],
        fm={
            "authority": "normative",
            "lifecycle_lane": "current",
            "doc_id": "as.doc.test.ent-a",
            "primary_entities": ["StaleDocCandidate"],
            "updated_at": "2020-01-01",
        },
    )
    b = _doc(
        "ent-b",
        "docs/example/ent-b.md",
        linked=[],
        fm={
            "authority": "normative",
            "lifecycle_lane": "current",
            "doc_id": "as.doc.test.ent-b",
            "primary_entities": ["StaleDocCandidate"],
            "updated_at": "2020-01-01",
        },
    )
    # Give each an unrelated resolved link so they are not orphan_doc.
    sa = _sym("sa", symbol_path="pkg.a.fn", path="pkg/a.py")
    sb = _sym("sb", symbol_path="pkg.b.fn", path="pkg/b.py")
    a.linked_symbols = ["pkg.a.fn"]
    a.frontmatter["linked_symbols"] = ["pkg.a.fn"]
    b.linked_symbols = ["pkg.b.fn"]
    b.frontmatter["linked_symbols"] = ["pkg.b.fn"]
    anc_a = DocAnchor(
        "aa",
        SCOPE,
        a.id,
        sa.id,
        "hash-a",
        "ok",
        "2020-01-01T00:00:00+00:00",
        "2020-01-01T00:00:00+00:00",
    )
    anc_b = DocAnchor(
        "ab",
        SCOPE,
        b.id,
        sb.id,
        "hash-a",
        "ok",
        "2020-01-01T00:00:00+00:00",
        "2020-01-01T00:00:00+00:00",
    )
    out = find_stale_doc_candidates(
        [a, b],
        [sa, sb],
        [anc_a, anc_b],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert any(r["finding_kind"] == "duplicate_authority" for r in rows)


def test_healthy_anchored_doc_not_flagged():
    sym = _sym("s-healthy", symbol_path="pkg.mod.healthy")
    doc = _doc("healthy", "docs/example/healthy.md", linked=["pkg.mod.healthy"])
    anc = DocAnchor(
        "ah",
        SCOPE,
        doc.id,
        sym.id,
        "hash-a",
        "ok",
        "2020-01-01T00:00:00+00:00",
        "2020-01-01T00:00:00+00:00",
    )
    out = find_stale_doc_candidates(
        [doc],
        [sym],
        [anc],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert not any(r.get("doc_id") == "as.doc.test.healthy" for r in rows)


def test_ghost_link_safe_to_unlink():
    doc = _doc("ghost2", "docs/example/ghost2.md", linked=["pkg.mod.gone"])
    out = find_stale_doc_candidates(
        [doc],
        [],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    ghost = [r for r in rows if r["finding_kind"] == "ghost_link"]
    assert ghost
    assert ghost[0]["safe_to_unlink"] is True
    assert ghost[0]["safe_to_delete"] is True


def test_fixture_noise_path_skipped():
    doc = _doc("noise", "docs/fixtures/never_should_exist_orphan.md", linked=[])
    out = find_stale_doc_candidates(
        [doc],
        [],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert not rows


def test_wiki_orphan_score_floor():
    scored = score_candidate(ScoreInput(finding_kind="wiki_orphan", days_since_touch=400))
    assert scored.score == 0.80
    assert scored.safe_to_delete is False
    assert scored.safe_to_update is True


def test_normative_empty_links_not_orphan():
    doc = _doc(
        "norm",
        "docs/example/norm.md",
        linked=[],
        fm={"authority": "normative", "lifecycle_lane": "current"},
    )
    out = find_stale_doc_candidates(
        [doc],
        [],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert not any(r.get("finding_kind") == "orphan_doc" for r in rows)


def test_class_method_linked_symbol_resolves():
    sym = _sym(
        "s-method",
        path="backend/services/docs-sync-service/src/docs_sync_service/service.py",
        symbol_path="docs_sync_service.service.DocsSyncService.stale_candidates",
    )
    doc = _doc(
        "methody",
        "docs/example/methody.md",
        linked=[
            "backend/services/docs-sync-service/src/docs_sync_service/service.py::DocsSyncService.stale_candidates",
        ],
        fm={"authority": "normative", "lifecycle_lane": "current"},
    )
    out = find_stale_doc_candidates(
        [doc],
        [sym],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert not any(r.get("finding_kind") == "ghost_link" for r in rows)


def test_blank_linked_symbol_tokens_ignored():
    sym = _sym("s-ok", path="pkg/ok.py", symbol_path="pkg.ok.fn")
    doc = _doc(
        "blanky",
        "docs/example/blanky.md",
        linked=["", "  ", "pkg/ok.py::fn"],
        fm={"authority": "informative", "lifecycle_lane": "current"},
    )
    # Simulate store-side empty string on the Document model field.
    doc.linked_symbols = ["", "pkg/ok.py::fn"]
    out = find_stale_doc_candidates(
        [doc],
        [sym],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert not any(r.get("finding_kind") == "ghost_link" for r in rows)
    for r in rows:
        details = [e.get("detail") for e in (r.get("evidence") or []) if e.get("kind") == "linked_symbol_missing"]
        assert "" not in details
        assert None not in details


def test_future_lane_empty_links_not_orphan():
    doc = _doc(
        "fut",
        "docs/example/future.md",
        linked=[],
        fm={"authority": "normative", "lifecycle_lane": "future"},
    )
    out = find_stale_doc_candidates(
        [doc],
        [],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert not any(r.get("finding_kind") == "orphan_doc" for r in rows)


def test_path_linked_symbols_resolve_via_file_path():
    sym = _sym(
        "s-path",
        path="backend/services/code-graph-service/src/code_graph_service/domain/dead_code_scoring.py",
        symbol_path="code_graph_service.domain.dead_code_scoring.score",
    )
    doc = _doc(
        "pathy",
        "docs/example/pathy.md",
        linked=[
            "backend/services/code-graph-service/src/code_graph_service/domain/dead_code_scoring.py",
            "backend/services/code-graph-service/src/code_graph_service/domain/unused_candidates/",
        ],
        fm={"authority": "normative", "lifecycle_lane": "current"},
    )
    anc = DocAnchor(
        "ap",
        SCOPE,
        doc.id,
        sym.id,
        "hash-a",
        "ok",
        "2020-01-01T00:00:00+00:00",
        "2020-01-01T00:00:00+00:00",
    )
    out = find_stale_doc_candidates(
        [doc],
        [sym],
        [anc],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert not any(r.get("finding_kind") == "ghost_link" for r in rows)


def test_unresolved_path_only_links_not_ghost_when_index_sparse():
    doc = _doc(
        "sparse",
        "docs/example/sparse.md",
        linked=["backend/services/missing_pkg/nope.py"],
        fm={"authority": "normative", "lifecycle_lane": "current"},
    )
    out = find_stale_doc_candidates(
        [doc],
        [],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert not any(r.get("finding_kind") in {"ghost_link", "orphan_doc"} for r in rows)
