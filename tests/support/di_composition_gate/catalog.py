"""DI composition gate catalog (Phases A–D)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SEA = ROOT / "docs" / "08-software-engineering-architecture"
SERVICES = ROOT / "backend" / "services"
CLI_PKG = ROOT / "backend" / "packages" / "astloom_cli"

REQUIRED_DOCS: tuple[Path, ...] = (
    SEA / "30-dependency-injection-and-composition-root.md",
    SEA / "45-backend-di-composition-feature-specification.md",
    SEA / "46-backend-di-composition-high-level-design.md",
    SEA / "47-backend-di-composition-low-level-design.md",
    SEA / "48-backend-di-composition-risks-challenges-and-acceptance.md",
)

CODE_GRAPH_BOOTSTRAP = (
    SERVICES / "code-graph-service" / "src" / "code_graph_service" / "bootstrap.py"
)
CODE_GRAPH_API = (
    SERVICES / "code-graph-service" / "src" / "code_graph_service" / "api" / "__init__.py"
)
CODE_GRAPH_APPLICATION = (
    SERVICES / "code-graph-service" / "src" / "code_graph_service" / "application"
)
CODE_GRAPH_DOMAIN = SERVICES / "code-graph-service" / "src" / "code_graph_service" / "domain"
MCP_STORE_FACTORY = (
    SERVICES / "mcp-gateway-service" / "src" / "mcp_gateway_service" / "store_factory.py"
)

CLI_PROCESS_CONTAINERS = CLI_PKG / "process_containers.py"
CLI_GRAPH_COMMANDS = CLI_PKG / "commands" / "graph.py"
CLI_DOCS_LINK_SYNC = CLI_PKG / "docs_link_sync.py"

# (service_dir, package_dir)
THIN_SERVICES: tuple[tuple[str, str], ...] = (
    ("memory-service", "memory_service"),
    ("core-data-service", "core_data_service"),
    ("docs-sync-service", "docs_sync_service"),
    ("rule-engine-service", "rule_engine_service"),
    ("orchestration-service", "orchestration_service"),
    ("audit-service", "audit_service"),
    ("adapter-service", "adapter_service"),
    ("identity-access-service", "identity_access_service"),
    ("project-profile-service", "project_profile_service"),
    ("reporting-service", "reporting_service"),
    ("common-context-service", "common_context_service"),
)

# Basenames allowed to reference concrete PostgresStore in thin packages.
THIN_STORE_ALLOWLIST: frozenset[str] = frozenset(
    {"bootstrap.py", "postgres_store.py", "__init__.py", "testing.py"}
)

BANNED_APPLICATION_PATTERNS: tuple[str, ...] = (
    "import neo4j",
    "from neo4j",
    "os.environ",
    "from ..postgres_store import",
    "from ..neo4j_store import",
    "from code_graph_service.postgres_store import",
    "from code_graph_service.neo4j_store import",
)

# Concrete infra clients only (project-profile still reads select env in core for MCP
# export; that is tracked separately from Store/Neo4j/LiteLLM hygiene).
BANNED_THIN_APP_PATTERNS: tuple[str, ...] = (
    "from .postgres_store import",
    "import litellm",
    "from litellm",
    "import neo4j",
    "from neo4j",
)
