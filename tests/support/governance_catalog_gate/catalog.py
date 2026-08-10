from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "09-platform-governance-operations"
GOVERNANCE_DIR = ROOT / "backend" / "configs" / "governance"
RISK_CATALOG = GOVERNANCE_DIR / "risk-open-decisions.json"
IMPACT_KPIS = GOVERNANCE_DIR / "impact-kpis.json"
GOVERNANCE_PACKAGE = ROOT / "backend" / "packages" / "governance_catalog"


REQUIRED_DOCS: tuple[Path, ...] = (
    DOCS / "00-index.md",
    DOCS / "01-security-access-control-and-privacy.md",
    DOCS / "02-observability-slo-and-incident-response.md",
    DOCS / "03-ci-cd-release-and-environment-strategy.md",
    DOCS / "04-data-retention-backup-and-disaster-recovery.md",
    DOCS / "05-api-versioning-and-contract-governance.md",
    DOCS / "06-runbooks-and-operational-procedures.md",
    DOCS / "07-risk-register-and-open-decisions.md",
    DOCS / "08-glossary-and-ubiquitous-language.md",
    DOCS / "09-automated-deployment-and-connectivity-runbooks.md",
    DOCS / "10-impact-reporting-and-benefit-measurement.md",
    DOCS / "11-phase9-verification-and-acceptance.md",
)


DOC_TOPIC_MARKERS: tuple[tuple[str, str], ...] = (
    ("01-security-access-control-and-privacy.md", "tenant"),
    ("01-security-access-control-and-privacy.md", "prompt"),
    ("02-observability-slo-and-incident-response.md", "SLO"),
    ("02-observability-slo-and-incident-response.md", "incident"),
    ("03-ci-cd-release-and-environment-strategy.md", "rollback"),
    ("04-data-retention-backup-and-disaster-recovery.md", "backup"),
    ("04-data-retention-backup-and-disaster-recovery.md", "restore"),
    ("05-api-versioning-and-contract-governance.md", "compatib"),
    ("05-api-versioning-and-contract-governance.md", "deprecat"),
    ("06-runbooks-and-operational-procedures.md", "runbook"),
    ("07-risk-register-and-open-decisions.md", "owner"),
    ("07-risk-register-and-open-decisions.md", "mitigation"),
    ("08-glossary-and-ubiquitous-language.md", "Activity"),
    ("09-automated-deployment-and-connectivity-runbooks.md", "install"),
    ("09-automated-deployment-and-connectivity-runbooks.md", "connector"),
    ("09-automated-deployment-and-connectivity-runbooks.md", "upgrade"),
    ("09-automated-deployment-and-connectivity-runbooks.md", "drift"),
    ("09-automated-deployment-and-connectivity-runbooks.md", "repair"),
    ("10-impact-reporting-and-benefit-measurement.md", "baseline"),
    ("10-impact-reporting-and-benefit-measurement.md", "token"),
    ("10-impact-reporting-and-benefit-measurement.md", "sample size"),
    ("10-impact-reporting-and-benefit-measurement.md", "caveat"),
)
