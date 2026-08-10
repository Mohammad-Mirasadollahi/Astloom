"""Tests for docs catalog cache and filters."""

from __future__ import annotations

import json
from pathlib import Path

from astloom_cli.docs_catalog import (
    build_docs_catalog,
    filter_docs_catalog,
    get_docs_catalog,
)


def _write_doc(
    root: Path,
    rel: str,
    *,
    tags: list[str],
    concern: str,
    title: str,
    lifecycle: str = "current",
) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    tag_yaml = "\n".join(f"- {t}" for t in tags)
    path.write_text(
        f"""---
doc_id: as.doc.test.{path.stem}
title: {title}
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Test summary for {title}.
tags:
{tag_yaml}
phase: agents
canonical_path: {rel}
lifecycle_lane: {lifecycle}
concern_lane: {concern}
audience_lane:
- agents
authority: normative
visibility: internal
linked_symbols: []
---

# {title}

## Purpose

Body.
""",
        encoding="utf-8",
    )


def test_build_catalog_vocabularies_are_observed_not_hardcoded(tmp_path: Path):
    _write_doc(tmp_path, "docs/a.md", tags=["ckg", "hybrid"], concern="standard", title="A")
    _write_doc(
        tmp_path,
        "docs/b.md",
        tags=["widget-xyz"],
        concern="my-product-lane",
        title="B",
        lifecycle="shipped-beta",
    )
    (tmp_path / "docs" / "bare.md").write_text("# no fm\n", encoding="utf-8")
    catalog = build_docs_catalog(tmp_path, roots=["docs"])
    assert catalog["mode"] == "docs_catalog"
    assert catalog["invents_edges"] is False
    assert catalog["vocabulary_source"] == "observed_frontmatter"
    # Custom values appear; global Astloom enums are NOT injected.
    assert "my-product-lane" in catalog["vocabularies"]["concern_lane"]
    assert "shipped-beta" in catalog["vocabularies"]["lifecycle_lane"]
    assert "standard" in catalog["vocabularies"]["concern_lane"]
    assert "gap" not in catalog["vocabularies"]["concern_lane"]  # never seen → absent
    assert catalog["lane_enums"]["concern_lane"] == catalog["vocabularies"]["concern_lane"]
    assert catalog["stats"]["document_count"] == 2
    tags = {row["tag"]: row["count"] for row in catalog["tags"]}
    assert tags["ckg"] == 1
    assert tags["widget-xyz"] == 1


def test_cache_hit_and_filter(tmp_path: Path, monkeypatch):
    _write_doc(tmp_path, "docs/x.md", tags=["alpha"], concern="design", title="X Doc")
    monkeypatch.setenv("ASTLOOM_DOCS_CATALOG_CACHE", str(tmp_path / "cache.json"))
    first = get_docs_catalog(tmp_path, refresh=True, roots=["docs"])
    assert first["cache_hit"] is False
    path = Path(first["cache_path"])
    assert path.is_file()
    second = get_docs_catalog(tmp_path, refresh=False)
    assert second["cache_hit"] is True
    filtered = filter_docs_catalog(second, tag="alpha", concern_lane="design", limit=10)
    assert filtered["match_count"] == 1
    assert filtered["documents"][0]["title"] == "X Doc"
    assert "design" in filtered["vocabularies"]["concern_lane"]


def test_filter_query_and_linked_only(tmp_path: Path):
    _write_doc(tmp_path, "docs/y.md", tags=["z"], concern="gap", title="Hybrid Notes")
    catalog = build_docs_catalog(tmp_path, roots=["docs"])
    catalog["documents"][0]["has_linked_symbols"] = True
    catalog["documents"][0]["linked_symbols_count"] = 2
    hit = filter_docs_catalog(catalog, query="hybrid", has_linked_symbols=True)
    assert hit["match_count"] == 1
    miss = filter_docs_catalog(catalog, query="hybrid", has_linked_symbols=False)
    assert miss["match_count"] == 0


def test_filter_query_matches_all_tokens(tmp_path: Path):
    _write_doc(
        tmp_path,
        "docs/09-automated-followup-task-lifecycle-and-retention.md",
        tags=["task", "followup"],
        concern="standard",
        title="Automated Follow-Up Task Lifecycle and Retention",
    )
    catalog = build_docs_catalog(tmp_path, roots=["docs"])
    hit = filter_docs_catalog(catalog, query="followup task lifecycle retention")
    assert hit["match_count"] == 1
    miss = filter_docs_catalog(catalog, query="followup missingtoken")
    assert miss["match_count"] == 0


def test_env_roots_override(tmp_path: Path, monkeypatch):
    _write_doc(tmp_path, "handbook/h.md", tags=["hb"], concern="guide", title="H")
    monkeypatch.setenv("ASTLOOM_DOCS_CATALOG_ROOTS", "handbook")
    monkeypatch.setenv("ASTLOOM_DOCS_CATALOG_CACHE", str(tmp_path / "env-cache.json"))
    catalog = get_docs_catalog(tmp_path, refresh=True)
    assert catalog["roots"] == ["handbook"]
    assert catalog["stats"]["document_count"] == 1
    assert "guide" in catalog["vocabularies"]["concern_lane"]


def test_refresh_docs_catalog_after_sync(tmp_path: Path, monkeypatch):
    _write_doc(tmp_path, "docs/s.md", tags=["sync"], concern="ops", title="S")
    monkeypatch.setenv("ASTLOOM_DOCS_CATALOG_CACHE", str(tmp_path / "after-sync.json"))
    monkeypatch.setenv("ASTLOOM_DOCS_CATALOG_ROOTS", "docs")
    from astloom_cli.docs_catalog import refresh_docs_catalog_after_sync

    info = refresh_docs_catalog_after_sync(tmp_path)
    assert info["ok"] is True
    assert info["document_count"] == 1
    assert Path(info["cache_path"]).is_file()


def test_cmd_docs_catalog_json(tmp_path: Path, monkeypatch, capsys):
    import argparse

    from astloom_cli.commands.docs_catalog import cmd_docs_catalog

    _write_doc(tmp_path, "docs/c.md", tags=["cli"], concern="onboarding", title="CLI")
    monkeypatch.setattr("astloom_cli.commands.docs_catalog.repo_root", lambda: tmp_path)
    monkeypatch.setenv("ASTLOOM_DOCS_CATALOG_CACHE", str(tmp_path / "c.json"))
    args = argparse.Namespace(
        refresh=True,
        json=True,
        roots="docs",
        tag="cli",
        concern="onboarding",
        lifecycle="",
        audience="",
        phase="",
        doc_type="",
        query="",
        linked_only=False,
        unlinked_only=False,
        limit=20,
    )
    assert cmd_docs_catalog(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["match_count"] == 1
    assert payload["invents_edges"] is False
    assert payload["vocabulary_source"] == "observed_frontmatter"
