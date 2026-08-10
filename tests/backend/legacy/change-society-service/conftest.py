"""Shared fixtures for change-society-service tests."""

from __future__ import annotations

import os
from pathlib import Path

from change_society.application.control_plane import AgentControlPlane, AgentTemplate, CapabilityRouter
from change_society.application.service import ChangeSocietyService
from change_society.domain.models import Scope
from change_society.infrastructure.agent_adapters import ModelAgentAdapter, StaticAgentAdapterRegistry
from change_society.infrastructure.control_plane_repositories import InMemoryControlPlaneRepository
from change_society.infrastructure.evidence_catalog import ScenarioEvidenceProvider
from change_society.infrastructure.fake_model import DeterministicModelClient
from change_society.infrastructure.repositories import InMemoryRunRepository

_HACKATHON_ENV = Path(__file__).resolve().parents[4] / "archives" / "hackathon" / ".env"


def _load_hackathon_env() -> None:
    if not _HACKATHON_ENV.is_file():
        return
    for raw in _HACKATHON_ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_hackathon_env()


class FixedClock:
    def __init__(self) -> None:
        self.value = 0

    def now(self) -> str:
        self.value += 1
        return f"2026-07-11T00:00:{self.value:02d}+00:00"


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def new(self, prefix: str) -> str:
        self.value += 1
        return f"{prefix}_{self.value}"


def make_service() -> ChangeSocietyService:
    model = DeterministicModelClient()
    clock = FixedClock()
    ids = SequenceIds()
    templates = tuple(
        AgentTemplate(key, name, "test", "model", (capability,), role, name)
        for key, name, capability, role in (
            ("context", "Context Scout", "retrieve_scoped_project_truth", "context_scout"),
            ("change", "Change Analyst", "interpret_ambiguous_software_change", "change_analyst"),
            ("impact", "Impact Analyst", "analyze_cross_boundary_impact", "impact_analyst"),
            ("policy", "Policy Guardian", "evaluate_policy_and_approval_risk", "policy_guardian"),
            ("judge", "Conflict Judge", "decompose_route_reconcile", "coordinator_judge"),
            ("frontend", "Frontend Delivery Coordinator", "coordinate_frontend_ui_delivery", "frontend_delivery_lead"),
        )
    )
    control = AgentControlPlane(
        InMemoryControlPlaneRepository(),
        StaticAgentAdapterRegistry({"model": ModelAgentAdapter(model)}),
        CapabilityRouter(),
        clock,
        ids,
        templates,
    )
    return ChangeSocietyService(
        InMemoryRunRepository(),
        model,
        ScenarioEvidenceProvider(),
        clock,
        ids,
        control,
        1800,
    )


SCOPE = Scope("tenant-a", "workspace-a", "project-a")
HEADERS = {
    "X-Tenant-Id": "tenant-a",
    "X-Workspace-Id": "workspace-a",
    "X-Actor-Id": "developer-a",
    "Idempotency-Key": "create-1",
    "X-Correlation-Id": "corr-test",
}
