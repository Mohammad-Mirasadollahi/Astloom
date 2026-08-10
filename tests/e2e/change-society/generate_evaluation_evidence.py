#!/usr/bin/env python3
"""Write redacted seven-scenario evaluation and ablation evidence for Phase 7 gates."""

from __future__ import annotations

import json
from pathlib import Path
import sys

_SUPPORT = Path(__file__).resolve().parents[2] / "support"
if str(_SUPPORT) not in sys.path:
    sys.path.insert(0, str(_SUPPORT))
from hackathon_pack import init_script  # noqa: E402

PACK = init_script(__file__)

from change_society.application.control_plane import AgentControlPlane, AgentTemplate, CapabilityRouter  # noqa: E402
from change_society.application.ablation import aggregate_benchmark_rows  # noqa: E402
from change_society.application.service import ChangeSocietyService  # noqa: E402
from change_society.domain.models import Scope  # noqa: E402
from change_society.infrastructure.agent_adapters import ModelAgentAdapter, StaticAgentAdapterRegistry  # noqa: E402
from change_society.infrastructure.control_plane_repositories import InMemoryControlPlaneRepository  # noqa: E402
from change_society.infrastructure.evidence_catalog import DEMO_SCENARIO_IDS, ScenarioEvidenceProvider  # noqa: E402
from change_society.infrastructure.fake_model import DeterministicModelClient  # noqa: E402
from change_society.infrastructure.repositories import InMemoryRunRepository  # noqa: E402

OUTPUT = PACK / "evidence/real/evaluation-scenarios.json"
SUMMARY = PACK / "evidence/real/benchmark-summary.json"


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
    return ChangeSocietyService(InMemoryRunRepository(), model, ScenarioEvidenceProvider(), clock, ids, control, 1800)


def main() -> int:
    service = make_service()
    scope = Scope("tenant-a", "workspace-a", "project-a")
    rows = []
    for index, scenario_id in enumerate(DEMO_SCENARIO_IDS):
        run = service.create_run(scope, "developer-a", f"evidence-{scenario_id}", f"evidence-{index}", scenario_id, None)
        comparison = service.evaluate_baseline(scope, run.run_id)
        rows.append(
            {
                "scenario_id": scenario_id,
                "run_id": run.run_id,
                "society_metrics": comparison["society"],
                "baseline_metrics": comparison["baseline"],
                "tradeoffs": comparison["tradeoffs"],
                "ablation": comparison["ablation"],
                "efficiency": comparison["ablation"]["efficiency"],
                "caveat": comparison["caveat"],
            }
        )
    aggregate = aggregate_benchmark_rows(
        [
            {
                "evaluation": {
                    "baseline": row["baseline_metrics"],
                    "society": row["society_metrics"],
                    "ablation": row["ablation"],
                }
            }
            for row in rows
        ]
    )
    payload = {
        "scenarios": rows,
        "sample_count": len(rows),
        "aggregate": aggregate,
        "caveat": aggregate["caveat"],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"Wrote {SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
