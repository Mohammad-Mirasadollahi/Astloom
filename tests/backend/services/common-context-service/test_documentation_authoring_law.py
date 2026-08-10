"""Unit tests for Full-tier documentation authoring law payload."""

from __future__ import annotations

from common_context_service.documentation_authoring_law import (
    REQUIRED_FRONTMATTER_KEYS,
    SKILL_MARKDOWN,
    authoring_law_payload,
)
from common_context_service.seed_mcp_first import mcp_first_seed_payloads


def test_authoring_law_payload_has_full_tier_checklist():
    payload = authoring_law_payload()
    assert payload["law_id"] == "astloom.documentation_authoring.full_tier"
    assert "doc_id" in payload["required_frontmatter_keys"]
    assert set(REQUIRED_FRONTMATTER_KEYS).issubset(set(payload["required_frontmatter_keys"]))
    assert any("Mermaid" in item for item in payload["hard_requirements"])
    assert "astloom docs-standards" in payload["cli_gates"]
    assert "Body-tier" in payload["tier_boundary"]["body_tier"]
    assert "Full-tier" in payload["tier_boundary"]["full_tier"]
    assert "NOT Full-tier" in payload["tier_boundary"]["body_tier"]


def test_seed_includes_documentation_authoring_skill():
    skills = [p for p in mcp_first_seed_payloads() if p.get("item_type") == "skill"]
    names = {p["name"] for p in skills}
    assert "astloom-documentation-authoring" in names
    assert "astloom-docs-sync" in names
    assert "astloom-remove-dead-code" in names
    assert "astloom-remove-stale-docs" in names
    assert "astloom-source-contracts" in names
    assert "astloom-standards-on-edit" in names
    authoring = next(p for p in skills if p["name"] == "astloom-documentation-authoring")
    assert authoring["body"] == SKILL_MARKDOWN
    assert "astloom_docs_authoring_standards" in authoring["body"]
    docs_sync = next(p for p in skills if p["name"] == "astloom-docs-sync")
    assert "Full-tier" in docs_sync["body"] or "astloom_docs_authoring_standards" in docs_sync["body"]
    dead = next(p for p in skills if p["name"] == "astloom-remove-dead-code")
    assert "live until proven" in dead["body"]
    stale = next(p for p in skills if p["name"] == "astloom-remove-stale-docs")
    assert "astloom_docs_stale_candidates" in stale["body"]
    contracts = next(p for p in skills if p["name"] == "astloom-source-contracts")
    assert "49-module-contract" in contracts["body"]
    assert "50-package-folder" in contracts["body"]
    on_edit = next(p for p in skills if p["name"] == "astloom-standards-on-edit")
    assert "fix-on-write" in on_edit["body"]
    assert "doc_version" in on_edit["body"]
    assert "updated_at" in on_edit["body"]
    assert "astloom-documentation-authoring" in on_edit["body"]
    entry = next(p for p in mcp_first_seed_payloads() if p.get("item_type") == "agents_entry")
    assert "astloom-remove-dead-code" in entry["body"]
    assert "astloom-source-contracts" in entry["body"]
    assert "astloom-standards-on-edit" in entry["body"]


def test_mcp_first_rule_requires_source_contracts():
    rule = next(p for p in mcp_first_seed_payloads() if p.get("item_type") == "always_rule")
    assert "astloom_docs_authoring_standards" in rule["body"]
    assert "Full-tier" in rule["body"]
    assert "49-module-contract-docstrings-standard" in rule["body"]
    assert "50-package-folder-readme-standard" in rule["body"]
    assert "astloom-source-contracts" in rule["body"]
    assert "astloom-standards-on-edit" in rule["body"]
    assert "Fix-on-read (docs)" in rule["body"]
    assert "Fix-on-read (module contracts)" in rule["body"]
    assert "Fix-on-write (standards)" in rule["body"]
    assert "same turn" in rule["body"]
    contracts = next(
        p for p in mcp_first_seed_payloads() if p.get("item_type") == "skill" and p["name"] == "astloom-source-contracts"
    )
    assert "Fix-on-read" in contracts["body"]
    from common_context_service.documentation_authoring_law import SKILL_MARKDOWN

    assert "Fix-on-read" in SKILL_MARKDOWN
