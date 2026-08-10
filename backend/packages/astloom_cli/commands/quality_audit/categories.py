"""Quality-audit finding categories (docs + code)."""

from __future__ import annotations

# Stable category ids used in reports and saved files.
CATEGORY_DOCS_STANDARDS = "docs.standards"
CATEGORY_DOCS_SIZE_SOFT = "docs.size_soft"
CATEGORY_DOCS_SIZE_HARD = "docs.size_hard"
CATEGORY_DOCS_LINKING_GAP = "docs.linking_gap"
CATEGORY_DOCS_FLOW_TABLE = "docs.flow_table_gap"
CATEGORY_DOCS_LANE_INVALID = "docs.lane_invalid"
CATEGORY_DOCS_REVISION_MISSING = "docs.revision_missing"
CATEGORY_DOCS_REVISION_INVALID = "docs.revision_invalid"
CATEGORY_DOCS_STALE_CLEANUP_HINT = "docs.stale_cleanup_hint"
CATEGORY_CODE_NEVER_INGESTED = "code.never_ingested"
CATEGORY_CODE_STALE_EDITED = "code.stale_edited"
CATEGORY_CODE_LOW_SYMBOL_DOCS = "code.low_symbol_docs"
CATEGORY_CODE_MISSING_EMBEDDINGS = "code.missing_embeddings"
CATEGORY_CODE_DEAD_CODE_HINT = "code.dead_code_cleanup_hint"

CATEGORY_META: dict[str, dict[str, str]] = {
    CATEGORY_DOCS_STANDARDS: {
        "title": "Documentation standards gate",
        "severity": "high",
        "meaning": "Full-tier machine check failed (frontmatter, lanes, H1/Purpose, Mermaid, hard size).",
        "fix_hint": "Follow docs/00-master-plan/10-documentation-standardization-procedure.md; run remediator.",
    },
    CATEGORY_DOCS_SIZE_SOFT: {
        "title": "Documentation soft size budget",
        "severity": "medium",
        "meaning": "Body exceeds ~400 lines; split into sibling modules.",
        "fix_hint": "Split on H2/H3; scripts/split_soft_budget_docs.py or manual siblings.",
    },
    CATEGORY_DOCS_SIZE_HARD: {
        "title": "Documentation hard size budget",
        "severity": "high",
        "meaning": "Body exceeds 800 lines; blocking for standardization.",
        "fix_hint": "Must split before accept; see standardization procedure §7.",
    },
    CATEGORY_DOCS_LINKING_GAP: {
        "title": "Documentation linking gap",
        "severity": "medium",
        "meaning": "Doc cites code paths but linked_symbols is empty or missing those tokens.",
        "fix_hint": (
            "Add path::Symbol evidence links; dry-run `astloom docs-suggest-links` "
            "(optional `--apply`), then `astloom sync`. See hybrid coverage doc 41."
        ),
    },
    CATEGORY_DOCS_FLOW_TABLE: {
        "title": "Design flow-table gap",
        "severity": "low",
        "meaning": "Design doc has Mermaid but no Step/Actor/Action/Outcome table.",
        "fix_hint": "Add flow table under Mermaid; remediator/optional enrichment inserts one.",
    },
    CATEGORY_DOCS_LANE_INVALID: {
        "title": "Invalid documentation lane",
        "severity": "medium",
        "meaning": "concern_lane (or related) uses a forbidden alias / closed-set violation.",
        "fix_hint": "Normalize per standardization procedure §4; remediator maps aliases.",
    },
    CATEGORY_DOCS_REVISION_MISSING: {
        "title": "Documentation revision stamp missing",
        "severity": "medium",
        "meaning": "Missing recommended doc_version and/or updated_at (soft migration).",
        "fix_hint": (
            "On material edit: bump doc_version (semver) and set updated_at (UTC YYYY-MM-DD). "
            "Baseline: python scripts/stamp_docs_revision.py --date YYYY-MM-DD."
        ),
    },
    CATEGORY_DOCS_REVISION_INVALID: {
        "title": "Documentation revision stamp invalid",
        "severity": "high",
        "meaning": "doc_version or updated_at present but not valid (semver / ISO date).",
        "fix_hint": "Fix to doc_version MAJOR.MINOR.PATCH and updated_at YYYY-MM-DD (UTC).",
    },
    CATEGORY_DOCS_STALE_CLEANUP_HINT: {
        "title": "Stale-documentation cleanup opportunity",
        "severity": "low",
        "meaning": (
            "Linking gaps or sync inventory may leave orphan/ghost/stale docs; "
            "Astloom scores candidates but does not delete Markdown."
        ),
        "fix_hint": (
            "After sync: MCP astloom_docs_stale_candidates "
            "(task_neighborhood default; project_scan + path_prefix for scoped discovery; "
            "prefer safe_to_update/safe_to_unlink; act on safe_to_delete only with score>=0.8); "
            "skill astloom-remove-stale-docs. "
            "See docs/07-code-knowledge-graph/78-stale-documentation-candidates-and-cleanup-loop.md."
        ),
    },
    CATEGORY_CODE_NEVER_INGESTED: {
        "title": "Code never ingested",
        "severity": "high",
        "meaning": "Client software files discovered by sync filters but not yet in the code graph.",
        "fix_hint": "Run astloom sync for pinned software paths.",
    },
    CATEGORY_CODE_STALE_EDITED: {
        "title": "Code stale after ingest",
        "severity": "high",
        "meaning": "Previously ingested files changed on disk and need re-sync.",
        "fix_hint": "Run astloom sync (incremental) for edited paths.",
    },
    CATEGORY_CODE_LOW_SYMBOL_DOCS: {
        "title": "Low living-doc coverage",
        "severity": "medium",
        "meaning": "Ingested files have little or no LLM/living documentation on symbols.",
        "fix_hint": "Re-sync with LLM docs enabled; check RPM/cloud consent and sync progress.",
    },
    CATEGORY_CODE_MISSING_EMBEDDINGS: {
        "title": "Missing semantic index rows",
        "severity": "high",
        "meaning": "Searchable graph symbols exist without a persisted embedding row.",
        "fix_hint": (
            "Run astloom sync (heals embeddings for touched files; noop drains a "
            "capped backlog). For full-project missing/mismatch heal: "
            "astloom sync heal (or ASTLOOM_EMBEDDING_REFRESH_FULL=1 once); "
            "inspect embedding_refresh on failure."
        ),
    },
    CATEGORY_CODE_DEAD_CODE_HINT: {
        "title": "Dead-code cleanup opportunity",
        "severity": "low",
        "meaning": (
            "Stale or never-ingested code may leave orphaned predecessors after "
            "replace/retire; Astloom scores candidates but does not delete files."
        ),
        "fix_hint": (
            "After sync: MCP astloom_code_graph_unused_candidates "
            "(task_neighborhood default; project_scan + path_prefix for scoped discovery; "
            "act only on safe_to_delete with score>=0.8 in the same change); "
            "skill astloom-remove-dead-code. "
            "See docs/07-code-knowledge-graph/36-dead-code-candidates-and-cleanup-loop.md."
        ),
    },
}

VALID_CONCERNS = frozenset(
    {
        "standard",
        "design",
        "decision",
        "problem",
        "gap",
        "contract",
        "ops",
        "example",
        "cross_team",
        "onboarding",
        "security",
        "product",
    }
)
