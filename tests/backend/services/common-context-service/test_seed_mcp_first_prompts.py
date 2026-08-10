"""Seed MCP-first prompts stay modular (one file each, no markdown tables)."""

from __future__ import annotations

import re

from common_context_service.seed_mcp_first import (
    AGENTS_ENTRY_BODY,
    MCP_FIRST_RULE_BODY,
    mcp_first_seed_payloads,
)
from common_context_service.seed_mcp_first_prompts import load_prompt, prompts_root

_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)


def test_prompt_files_exist_separately():
    root = prompts_root()
    assert (root / "always_rule_mcp_first.md").is_file()
    assert (root / "agents_entry.md").is_file()
    for name in (
        "astloom-session-bootstrap",
        "astloom-memory",
        "astloom-code-graph",
        "astloom-remove-dead-code",
        "astloom-durable-write",
        "astloom-docs-sync",
        "astloom-source-contracts",
        "astloom-standards-on-edit",
        "astloom-quality-audit",
        "astloom-create-task",
    ):
        assert (root / "skills" / f"{name}.md").is_file()
    # documentation-authoring stays in documentation_authoring_law — not merged here
    assert not (root / "skills" / "astloom-documentation-authoring.md").exists()


def test_seed_prompt_files_have_no_markdown_tables():
    root = prompts_root()
    paths = [root / "always_rule_mcp_first.md", root / "agents_entry.md"]
    paths.extend(sorted((root / "skills").glob("*.md")))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert _TABLE_ROW.search(text) is None, f"markdown table found in {path.name}"


def test_loaded_bodies_match_dedicated_files_not_concatenated():
    assert MCP_FIRST_RULE_BODY == load_prompt("always_rule_mcp_first.md")
    assert AGENTS_ENTRY_BODY == load_prompt("agents_entry.md")
    # Agents entry uses a bullet list, not a pipe table.
    assert "| Skill |" not in AGENTS_ENTRY_BODY
    assert "`astloom-standards-on-edit`" in AGENTS_ENTRY_BODY
    assert "`astloom-quality-audit`" in AGENTS_ENTRY_BODY
    assert "Quality debt loop" in MCP_FIRST_RULE_BODY or "astloom_quality_audit" in MCP_FIRST_RULE_BODY

    skills = {
        p["name"]: p["body"]
        for p in mcp_first_seed_payloads()
        if p.get("item_type") == "skill"
    }
    memory = load_prompt("skills", "astloom-memory.md")
    create = load_prompt("skills", "astloom-create-task.md")
    assert skills["astloom-memory"] == memory
    assert skills["astloom-create-task"] == create
    # Bodies are not glued together.
    assert "# Astloom create task" not in memory
    assert "# Astloom memory" not in create
