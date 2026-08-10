"""Smoke: each FastAPI service package has a python -m entrypoint."""
from pathlib import Path

SERVICES = [
    ("core-data-service", "core_data_service", "ASTLOOM_CORE_DATA_PORT"),
    ("memory-service", "memory_service", "ASTLOOM_MEMORY_PORT"),
    ("docs-sync-service", "docs_sync_service", "ASTLOOM_DOCS_SYNC_PORT"),
    ("code-graph-service", "code_graph_service", "ASTLOOM_CODE_GRAPH_PORT"),
    ("rule-engine-service", "rule_engine_service", "ASTLOOM_RULE_ENGINE_PORT"),
    ("adapter-service", "adapter_service", "ASTLOOM_ADAPTER_PORT"),
    ("audit-service", "audit_service", "ASTLOOM_AUDIT_PORT"),
    ("identity-access-service", "identity_access_service", "ASTLOOM_IDENTITY_ACCESS_PORT"),
    ("orchestration-service", "orchestration_service", "ASTLOOM_ORCHESTRATION_PORT"),
    ("reporting-service", "reporting_service", "ASTLOOM_REPORTING_PORT"),
    ("project-profile-service", "project_profile_service", "ASTLOOM_PROJECT_PROFILE_PORT"),
    ("common-context-service", "common_context_service", "ASTLOOM_COMMON_CONTEXT_PORT"),
]

ROOT = Path(__file__).resolve().parents[3] / "backend" / "services"


def test_service_main_entrypoints():
    for service_dir, pkg, env in SERVICES:
        main = ROOT / service_dir / "src" / pkg / "__main__.py"
        text = main.read_text()
        assert f"{pkg}.api:app" in text
        assert "factory=True" in text
        assert env in text
