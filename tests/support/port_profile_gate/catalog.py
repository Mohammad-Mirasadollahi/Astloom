from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "08-software-engineering-architecture"
PORT_PROFILE = ROOT / "backend" / "configs" / "port-profiles" / "astloom-dev.json"
PORT_PACKAGE = ROOT / "backend" / "packages" / "port_profile"

# Presence checks for shared packages that live under hyphenated dirs or contracts/sdk.
SHARED_PACKAGE_LOADERS: tuple[tuple[str, Path], ...] = (
    ("shared_kernel", ROOT / "backend/packages/shared-kernel/shared_kernel/config.py"),
    ("contracts", ROOT / "backend/packages/contracts/api/__init__.py"),
    ("sdk", ROOT / "backend/packages/sdk/python/client.py"),
    ("code_metadata", ROOT / "backend/packages/code-metadata/code_metadata/loader.py"),
    ("common_context", ROOT / "backend/packages/common-context/common_context/loader.py"),
)


@dataclass(frozen=True)
class OwnedService:
    name: str
    src_path: Path
    test_path: Path
    contract_glob: str
    port_key: str


OWNED_SERVICES: tuple[OwnedService, ...] = (
    OwnedService(
        "core-data-service",
        ROOT / "backend/services/core-data-service/src",
        ROOT / "tests/backend/services/core-data-service",
        "**/phase-1-api-contract.md",
        "ASTLOOM_CORE_DATA_PORT",
    ),
    OwnedService(
        "memory-service",
        ROOT / "backend/services/memory-service/src",
        ROOT / "tests/backend/services/memory-service",
        "**/phase-2-api-contract.md",
        "ASTLOOM_MEMORY_PORT",
    ),
    OwnedService(
        "docs-sync-service",
        ROOT / "backend/services/docs-sync-service/src",
        ROOT / "tests/backend/services/docs-sync-service",
        "**/phase-3-api-contract.md",
        "ASTLOOM_DOCS_SYNC_PORT",
    ),
    OwnedService(
        "rule-engine-service",
        ROOT / "backend/services/rule-engine-service/src",
        ROOT / "tests/backend/services/rule-engine-service",
        "**/phase-4-api-contract.md",
        "ASTLOOM_RULE_ENGINE_PORT",
    ),
    OwnedService(
        "adapter-service",
        ROOT / "backend/services/adapter-service/src",
        ROOT / "tests/backend/services/adapter-service",
        "**/phase-5-api-contract.md",
        "ASTLOOM_ADAPTER_PORT",
    ),
    OwnedService(
        "code-graph-service",
        ROOT / "backend/services/code-graph-service/src",
        ROOT / "tests/backend/services/code-graph-service",
        "**/phase-7-api-contract.md",
        "ASTLOOM_CODE_GRAPH_PORT",
    ),
)


REQUIRED_DOCS: tuple[Path, ...] = (
    DOCS / "00-index.md",
    DOCS / "01-architecture-principles.md",
    DOCS / "02-service-boundaries-and-modules.md",
    DOCS / "04-development-port-management.md",
    DOCS / "05-modular-project-structure.md",
    DOCS / "06-engineering-operating-model.md",
    DOCS / "08-interface-and-contract-engineering.md",
    DOCS / "09-data-and-persistence-engineering.md",
    DOCS / "11-testing-and-verification-engineering.md",
    DOCS / "12-ci-cd-and-release-engineering.md",
    DOCS / "14-observability-and-debuggability-engineering.md",
    DOCS / "16-security-and-threat-modeling-engineering.md",
    DOCS / "17-engineering-governance-and-change-control.md",
    DOCS / "19-zero-touch-installation-and-bootstrap-automation.md",
    DOCS / "23-project-isolation-and-composition-architecture.md",
    DOCS / "24-admin-web-interface-and-agent-control-surface.md",
    DOCS / "25-live-and-unit-test-strategy.md",
    DOCS / "34-phase8-verification-and-acceptance.md",
)


DOC_TOPIC_MARKERS: tuple[tuple[str, str], ...] = (
    ("04-development-port-management.md", "ASTLOOM_"),
    ("08-interface-and-contract-engineering.md", "compatibility"),
    ("09-data-and-persistence-engineering.md", "migration"),
    ("12-ci-cd-and-release-engineering.md", "rollback"),
    ("16-security-and-threat-modeling-engineering.md", "trust boundaries"),
    ("23-project-isolation-and-composition-architecture.md", "ProjectGroup"),
    ("24-admin-web-interface-and-agent-control-surface.md", "Activity Timeline"),
    ("25-live-and-unit-test-strategy.md", "Live Test"),
)
