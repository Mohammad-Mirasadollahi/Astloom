"""Unit checks for app Docker packaging artifacts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_wheelhouse_script_exists_and_targets_opt() -> None:
    script = ROOT / "scripts" / "build-wheelhouse.sh"
    text = script.read_text(encoding="utf-8")
    assert script.is_file()
    assert "/opt/astloom-wheelhouse" in text
    assert "download" in text
    assert "pip wheel" in text or "wheel --no-deps" in text


def test_mcp_gateway_dockerfile_uses_wheelhouse_context() -> None:
    dockerfile = ROOT / "backend" / "deployments" / "docker" / "Dockerfile.mcp-gateway"
    text = dockerfile.read_text(encoding="utf-8")
    assert "COPY --from=wheelhouse" in text
    assert "--no-index" in text
    assert "--find-links=/opt/astloom-wheelhouse" in text
    assert "common-context-service" in text
    assert "mcp_gateway_service" in text


def test_compose_defines_mcp_gateway_app_profile() -> None:
    compose = ROOT / "backend" / "deployments" / "compose" / "compose.yaml"
    text = compose.read_text(encoding="utf-8")
    assert "mcp-gateway:" in text
    assert 'profiles: ["app", "all"]' in text
    assert "ASTLOOM_POSTGRES_HOST: postgres" in text


def test_app_docker_smoke_script_exists() -> None:
    smoke = ROOT / "tests" / "e2e" / "docker" / "run-app-docker-smoke.sh"
    text = smoke.read_text(encoding="utf-8")
    assert smoke.is_file()
    assert "build-wheelhouse.sh" in text
    assert "/health" in text
    assert "initialize" in text
