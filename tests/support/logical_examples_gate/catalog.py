from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "11-logical-implementation-examples"
CATALOG_DIR = ROOT / "backend" / "configs" / "logical-examples"
EXAMPLES_CATALOG = CATALOG_DIR / "examples-catalog.json"
LOGICAL_EXAMPLES_PACKAGE = ROOT / "backend" / "packages" / "logical_examples"


REQUIRED_DOCS: tuple[Path, ...] = (
    DOCS / "00-index.md",
    DOCS / "01-end-to-end-password-migration-example.md",
    DOCS / "02-memory-and-context-example.md",
    DOCS / "03-docs-and-code-graph-example.md",
    DOCS / "04-rule-engine-and-human-approval-example.md",
    DOCS / "05-interoperability-and-broker-example.md",
    DOCS / "06-developer-implementation-checklist.md",
    DOCS / "07-phase11-verification-and-acceptance.md",
)


DOC_TOPIC_MARKERS: tuple[tuple[str, str], ...] = (
    ("01-end-to-end-password-migration-example.md", "Edge Cases"),
    ("01-end-to-end-password-migration-example.md", "Developer Implementation Notes"),
    ("01-end-to-end-password-migration-example.md", "Task"),
    ("02-memory-and-context-example.md", "ContextBundle"),
    ("02-memory-and-context-example.md", "Edge Cases"),
    ("02-memory-and-context-example.md", "WeightProfile"),
    ("03-docs-and-code-graph-example.md", "Edge Cases"),
    ("03-docs-and-code-graph-example.md", "DriftFinding"),
    ("04-rule-engine-and-human-approval-example.md", "Edge Cases"),
    ("04-rule-engine-and-human-approval-example.md", "Escalation"),
    ("05-interoperability-and-broker-example.md", "Edge Cases"),
    ("05-interoperability-and-broker-example.md", "DeadLetter"),
    ("06-developer-implementation-checklist.md", "Core Data Model Checklist"),
    ("06-developer-implementation-checklist.md", "Memory and Context Checklist"),
    ("06-developer-implementation-checklist.md", "Minimum Coding Readiness Criteria"),
)
