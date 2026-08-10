"""Full-tier documentation authoring law for MCP-connected coding agents.

Single source of truth for:
- Seed skill `astloom-documentation-authoring`
- MCP tool `astloom_docs_authoring_standards` (maps_to docs_sync.authoring_standards)

Docs-sync Body-tier validate/note/draft/index is NOT sufficient for Astloom product
docs under `docs/`. Agents must apply this Full-tier law when writing or remediating
those trees.
"""

from __future__ import annotations

from typing import Any

# Canonical paths (read on disk when available; this payload is always available via MCP).
CANONICAL_PATHS: dict[str, str] = {
    "portable_law": "docs/agents/documentation-authoring.md",
    "team_playbook": "docs/agents/team-documentation-playbook-for-astloom.md",
    "team_handout": "docs/agents/TEAM-HANDOUT-astloom-documentation-complete.md",
    "standardization_procedure": "docs/00-master-plan/10-documentation-standardization-procedure.md",
    "hybrid_coverage": "docs/07-code-knowledge-graph/41-hybrid-documentation-coverage.md",
    "docs_catalog": "docs/07-code-knowledge-graph/42-documentation-catalog-and-lane-cache.md",
    "standards_pack": "backend/docs/standards/documentation/",
    "pack_01": "backend/docs/standards/documentation/01-professional-documentation-standard.md",
    "pack_02": "backend/docs/standards/documentation/02-documentation-structure-and-machine-ingest-standard.md",
    "pack_03": "backend/docs/standards/documentation/03-documentation-classification-and-lanes.md",
    "pack_04": "backend/docs/standards/documentation/04-diagrams-and-agent-readable-flows.md",
    "write_documentation_skill": ".agents/skills/write-documentation/",
}

# Closed-set reminders; full enums live in pack 03 / procedure 09.
REQUIRED_FRONTMATTER_KEYS: list[str] = [
    "doc_id",
    "title",
    "doc_type",
    "status",
    "schema_version",
    "owner",
    "summary",
    "tags",
    "phase",
    "canonical_path",
    "lifecycle_lane",
    "concern_lane",
    "audience_lane",
    "authority",
    "visibility",
]

HARD_REQUIREMENTS: list[str] = [
    "English only in committed Markdown.",
    "Correct folder under docs/, backend/docs/, frontend/docs/, ai-toolstack/docs/, or deploy-toolkit.",
    "Full YAML frontmatter including all five lane fields (closed-set enums).",
    "doc_id form as.doc.<domain>.<slug> for Astloom docs/ (never tsoc.doc.* there).",
    "Exactly one H1 matching title; Purpose H2; chunkable H2s; Related Documents for normative types.",
    "Soft body budget ~400 lines, hard ~800 — split siblings when exceeded.",
    "Implementation-grade content (contracts, ownership, failure, verification) — not marketing.",
    "Design types (hld/lld/feature_spec/service_design): Mermaid + matching agent-readable flow table in the same H2.",
    "linked_symbols only when evidence exists on disk (qualified_name / path::Symbol / symbol id).",
    "Optional evidence helper: astloom docs-suggest-links (dry-run; --apply only updates frontmatter; sync creates edges).",
    "Hybrid coverage optional layers prefer human → living → rationale → AST; never invent DOCUMENTED_BY (see docs/07-code-knowledge-graph/41-hybrid-documentation-coverage.md).",
    "Use docs catalog (astloom docs-catalog / astloom_docs_catalog) for tag/lane narrowing before reading many Markdown files.",
    "When standardizing or remediating: follow docs/00-master-plan/10-documentation-standardization-procedure.md.",
    "On material create/edit: keep body truthful, bump doc_version (semver MAJOR.MINOR.PATCH), set updated_at to UTC YYYY-MM-DD — never stamp-only.",
    "Prefer docs-sync drift / linked_symbols / catalog to decide which docs a code change must update — dates alone are not the signal.",
    "Fix-on-read: after opening a product Markdown file that fails Full-tier law, remediate that file in the same turn before continuing.",
    "Verify with CLI: astloom docs-standards (zero issues; heed missing_recommended:doc_version/updated_at warnings) and astloom quality-audit for docs.* categories.",
]

TIER_BOUNDARY: dict[str, str] = {
        "body_tier": (
            "Body-tier: docs-sync MCP validate/note/draft/index — thinner frontmatter for governed "
            "docs-as-code sync. Necessary for drift/coverage workflows; NOT Full-tier compliance."
        ),
        "full_tier": (
            "Full-tier: Astloom product documentation under docs/ (and other normative trees). "
            "Requires portable law + packs 01–04 + procedure 10. MCP tool "
            "astloom_docs_authoring_standards returns this checklist."
        ),
    }

CLI_GATES: list[str] = [
    "astloom docs-standards",
    "astloom docs-standards remediate (when remediating)",
    "astloom docs-suggest-links (hybrid evidence linked_symbols suggestions)",
    "astloom docs-catalog (tags/lanes cache for retrieval; --refresh after bulk doc edits)",
    "astloom quality-audit (docs.* categories must be clean)",
    "astloom_quality_audit MCP (session start + after material edits)",
]

SKILL_MARKDOWN = """---
name: astloom-documentation-authoring
description: Full-tier ThinkingSOC/Astloom Markdown authoring law for MCP coding agents.
---

# Astloom documentation authoring (Full-tier)

## When

- How documentation works / what standards apply.
- Create or materially edit Markdown under `docs/`, `backend/docs/`, `frontend/docs/`,
  `ai-toolstack/docs/`, or `deploy-toolkit/**/*.md`.
- Remediate nonconforming product docs.
- **Fix-on-read:** Read a product Markdown file that fails Full-tier law.

## Mandatory first step (MCP)

1. Call `astloom_docs_authoring_standards` and follow that checklist (SSOT for Full-tier).
2. When writing/remediating on disk, also use as needed:
   - `docs/agents/team-documentation-playbook-for-astloom.md`
   - `docs/00-master-plan/10-documentation-standardization-procedure.md`
   - `docs/agents/documentation-authoring.md`
   - Packs under `backend/docs/standards/documentation/` and hybrid coverage doc 41

## Hard requirements

1. English only in committed docs.
2. Full frontmatter: `doc_id`, `title`, `doc_type`, `status`, `schema_version`, `owner`,
   `summary`, `tags`, `phase`, `canonical_path`, plus lanes
   (`lifecycle_lane`, `concern_lane`, `audience_lane`, `authority`, `visibility`).
3. Astloom `docs/`: `doc_id` = `as.doc.<domain>.<slug>`.
4. One H1 = title; Purpose H2; modular H2s; Related Documents for normative types.
5. Soft ≤ ~400 body lines; hard ≤ ~800 or split.
6. Design docs: Mermaid + matching flow table in the same H2 (not Mermaid-only).
7. `linked_symbols` only with on-disk evidence (`astloom docs-suggest-links` optional).
8. Standardize via procedure 10; gate with `astloom docs-standards` and `astloom quality-audit`.
9. Hybrid layers (optional): human → living → rationale → AST; never invent edges.
10. Narrow with `astloom_docs_catalog` / `astloom docs-catalog` before wide Read.
11. **Revision on material create/edit:** bump `doc_version` (semver) and set `updated_at`
    (`YYYY-MM-DD` UTC) **with** truthful body changes — never stamp-only. Prefer drift /
    `linked_symbols` / catalog to choose which docs a code change must update.
12. **Fix-on-read:** remediate a nonconforming product doc you opened **in the same turn**.

## Body-tier vs Full-tier

- **Body-tier:** `astloom_docs_write` validate/note/draft/index — docs-sync only.
- **Full-tier:** this skill + `astloom_docs_authoring_standards` — required for product docs.

## Do not

- Treat docs-sync validate as Full-tier.
- Invent Persian committed Markdown.
- Leave a Read/reviewed nonconforming doc unfixed in the same turn.
- Use `linked_symbols` without evidence.
- Invent `DOCUMENTED_BY` outside `astloom sync` Phase 2 resolve.
- Bump `doc_version` / `updated_at` without aligning the document body.
"""


def authoring_law_payload() -> dict[str, Any]:
    """Structured payload for MCP tool astloom_docs_authoring_standards."""
    return {
        "law_id": "astloom.documentation_authoring.full_tier",
        "schema_version": "1.0",
        "summary": (
            "Full-tier documentation authoring law for Astloom product Markdown. "
            "Docs-sync Body-tier tools alone are not sufficient."
        ),
        "tier_boundary": TIER_BOUNDARY,
        "canonical_paths": CANONICAL_PATHS,
        "required_frontmatter_keys": REQUIRED_FRONTMATTER_KEYS,
        "revision_frontmatter_keys": ["doc_version", "updated_at"],
        "hard_requirements": HARD_REQUIREMENTS,
        "cli_gates": CLI_GATES,
        "skill_name": "astloom-documentation-authoring",
        "related_mcp_tools": [
            "astloom_docs_authoring_standards",
            "astloom_docs_catalog",
            "astloom_docs_status",
            "astloom_docs_drift_check",
            "astloom_docs_write",
            "astloom_quality_audit",
            "astloom_code_graph_generation_context",
            "astloom_guidance_get_skill",
        ],
        "skill_markdown": SKILL_MARKDOWN,
    }
