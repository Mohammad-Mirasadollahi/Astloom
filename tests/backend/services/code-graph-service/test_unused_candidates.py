"""Unit tests for unused-symbol candidate detection and scoring."""

from __future__ import annotations

from code_graph_service.domain.dead_code_scoring import (
    ScoreInput,
    coverage_confirmation_port,
    flag_controlled_dead_port,
    llm_triage_port,
    score_candidate,
    string_name_reference_port,
)
from code_graph_service.domain.enums import CallConfidence, DocStatus, RelType, SymbolKind
from code_graph_service.domain.models import GraphEdge, GraphSymbol, Scope
from code_graph_service.domain.unused_candidates import find_unused_candidates

SCOPE = Scope("t", "w", "p")


def _sym(
    sid: str,
    name: str,
    *,
    kind: SymbolKind = SymbolKind.FUNCTION,
    path: str = "pkg/mod.py",
    body: str = "return 1",
    visibility: str = "public",
) -> GraphSymbol:
    return GraphSymbol(
        id=sid,
        scope=SCOPE,
        kind=kind,
        file_path=path,
        name=name,
        qualified_name=f"pkg.mod.{name}",
        signature=f"def {name}():",
        body=body,
        hash_value="h",
        ai_documentation="",
        doc_status=DocStatus.UNCHANGED,
        embedding=[],
        visibility=visibility,
    )


def test_changed_symbols_unused_helper():
    helper = _sym("s:helper", "old_helper", visibility="private")
    caller = _sym("s:caller", "run")
    # Live importer in the same file so private unused reaches base 0.95.
    live_fn = _sym("s:live", "live_fn", visibility="public")
    edges = [
        GraphEdge(
            id="e1",
            scope=SCOPE,
            rel_type=RelType.CALLS.value,
            source_id=caller.id,
            target_id="s:other",
            confidence=CallConfidence.EXACT,
        ),
        GraphEdge(
            id="e2",
            scope=SCOPE,
            rel_type=RelType.IMPORTS.value,
            source_id=caller.id,
            target_id=live_fn.id,
            confidence=CallConfidence.EXACT,
        ),
    ]
    out = find_unused_candidates(
        [helper, caller, live_fn],
        edges,
        scope_mode="changed_symbols",
        anchor_symbols=["old_helper"],
    )
    assert out["freshness"] == "ok"
    assert len(out["candidates"]) == 1
    row = out["candidates"][0]
    assert row["safe_to_delete"] is True
    assert row["symbol"].endswith("old_helper")
    assert row["score"] >= 0.80
    assert row["confidence"] == "high"
    assert row["finding_kind"] == "unused_symbol"
    assert row["evidence"]
    assert any(e.get("kind") == "no_inbound_strong_use" for e in row["evidence"])
    assert out["kpi_hints"]["dead_code_candidates_surfaced"] == 1


def test_entrypoint_is_live_root_not_candidate():
    """Entrypoints are live roots (sound over-approx); not listed for deletion."""
    main = _sym("s:main", "main", body="print('hi')")
    out = find_unused_candidates(
        [main],
        [],
        scope_mode="explicit_paths",
        anchor_paths=["pkg/mod.py"],
        include_uncertain=True,
    )
    assert out["candidates"] == []
    assert not any(r.get("symbol", "").endswith("main") for r in out["skipped_uncertain"])


def test_no_anchors_refuses_repo_scan():
    helper = _sym("s:helper", "orphan")
    out = find_unused_candidates([helper], [], scope_mode="changed_symbols")
    assert out["candidates"] == []
    assert out.get("note") == "no_anchor_symbols_or_paths"


def test_project_scan_allows_whole_project():
    helper = _sym("s:helper", "orphan", visibility="private")
    out = find_unused_candidates(
        [helper],
        [],
        scope_mode="project_scan",
        min_confidence=0.8,
    )
    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["safe_to_delete"] is True


def test_freshness_stale_blocks_safe_delete():
    helper = _sym("s:helper", "old_helper")
    out = find_unused_candidates(
        [helper],
        [],
        scope_mode="changed_symbols",
        anchor_symbols=["old_helper"],
        freshness="pending_sync",
        include_uncertain=True,
    )
    assert out["candidates"] == []
    assert out["skipped_uncertain"]
    assert any("freshness_pending_sync" in (row.get("blockers") or []) for row in out["skipped_uncertain"])
    assert out["skipped_uncertain"][0]["score"] <= 0.50


def test_inbound_call_excludes_symbol():
    helper = _sym("s:helper", "helper")
    caller = _sym("s:caller", "run")
    edges = [
        GraphEdge(
            id="e1",
            scope=SCOPE,
            rel_type=RelType.CALLS.value,
            source_id=caller.id,
            target_id=helper.id,
            confidence=CallConfidence.EXACT,
        )
    ]
    out = find_unused_candidates(
        [helper, caller],
        edges,
        scope_mode="changed_symbols",
        anchor_symbols=["helper"],
    )
    assert out["candidates"] == []


def test_ambiguous_call_does_not_mark_live_but_caps_score():
    helper = _sym("s:helper", "helper", visibility="private")
    caller = _sym("s:caller", "run")
    edges = [
        GraphEdge(
            id="e1",
            scope=SCOPE,
            rel_type=RelType.CALLS.value,
            source_id=caller.id,
            target_id=helper.id,
            confidence=CallConfidence.AMBIGUOUS,
        )
    ]
    out = find_unused_candidates(
        [helper, caller],
        edges,
        scope_mode="changed_symbols",
        anchor_symbols=["helper"],
        # Normative: ambiguous must surface without requiring include_uncertain.
    )
    assert out["candidates"] == []
    rows = [
        r
        for r in out["skipped_uncertain"]
        if r.get("symbol_id") == helper.id and r.get("finding_kind") == "unused_symbol"
    ]
    assert rows
    row = rows[0]
    assert row["score"] <= 0.55
    assert "weak_or_ambiguous_call_edge" in row["blockers"]
    assert any(e.get("kind") == "weak_or_ambiguous_call_edge" for e in row["evidence"])


def test_tested_by_only_marks_test_only():
    helper = _sym("s:helper", "helper", visibility="private")
    test_fn = _sym("s:test", "test_helper", path="tests/test_mod.py")
    edges = [
        GraphEdge(
            id="e1",
            scope=SCOPE,
            rel_type=RelType.TESTED_BY.value,
            source_id=helper.id,
            target_id=test_fn.id,
            confidence=CallConfidence.EXACT,
        )
    ]
    out = find_unused_candidates(
        [helper, test_fn],
        edges,
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,
    )
    helper_rows = [
        r
        for r in (out["candidates"] + out["skipped_uncertain"])
        if r.get("symbol_id") == helper.id and r.get("finding_kind") == "unused_symbol"
    ]
    assert helper_rows
    assert helper_rows[0].get("test_only") is True
    assert helper_rows[0].get("safe_to_delete") is not True


def test_graph_corpus_string_name_blocks_safe_delete():
    helper = _sym("s:helper", "OldHelper", visibility="private")
    registry = _sym(
        "s:reg",
        "register",
        path="pkg/registry.py",
        body='HANDLERS = {"OldHelper": None}\n',
    )
    out = find_unused_candidates(
        [helper, registry],
        [],
        scope_mode="changed_symbols",
        anchor_symbols=["OldHelper"],
        include_uncertain=True,
    )
    assert out["candidates"] == []
    rows = [r for r in out["skipped_uncertain"] if r.get("symbol_id") == helper.id]
    assert rows
    assert "string_name_reference" in rows[0]["blockers"]
    assert rows[0]["score"] <= 0.45


def test_wip_path_caps_score():
    helper = _sym("s:helper", "scratch_fn", path="pkg/wip/mod.py", visibility="private")
    out = find_unused_candidates(
        [helper],
        [],
        scope_mode="changed_symbols",
        anchor_symbols=["scratch_fn"],
    )
    assert out["candidates"] == []
    rows = out["skipped_uncertain"]
    assert rows
    assert rows[0]["score"] <= 0.55
    assert "wip_or_recent_path" in rows[0]["blockers"]
    assert any(e.get("kind") == "wip_or_recent_path" for e in rows[0]["evidence"])


def test_http_handler_not_safe_to_delete():
    """Decorated HTTP handlers are live roots (entrypoint); never safe_to_delete."""
    handler = _sym(
        "s:login",
        "login",
        body="@app.get('/login')\ndef login():\n    return 1\n",
    )
    out = find_unused_candidates(
        [handler],
        [],
        scope_mode="changed_symbols",
        anchor_symbols=["login"],
        include_uncertain=True,
    )
    assert out["candidates"] == []
    assert not any(r.get("safe_to_delete") for r in out["skipped_uncertain"])


def test_registry_blocker():
    helper = _sym(
        "s:helper",
        "old_helper",
        body="HANDLERS = {'x': old_helper}\nreturn 1\n",
    )
    out = find_unused_candidates(
        [helper],
        [],
        scope_mode="changed_symbols",
        anchor_symbols=["old_helper"],
        include_uncertain=True,
    )
    assert out["candidates"] == []
    rows = [
        r
        for r in out["skipped_uncertain"]
        if r.get("symbol_id") == helper.id and r.get("finding_kind") == "unused_symbol"
    ]
    assert rows
    assert "possible_string_registry" in rows[0]["blockers"]


def test_tsoc_defer_blocker():
    helper = _sym(
        "s:helper",
        "old_helper",
        body="# tsoc-defer: keep until migration; remove when done\nreturn 1\n",
    )
    out = find_unused_candidates(
        [helper],
        [],
        scope_mode="changed_symbols",
        anchor_symbols=["old_helper"],
        include_uncertain=True,
    )
    assert out["candidates"] == []
    rows = [
        r
        for r in out["skipped_uncertain"]
        if r.get("symbol_id") == helper.id and r.get("finding_kind") == "unused_symbol"
    ]
    assert rows
    assert "tsoc_defer" in rows[0]["blockers"]


def test_dead_subgraph_mutual_calls():
    a = _sym("s:a", "a_fn", visibility="private")
    b = _sym("s:b", "b_fn", visibility="private")
    edges = [
        GraphEdge(
            id="e1",
            scope=SCOPE,
            rel_type=RelType.CALLS.value,
            source_id=a.id,
            target_id=b.id,
            confidence=CallConfidence.EXACT,
        ),
        GraphEdge(
            id="e2",
            scope=SCOPE,
            rel_type=RelType.CALLS.value,
            source_id=b.id,
            target_id=a.id,
            confidence=CallConfidence.EXACT,
        ),
    ]
    out = find_unused_candidates(
        [a, b],
        edges,
        scope_mode="project_scan",
        min_confidence=0.5,
    )
    symbol_rows = [r for r in out["candidates"] if r["finding_kind"] == "dead_subgraph"]
    assert len(symbol_rows) == 2


def test_test_only_not_safe_to_delete():
    helper = _sym("s:helper", "helper", visibility="private")
    test_fn = _sym("s:test", "test_helper", path="tests/test_mod.py")
    edges = [
        GraphEdge(
            id="e1",
            scope=SCOPE,
            rel_type=RelType.CALLS.value,
            source_id=test_fn.id,
            target_id=helper.id,
            confidence=CallConfidence.EXACT,
        )
    ]
    out = find_unused_candidates(
        [helper, test_fn],
        edges,
        scope_mode="project_scan",
        include_uncertain=True,
        min_confidence=0.0,  # explicit: include capped test_only rows
    )
    helper_rows = [
        r
        for r in (out["candidates"] + out["skipped_uncertain"])
        if r.get("symbol_id") == helper.id and r.get("finding_kind") == "unused_symbol"
    ]
    assert helper_rows
    assert helper_rows[0].get("test_only") is True
    assert helper_rows[0].get("safe_to_delete") is not True


def test_min_confidence_filters():
    helper = _sym(
        "s:helper",
        "old_helper",
        body="# tsoc-defer: x\nreturn 1\n",
    )
    out = find_unused_candidates(
        [helper],
        [],
        scope_mode="project_scan",
        min_confidence=0.9,
        include_uncertain=True,
    )
    assert out["candidates"] == []
    assert out["skipped_uncertain"] == []


def test_score_candidate_monotonic_caps():
    high = score_candidate(
        ScoreInput(visibility="private", freshness="ok", file_has_live_importers=True)
    )
    assert high.score >= 0.90
    assert high.safe_to_delete is True
    private_orphan = score_candidate(ScoreInput(visibility="private", freshness="ok"))
    assert private_orphan.score == 0.80
    capped = score_candidate(
        ScoreInput(visibility="private", freshness="ok", blockers=["entrypoint"])
    )
    assert capped.score <= 0.40
    assert capped.safe_to_delete is False


def test_string_name_cap_is_point_45():
    scored = score_candidate(
        ScoreInput(
            visibility="private",
            freshness="ok",
            file_has_live_importers=True,
            blockers=["string_name_reference"],
        )
    )
    assert scored.score == 0.45
    assert scored.safe_to_delete is False


def test_project_scan_defaults_min_confidence_floor():
    helper = _sym("s:helper", "orphan", visibility="private")
    # Without explicit min_confidence, project_scan applies 0.50 floor (still surfaces high scores).
    out = find_unused_candidates([helper], [], scope_mode="project_scan")
    assert out["candidates"]
    assert out["candidates"][0]["score"] >= 0.50


def test_phase_ports_inert_by_default():
    assert string_name_reference_port("foo", "a.py") == []
    assert coverage_confirmation_port("s1") == []
    assert llm_triage_port({"safe_to_delete": False}, enabled=False) is None
    assert flag_controlled_dead_port() == []


def test_llm_triage_cannot_raise_safe_to_delete():
    verdict = llm_triage_port(
        {"safe_to_delete": False, "symbol": "x"},
        enabled=True,
        judge=lambda f: {"agree": True, "safe_to_delete": True},
    )
    assert verdict is not None
    assert verdict["safe_to_delete"] is False


def test_local_advisory_triage_default_judge():
    from code_graph_service.domain.dead_code_scoring import local_advisory_triage_judge

    verdict = llm_triage_port(
        {"safe_to_delete": False, "blockers": ["tsoc_defer"]},
        enabled=True,
    )
    assert verdict is not None
    assert verdict["verdict"] == "keep"
    assert verdict["engine"] == "local_rules"
    assert local_advisory_triage_judge({"test_only": True})["verdict"] == "delete_with_exclusive_tests"


def test_coverage_hits_block_safe_delete():
    helper = _sym("s:helper", "orphan", visibility="private")
    out = find_unused_candidates(
        [helper],
        [],
        scope_mode="changed_symbols",
        anchor_symbols=["orphan"],
        coverage_hits={"s:helper": 3},
    )
    assert out["candidates"] == []
    rows = out["skipped_uncertain"]
    assert rows
    assert "coverage_runtime_use" in rows[0]["blockers"]
    assert rows[0]["score"] <= 0.40


def test_coverage_zero_hits_evidence_only():
    helper = _sym("s:helper", "orphan", visibility="private")
    out = find_unused_candidates(
        [helper],
        [],
        scope_mode="changed_symbols",
        anchor_symbols=["orphan"],
        coverage_hits={"s:helper": 0},
    )
    rows = out["candidates"] + out["skipped_uncertain"]
    assert rows
    assert any(e.get("kind") == "coverage_zero_hits" for e in rows[0]["evidence"])
    assert "coverage_runtime_use" not in (rows[0].get("blockers") or [])


def test_flag_controlled_dead_from_states():
    helper = _sym("s:helper", "unused_flagged")
    out = find_unused_candidates(
        [helper],
        [],
        scope_mode="project_scan",
        min_confidence=0.5,
        flag_states={
            "feat.old": {
                "constant_for_days": 120,
                "symbol": "pkg.mod.unused_flagged",
                "symbol_id": "s:helper",
                "path": "pkg/mod.py",
            }
        },
    )
    flag_rows = [
        r for r in out["skipped_uncertain"] if r.get("finding_kind") == "flag_controlled_dead"
    ]
    assert flag_rows
    assert flag_rows[0]["safe_to_delete"] is not True
    assert "flag_controlled_dead_needs_refactor" in flag_rows[0]["blockers"]


def test_disk_search_string_name(tmp_path):
    helper = _sym("s:helper", "DiskOnlyName", visibility="private", path="pkg/mod.py")
    other = tmp_path / "other" / "reg.py"
    other.parent.mkdir(parents=True)
    other.write_text('NAMES = ["DiskOnlyName"]\n', encoding="utf-8")
    out = find_unused_candidates(
        [helper],
        [],
        scope_mode="changed_symbols",
        anchor_symbols=["DiskOnlyName"],
        repo_root=str(tmp_path),
        disk_search=True,
    )
    assert out["candidates"] == []
    assert any("string_name_reference" in (r.get("blockers") or []) for r in out["skipped_uncertain"])


def test_string_name_port_when_wired():
    blockers = string_name_reference_port(
        "OldHelper",
        "pkg/mod.py",
        search=lambda name, path: ["other/file.py"] if name == "OldHelper" else [],
    )
    assert blockers == ["string_name_reference"]


def test_zombie_package_finding():
    a = _sym("s:a", "a_fn", path="pkg/orphan/a.py", visibility="private")
    b = _sym("s:b", "b_fn", path="pkg/orphan/b.py", visibility="private")
    out = find_unused_candidates(
        [a, b],
        [],
        scope_mode="project_scan",
        min_confidence=0.0,
        include_uncertain=True,
    )
    rows = [
        r
        for r in (out["candidates"] + out["skipped_uncertain"])
        if r.get("finding_kind") == "zombie_package"
    ]
    assert rows
    assert rows[0]["kind"] == "package"
    assert rows[0]["safe_to_delete"] is False
    assert "zombie_package" in rows[0]["blockers"]
    assert rows[0].get("recommendation") == "retire"


def test_unwired_shared_package_wire_under_backend_packages(tmp_path):
    top = tmp_path / "backend" / "packages" / "code-metadata" / "code_metadata"
    top.mkdir(parents=True)
    (tmp_path / "tests" / "backend" / "packages").mkdir(parents=True)
    (tmp_path / "tests" / "backend" / "packages" / "test_code_metadata.py").write_text(
        "from code_metadata import load_profile\n", encoding="utf-8"
    )
    a = _sym(
        "s:a",
        "load_profile",
        path="backend/packages/code-metadata/code_metadata/loader.py",
        visibility="public",
    )
    b = _sym(
        "s:b",
        "validate_profile",
        path="backend/packages/code-metadata/code_metadata/contracts.py",
        visibility="public",
    )
    out = find_unused_candidates(
        [a, b],
        [],
        scope_mode="project_scan",
        min_confidence=0.0,
        include_uncertain=True,
        repo_root=str(tmp_path),
    )
    rows = [
        r
        for r in (out["candidates"] + out["skipped_uncertain"])
        if r.get("finding_kind") == "unwired_shared_package"
    ]
    assert rows
    assert rows[0]["recommendation"] == "wire"
    assert rows[0]["safe_to_delete"] is False
    assert "unwired_shared_package" in rows[0]["blockers"]


def test_unwired_shared_package_keep_public_for_sdk_lane():
    a = _sym(
        "s:a",
        "declare",
        path="backend/packages/adapter_harness/capability.py",
        visibility="public",
    )
    b = _sym(
        "s:b",
        "secret_ref",
        path="backend/packages/adapter_harness/secret_ref.py",
        visibility="public",
    )
    out = find_unused_candidates(
        [a, b],
        [],
        scope_mode="project_scan",
        min_confidence=0.0,
        include_uncertain=True,
    )
    rows = [
        r
        for r in (out["candidates"] + out["skipped_uncertain"])
        if r.get("finding_kind") == "unwired_shared_package"
    ]
    assert rows
    assert rows[0]["recommendation"] == "keep_public"
    assert rows[0]["safe_to_delete"] is False


def test_structural_package_findings_survive_max_results_noise():
    """Package findings must not be truncated away by many equal-score symbols."""
    harness_a = _sym(
        "s:ha",
        "declare",
        path="backend/packages/adapter_harness/capability.py",
        visibility="public",
    )
    harness_b = _sym(
        "s:hb",
        "secret_ref",
        path="backend/packages/adapter_harness/secret_ref.py",
        visibility="public",
    )
    noise = [
        _sym(f"s:n{i}", f"noise_{i:03d}", path=f"backend/packages/other/m{i:03d}.py")
        for i in range(40)
    ]
    out = find_unused_candidates(
        [harness_a, harness_b, *noise],
        [],
        scope_mode="project_scan",
        min_confidence=0.0,
        include_uncertain=True,
        max_results=5,
        path_prefix="backend/packages",
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert any(r.get("finding_kind") == "unwired_shared_package" for r in rows)
    assert any(r.get("recommendation") == "keep_public" for r in rows)


def test_runtime_dead_for_live_zero_coverage():
    helper = _sym("s:helper", "helper")
    caller = _sym("s:caller", "run")
    edges = [
        GraphEdge(
            id="e1",
            scope=SCOPE,
            rel_type=RelType.CALLS.value,
            source_id=caller.id,
            target_id=helper.id,
            confidence=CallConfidence.EXACT,
        )
    ]
    # Pool is helper only; caller outside marks it live. Zero coverage → runtime_dead.
    out = find_unused_candidates(
        [helper, caller],
        edges,
        scope_mode="changed_symbols",
        anchor_symbols=["helper"],
        min_confidence=0.0,
        include_uncertain=True,
        coverage_hits={"s:helper": 0},
    )
    rows = [
        r
        for r in (out["candidates"] + out["skipped_uncertain"])
        if r.get("finding_kind") == "runtime_dead" and r.get("symbol_id") == helper.id
    ]
    assert rows
    assert rows[0]["safe_to_delete"] is False
    assert "runtime_dead_needs_proof" in rows[0]["blockers"]


def test_kpi_hints_include_resolved_placeholder():
    helper = _sym("s:helper", "orphan", visibility="private")
    out = find_unused_candidates([helper], [], scope_mode="project_scan")
    assert out["kpi_hints"]["dead_code_candidates_resolved"] == 0


def test_path_prefix_filters_reported_candidates():
    """path_prefix limits reported pool; symbols outside the prefix are omitted."""
    in_pkg = _sym("s:in", "orphan_in", path="pkg_b/mod.py", visibility="private")
    out_pkg = _sym("s:out", "orphan_out", path="pkg_a/mod.py", visibility="private")
    out = find_unused_candidates(
        [in_pkg, out_pkg],
        [],
        scope_mode="project_scan",
        include_uncertain=True,
        path_prefix="pkg_b",
    )
    assert out["path_prefix"] == "pkg_b"
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    assert rows
    assert all(str(r.get("path") or "").startswith("pkg_b") for r in rows)
    assert not any("orphan_out" in str(r.get("symbol") or "") for r in rows)


def test_path_prefix_keeps_cross_package_callee_live():
    """Caller outside path_prefix still marks callee inside prefix as live."""
    main = _sym("s:main", "main", path="pkg_a/app.py", body="return helper()")
    helper = _sym("s:helper", "helper", path="pkg_b/lib.py", visibility="public")
    orphan = _sym("s:orphan", "orphan", path="pkg_b/lib.py", visibility="private")
    edges = [
        GraphEdge(
            id="e-call",
            scope=SCOPE,
            rel_type=RelType.CALLS.value,
            source_id=main.id,
            target_id=helper.id,
            confidence=CallConfidence.EXACT,
        ),
    ]
    out = find_unused_candidates(
        [main, helper, orphan],
        edges,
        scope_mode="project_scan",
        include_uncertain=True,
        path_prefix="pkg_b",
        min_confidence=0.0,
    )
    rows = list(out["candidates"]) + list(out["skipped_uncertain"])
    names = {str(r.get("symbol") or "") for r in rows}
    assert any("orphan" in n for n in names)
    assert not any(r.get("safe_to_delete") and "helper" in str(r.get("symbol") or "") for r in rows)
    # helper must not appear as an unused candidate at all when reachable from outside.
    assert not any(n.endswith(".helper") or n.endswith("helper") for n in names if "orphan" not in n)


def test_score_never_increases_for_old_files():
    young = score_candidate(
        ScoreInput(visibility="private", freshness="ok", file_has_live_importers=True)
    )
    old = score_candidate(
        ScoreInput(
            visibility="private",
            freshness="ok",
            file_has_live_importers=True,
            days_since_touch=400,
        )
    )
    assert old.score <= young.score


def test_days_since_touch_ignores_graph_updated_at():
    from code_graph_service.domain.dead_code_scoring import days_since_touch_from_symbol

    helper = _sym("s:helper", "orphan")
    helper.updated_at = "2026-08-10T00:00:00Z"
    assert days_since_touch_from_symbol(helper) is None


def test_days_since_touch_uses_repo_mtime(tmp_path):
    from code_graph_service.domain.dead_code_scoring import days_since_touch_from_symbol

    rel = "pkg/old.py"
    target = tmp_path / rel
    target.parent.mkdir(parents=True)
    target.write_text("def orphan():\n    return 1\n", encoding="utf-8")
    # Make file look 40 days old
    import os
    import time as time_mod

    old_ts = time_mod.time() - (40 * 86400)
    os.utime(target, (old_ts, old_ts))
    helper = _sym("s:helper", "orphan", path=rel)
    helper.updated_at = "2026-08-10T00:00:00Z"
    days = days_since_touch_from_symbol(helper, repo_root=str(tmp_path))
    assert days is not None and days >= 30


def test_large_corpus_string_name_scan_stays_bounded():
    """Regression: project_scan must not O(dead × symbols) re-scan bodies."""
    import time

    noise: list[GraphSymbol] = []
    for i in range(4000):
        noise.append(
            _sym(
                f"s:n{i}",
                f"noise_{i}",
                path=f"pkg/noise_{i}.py",
                body=("payload = 1\n" * 60) + f'NAME = "noise_{i}"\n',
            )
        )
    dead = [
        _sym(f"s:d{i}", f"DeadTarget{i}", visibility="private", path=f"pkg/dead/{i}.py")
        for i in range(120)
    ]
    registry = _sym(
        "s:reg",
        "reg",
        path="pkg/registry.py",
        body='HANDLERS = ["DeadTarget0", "DeadTarget1"]\n',
    )
    started = time.perf_counter()
    out = find_unused_candidates(
        [*dead, registry, *noise],
        [],
        scope_mode="project_scan",
        min_confidence=0.0,
        include_uncertain=True,
        path_prefix="pkg/dead",
        max_results=200,
    )
    elapsed = time.perf_counter() - started
    assert elapsed < 3.0, f"unused scan too slow: {elapsed:.2f}s"
    blocked = [
        r
        for r in out["skipped_uncertain"]
        if "string_name_reference" in (r.get("blockers") or [])
    ]
    assert any(str(r.get("symbol") or "").endswith("DeadTarget0") for r in blocked)
