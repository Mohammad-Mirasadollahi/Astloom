#!/usr/bin/env python3
"""Live MCP HTTP probe: docs stale_candidates on indexed fixture docs.

Requires ``astloom service`` up. Uses dedicated project scope.
Asserts per-doc finding kinds (not merely set membership) and a healthy control.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from usage_profile.mcp_tokens import mint_connect_token

ROOT = Path(__file__).resolve().parents[3]
SECRET = ROOT / ".astloom" / "mcp-http.secret"
MCP_URL = os.environ.get("ASTLOOM_MCP_HTTP_PUBLIC_URL", "http://127.0.0.1:32500").rstrip("/")
if not MCP_URL.endswith("/mcp"):
    MCP_URL = f"{MCP_URL}/mcp"

TENANT = "mir"
WORKSPACE = "dev"
PROJECT = "staledocs-live"
PATH_PREFIX = "docs/fixtures/stale_live"

DOC_ORPHAN = "as.doc.test.stale-live-orphan"
DOC_GHOST = "as.doc.test.stale-live-ghost"
DOC_WIKI = "as.doc.test.stale-live-wiki-orphan"
DOC_DUP_A = "as.doc.test.stale-live-dup-a"
DOC_DUP_B = "as.doc.test.stale-live-dup-b"
DOC_HEALTHY = "as.doc.test.stale-live-healthy"
DOC_RELATED_A = "as.doc.test.stale-live-rel-a"
DOC_RELATED_B = "as.doc.test.stale-live-rel-b"


def _payload(result: dict) -> dict:
    sc = result.get("structuredContent")
    if isinstance(sc, dict):
        return sc
    for part in result.get("content") or []:
        if part.get("type") == "text":
            return json.loads(part.get("text") or "{}")
    raise AssertionError(f"no structured payload: {result!r}")


def _index_ok(result: dict) -> None:
    assert result.get("written") == "document", result
    assert isinstance(result.get("document"), dict), result


def _by_doc_id(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        did = str(row.get("doc_id") or "")
        if did and did not in out:
            out[did] = row
    return out


@pytest.mark.live
def test_live_stale_docs_candidates_via_mcp_http():
    if not SECRET.is_file():
        pytest.skip(f"missing MCP secret at {SECRET}")

    secret = SECRET.read_text(encoding="utf-8").strip()
    os.environ["ASTLOOM_MCP_TOKEN_SECRET"] = secret
    token = mint_connect_token(
        tenant_id=TENANT, workspace_id=WORKSPACE, project_id=PROJECT, ttl_seconds=3600
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def rpc(method: str, params: dict | None = None, rid: int = 1) -> dict:
        response = httpx.post(
            MCP_URL,
            headers=headers,
            json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}},
            timeout=120.0,
        )
        response.raise_for_status()
        body = response.json()
        assert "error" not in body, body
        return body

    init = rpc(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "live-stale-docs", "version": "0"},
        },
        1,
    )
    assert "result" in init, init

    listed = rpc("tools/list", {}, 2)
    names = {t.get("name") for t in (listed.get("result") or {}).get("tools") or []}
    assert names == {"mcp_search_tools", "mcp_execute_tool"}, names

    search = rpc(
        "tools/call",
        {
            "name": "mcp_search_tools",
            "arguments": {"query": "stale documentation candidates docs write", "limit": 15},
        },
        3,
    )
    search_payload = _payload(search.get("result") or {})
    hits = list(search_payload.get("results") or [])
    by_name = {str(h.get("tool_name") or ""): h for h in hits if isinstance(h, dict)}
    assert "astloom_docs_stale_candidates" in by_name, search_payload
    assert "astloom_docs_write" in by_name, search_payload
    server_name = str(by_name["astloom_docs_stale_candidates"].get("server_name") or "")
    assert server_name

    rid = 4

    def execute(tool_name: str, tool_args: dict) -> dict:
        nonlocal rid
        call = rpc(
            "tools/call",
            {
                "name": "mcp_execute_tool",
                "arguments": {
                    "tool_name": tool_name,
                    "server_name": server_name,
                    "arguments": tool_args,
                },
            },
            rid,
        )
        rid += 1
        return _payload(call.get("result") or {})

    def index_doc(
        *,
        title: str,
        path: str,
        doc_id: str,
        body: str,
        frontmatter: dict,
        symbol: str | None = None,
        file_path: str | None = None,
    ) -> dict:
        args: dict = {
            "mode": "index",
            "title": title,
            "body": body,
            "path": path,
            "doc_id": doc_id,
            "frontmatter": frontmatter,
        }
        if symbol:
            args["symbol"] = symbol
        if file_path:
            args["file_path"] = file_path
        result = execute("astloom_docs_write", args)
        _index_ok(result)
        if symbol:
            assert result.get("symbol_id"), result
            assert result.get("anchor"), result
        return result

    index_doc(
        title="Live orphan fixture",
        path=f"{PATH_PREFIX}/orphan.md",
        doc_id=DOC_ORPHAN,
        body="Intentionally unlinked orphan doc for stale-docs live probe.\n",
        frontmatter={
            "doc_id": DOC_ORPHAN,
            "title": "Live orphan fixture",
            "owner": "live-test",
            "status": "active",
            "schema_version": "1.0",
            "linked_symbols": [],
            "decision_refs": [],
            "concern_lane": "product",
            "lifecycle_lane": "current",
            "authority": "informative",
            "updated_at": "2020-01-01",
        },
    )

    index_doc(
        title="Live ghost fixture",
        path=f"{PATH_PREFIX}/ghost.md",
        doc_id=DOC_GHOST,
        body="Doc with ghost linked_symbols for stale-docs live probe.\n",
        frontmatter={
            "doc_id": DOC_GHOST,
            "title": "Live ghost fixture",
            "owner": "live-test",
            "status": "active",
            "schema_version": "1.0",
            "linked_symbols": ["pkg.missing.symbol_absent_for_live"],
            "decision_refs": [],
            "concern_lane": "product",
            "lifecycle_lane": "current",
            "authority": "informative",
            "updated_at": "2020-01-01",
        },
    )

    index_doc(
        title="Live wiki orphan fixture",
        path=f"{PATH_PREFIX}/wiki/modules/auth.md",
        doc_id=DOC_WIKI,
        body="Published wiki page without durable code anchors.\n",
        frontmatter={
            "doc_id": DOC_WIKI,
            "title": "Live wiki orphan fixture",
            "owner": "live-test",
            "status": "active",
            "schema_version": "1.0",
            "linked_symbols": [],
            "decision_refs": [],
            "concern_lane": "product",
            "lifecycle_lane": "current",
            "authority": "informative",
            "tags": ["repository-code-wiki"],
            "updated_at": "2020-01-01",
        },
    )

    index_doc(
        title="Live duplicate authority A",
        path=f"{PATH_PREFIX}/dup-a.md",
        doc_id=DOC_DUP_A,
        body="Normative current peer A sharing SoT topic.\n",
        symbol="pkg.live.SharedSoT",
        file_path="pkg/live.py",
        frontmatter={
            "doc_id": DOC_DUP_A,
            "title": "Live duplicate authority A",
            "owner": "live-test",
            "status": "active",
            "schema_version": "1.0",
            "linked_symbols": ["pkg.live.SharedSoT"],
            "decision_refs": [],
            "concern_lane": "product",
            "lifecycle_lane": "current",
            "authority": "normative",
            "primary_entities": ["LiveStaleDupTopic"],
            "updated_at": "2020-01-01",
        },
    )
    index_doc(
        title="Live duplicate authority B",
        path=f"{PATH_PREFIX}/dup-b.md",
        doc_id=DOC_DUP_B,
        body="Normative current peer B sharing SoT topic without relation.\n",
        symbol="pkg.live.SharedSoT",
        file_path="pkg/live.py",
        frontmatter={
            "doc_id": DOC_DUP_B,
            "title": "Live duplicate authority B",
            "owner": "live-test",
            "status": "active",
            "schema_version": "1.0",
            "linked_symbols": ["pkg.live.SharedSoT"],
            "decision_refs": [],
            "concern_lane": "product",
            "lifecycle_lane": "current",
            "authority": "normative",
            "primary_entities": ["LiveStaleDupTopic"],
            "updated_at": "2020-01-01",
        },
    )

    # Related normative peers sharing a topic — must NOT be duplicate_authority.
    index_doc(
        title="Live related authority A",
        path=f"{PATH_PREFIX}/rel-a.md",
        doc_id=DOC_RELATED_A,
        body="Normative peer with declared related_docs.\n",
        symbol="pkg.live.RelatedSoT",
        file_path="pkg/related.py",
        frontmatter={
            "doc_id": DOC_RELATED_A,
            "title": "Live related authority A",
            "owner": "live-test",
            "status": "active",
            "schema_version": "1.0",
            "linked_symbols": ["pkg.live.RelatedSoT"],
            "decision_refs": [],
            "concern_lane": "product",
            "lifecycle_lane": "current",
            "authority": "normative",
            "related_docs": [DOC_RELATED_B],
            "updated_at": "2020-01-01",
        },
    )
    index_doc(
        title="Live related authority B",
        path=f"{PATH_PREFIX}/rel-b.md",
        doc_id=DOC_RELATED_B,
        body="Normative peer with declared related_docs.\n",
        symbol="pkg.live.RelatedSoT",
        file_path="pkg/related.py",
        frontmatter={
            "doc_id": DOC_RELATED_B,
            "title": "Live related authority B",
            "owner": "live-test",
            "status": "active",
            "schema_version": "1.0",
            "linked_symbols": ["pkg.live.RelatedSoT"],
            "decision_refs": [],
            "concern_lane": "product",
            "lifecycle_lane": "current",
            "authority": "normative",
            "related_docs": [DOC_RELATED_A],
            "updated_at": "2020-01-01",
        },
    )

    # Healthy control: unique anchored symbol — must not appear as a candidate.
    index_doc(
        title="Live healthy fixture",
        path=f"{PATH_PREFIX}/healthy.md",
        doc_id=DOC_HEALTHY,
        body="Healthy linked doc for negative precision probe.\n",
        symbol="pkg.live.HealthyOnly",
        file_path="pkg/healthy.py",
        frontmatter={
            "doc_id": DOC_HEALTHY,
            "title": "Live healthy fixture",
            "owner": "live-test",
            "status": "active",
            "schema_version": "1.0",
            "linked_symbols": ["pkg.live.HealthyOnly"],
            "decision_refs": [],
            "concern_lane": "product",
            "lifecycle_lane": "current",
            "authority": "informative",
            "updated_at": "2020-01-01",
        },
    )

    payload = execute(
        "astloom_docs_stale_candidates",
        {
            "scope_mode": "project_scan",
            "path_prefix": PATH_PREFIX,
            "min_confidence": 0.5,
            "max_results": 50,
            "include_uncertain": True,
            "triage": True,
        },
    )
    assert payload.get("scope_mode") == "project_scan", payload
    assert payload.get("path_prefix") == PATH_PREFIX, payload
    assert "index_coverage" in payload, payload
    cov = payload.get("index_coverage") or {}
    assert cov.get("safe_absence_claims") is True, payload
    hints = payload.get("kpi_hints") or {}
    assert "stale_docs_candidates_surfaced" in hints
    assert hints.get("stale_docs_candidates_resolved") == 0

    rows = list(payload.get("candidates") or []) + list(payload.get("skipped_uncertain") or [])
    assert rows, payload
    assert all(str(r.get("path") or "").startswith(PATH_PREFIX) for r in rows)
    by_id = _by_doc_id(rows)

    assert DOC_HEALTHY not in by_id, {"healthy_leaked": by_id.get(DOC_HEALTHY), "rows": rows}
    assert DOC_RELATED_A not in by_id and DOC_RELATED_B not in by_id, {
        "related_flagged": {DOC_RELATED_A: by_id.get(DOC_RELATED_A), DOC_RELATED_B: by_id.get(DOC_RELATED_B)},
        "rows": rows,
    }

    orphan = by_id[DOC_ORPHAN]
    assert orphan["finding_kind"] == "orphan_doc", orphan
    assert orphan.get("safe_to_delete") is True, orphan
    assert float(orphan.get("score") or 0) >= 0.8, orphan

    ghost = by_id[DOC_GHOST]
    assert ghost["finding_kind"] == "ghost_link", ghost
    assert ghost.get("safe_to_unlink") is True, ghost
    assert any(
        e.get("kind") == "linked_symbol_missing" for e in (ghost.get("evidence") or [])
    ), ghost

    wiki = by_id[DOC_WIKI]
    assert wiki["finding_kind"] == "wiki_orphan", wiki
    assert wiki.get("safe_to_delete") is not True, wiki
    assert wiki.get("safe_to_update") is True, wiki

    dup_a = by_id[DOC_DUP_A]
    dup_b = by_id[DOC_DUP_B]
    assert dup_a["finding_kind"] == "duplicate_authority", dup_a
    assert dup_b["finding_kind"] == "duplicate_authority", dup_b
    for dup in (dup_a, dup_b):
        assert dup.get("safe_to_delete") is not True, dup
        assert "needs_human_task" in (dup.get("blockers") or []), dup
        peers = set(dup.get("duplicate_peers") or [])
        assert peers, dup

    kinds = {str(r.get("finding_kind") or "") for r in rows}
    out = {
        "http_mcp_ok": True,
        "server_name": server_name,
        "project_id": PROJECT,
        "path_prefix": payload.get("path_prefix"),
        "index_coverage": payload.get("index_coverage"),
        "kpi_hints": hints,
        "row_count": len(rows),
        "finding_kinds": sorted(kinds),
        "by_doc_id": {
            did: {
                "finding_kind": row.get("finding_kind"),
                "score": row.get("score"),
                "safe_to_delete": row.get("safe_to_delete"),
                "safe_to_unlink": row.get("safe_to_unlink"),
                "safe_to_update": row.get("safe_to_update"),
                "blockers": row.get("blockers"),
            }
            for did, row in by_id.items()
        },
        "healthy_absent": DOC_HEALTHY not in by_id,
        "related_absent": DOC_RELATED_A not in by_id and DOC_RELATED_B not in by_id,
        "triage_engine": payload.get("triage_engine"),
    }
    artifact = ROOT / "tests" / "artifacts" / "docs-sync-live" / "stale-docs-live.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.path[:0] = [str(ROOT / "backend" / "packages")]
    test_live_stale_docs_candidates_via_mcp_http()
    print("HTTP_MCP_STALE_DOCS_OK")
