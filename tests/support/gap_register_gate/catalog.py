from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "10-gap-analysis"
GOVERNANCE_DIR = ROOT / "backend" / "configs" / "governance"
GAP_REGISTER = GOVERNANCE_DIR / "gap-register.json"
GOVERNANCE_PACKAGE = ROOT / "backend" / "packages" / "governance_catalog"


REQUIRED_DOCS: tuple[Path, ...] = (
    DOCS / "00-index.md",
    DOCS / "01-gap-register.md",
    DOCS / "02-architecture-gaps.md",
    DOCS / "03-technical-implementation-gaps.md",
    DOCS / "04-governance-operations-gaps.md",
    DOCS / "05-gap-triage-and-resolution-process.md",
    DOCS / "06-phase10-verification-and-acceptance.md",
)


DOC_TOPIC_MARKERS: tuple[tuple[str, str], ...] = (
    ("01-gap-register.md", "GAP-001"),
    ("01-gap-register.md", "Status:"),
    ("02-architecture-gaps.md", "Architecture"),
    ("03-technical-implementation-gaps.md", "Technical"),
    ("04-governance-operations-gaps.md", "Governance"),
    ("05-gap-triage-and-resolution-process.md", "owner"),
    ("05-gap-triage-and-resolution-process.md", "phase gate"),
    ("05-gap-triage-and-resolution-process.md", "Accepted risk"),
    ("05-gap-triage-and-resolution-process.md", "closed"),
)
