"""Unit tests for AWG layout profiles and untyped CommonItem migration."""

from __future__ import annotations

from pathlib import Path


def test_layout_profile_claude_dual_writes_agents_entry():
    from common_context_service.guidance_export import (
        planned_files_from_items,
        relative_paths_for_item,
    )

    item = {
        "id": "entry-1",
        "item_type": "agents_entry",
        "title": "Agent entry",
        "body": "# Agent entry\n",
        "slug": "agents-entry",
    }
    paths = relative_paths_for_item(item, "claude_compatible")
    assert paths == ["AGENTS.md", "CLAUDE.md"]
    planned = planned_files_from_items([item], "claude_compatible")
    assert {p["path"] for p in planned} == {"AGENTS.md", "CLAUDE.md"}


def test_layout_profile_claude_rule_and_skill_paths():
    from common_context_service.guidance_export import relative_paths_for_item
    from common_context_service.layout_profiles import get_layout_profile

    profile = get_layout_profile("claude_compatible")
    assert profile["always_rule_dir"] == ".claude/rules"
    assert profile["skill_dir"] == ".claude/skills"
    assert profile.get("cursor_mdc_frontmatter") is False

    rule = {"item_type": "always_rule", "slug": "mcp-first-astloom", "body": "# r\n"}
    skill = {"item_type": "skill", "name": "astloom-session-bootstrap", "body": "# s\n"}
    assert relative_paths_for_item(rule, "claude_compatible") == [
        ".claude/rules/mcp-first-astloom.md"
    ]
    assert relative_paths_for_item(skill, "claude_compatible") == [
        ".claude/skills/astloom-session-bootstrap/SKILL.md"
    ]


def test_layout_profile_generic_skips_rules_and_skills():
    from common_context_service.guidance_export import relative_paths_for_item

    rule = {"item_type": "always_rule", "slug": "x", "body": "# r\n"}
    skill = {"item_type": "skill", "name": "y", "body": "# s\n"}
    assert relative_paths_for_item(rule, "generic_agents_md") == []
    assert relative_paths_for_item(skill, "generic_agents_md") == []


def test_materialize_claude_compatible_writes_claude_md(tmp_path):
    from common_context_service.guidance_export import materialize_mcp_first_seed

    root = Path(tmp_path)
    result = materialize_mcp_first_seed(root, layout="claude_compatible")
    assert result["layout"] == "claude_compatible"
    assert (root / "AGENTS.md").is_file()
    assert (root / "CLAUDE.md").is_file()
    assert (root / ".claude/rules/mcp-first-astloom.md").is_file()
    assert (root / ".claude/skills/astloom-session-bootstrap/SKILL.md").is_file()
    # Cursor mdc frontmatter must not appear on Claude layout rules
    body = (root / ".claude/rules/mcp-first-astloom.md").read_text(encoding="utf-8")
    assert not body.startswith("---\n")


def test_migrate_untyped_guidance_proposals_and_apply():
    from common_context_service.guidance_migrate import migrate_untyped_guidance_items

    items = [
        {"id": "1", "item_type": "agents_entry", "title": "Agent entry"},
        {"id": "2", "slug": "always-mcp-first", "title": "MCP rule", "tags": []},
        {"id": "3", "path": ".cursor/skills/foo/SKILL.md", "title": "Foo"},
        {"id": "4", "title": "Random note", "body": "hello"},
    ]
    dry = migrate_untyped_guidance_items(items, apply=False)
    assert dry["unchanged"] == 1
    assert dry["skipped"] == 1
    assert {p["to"] for p in dry["proposals"]} == {"always_rule", "skill"}
    assert dry["items"] is items

    applied = migrate_untyped_guidance_items(items, apply=True)
    assert applied["applied"] is True
    by_id = {i["id"]: i for i in applied["items"]}
    assert by_id["2"]["item_type"] == "always_rule"
    assert by_id["3"]["item_type"] == "skill"
    assert by_id["1"]["item_type"] == "agents_entry"
    assert "item_type" not in by_id["4"] or by_id["4"].get("item_type") not in {
        "agents_entry",
        "always_rule",
        "skill",
    }
