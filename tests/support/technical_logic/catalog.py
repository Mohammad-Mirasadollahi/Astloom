from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class PhaseSlice:
    phase: int
    service: str
    src_path: Path
    test_path: Path
    logic_doc: Path
    pytest_command: str
    check_types: tuple[str, ...]


PHASE_SLICES: tuple[PhaseSlice, ...] = (
    PhaseSlice(
        1,
        "core-data-service",
        ROOT / "backend/services/core-data-service/src",
        ROOT / "tests/backend/services/core-data-service",
        ROOT / "docs/06-technical-logic/01-core-data-model-technical-logic.md",
        "PYTHONPATH=backend/services/core-data-service/src .venv/bin/python -m pytest tests/backend/services/core-data-service",
        ("contract", "state_machine", "idempotency", "redaction"),
    ),
    PhaseSlice(
        2,
        "memory-service",
        ROOT / "backend/services/memory-service/src",
        ROOT / "tests/backend/services/memory-service",
        ROOT / "docs/06-technical-logic/02-memory-context-technical-logic.md",
        "PYTHONPATH=backend/services/memory-service/src .venv/bin/python -m pytest tests/backend/services/memory-service",
        ("contract", "idempotency", "redaction", "retrieval"),
    ),
    PhaseSlice(
        3,
        "docs-sync-service",
        ROOT / "backend/services/docs-sync-service/src",
        ROOT / "tests/backend/services/docs-sync-service",
        ROOT / "docs/06-technical-logic/03-docs-sync-technical-logic.md",
        "PYTHONPATH=backend/services/docs-sync-service/src .venv/bin/python -m pytest tests/backend/services/docs-sync-service",
        ("contract", "docs_drift", "idempotency"),
    ),
    PhaseSlice(
        4,
        "rule-engine-service",
        ROOT / "backend/services/rule-engine-service/src",
        ROOT / "tests/backend/services/rule-engine-service",
        ROOT / "docs/06-technical-logic/04-rules-orchestration-technical-logic.md",
        "PYTHONPATH=backend/services/rule-engine-service/src .venv/bin/python -m pytest tests/backend/services/rule-engine-service",
        ("contract", "rule_evaluation", "idempotency"),
    ),
    PhaseSlice(
        5,
        "adapter-service",
        ROOT / "backend/services/adapter-service/src",
        ROOT / "tests/backend/services/adapter-service",
        ROOT / "docs/06-technical-logic/05-interoperability-technical-logic.md",
        "PYTHONPATH=backend/services/adapter-service/src .venv/bin/python -m pytest tests/backend/services/adapter-service",
        ("contract", "broker_delivery", "idempotency"),
    ),
)


TECHNICAL_LOGIC_DOCS = (
    ROOT / "docs/06-technical-logic/00-index.md",
    ROOT / "docs/06-technical-logic/06-end-to-end-runtime-logic.md",
    ROOT / "docs/06-technical-logic/07-technical-test-strategy.md",
    ROOT / "docs/06-technical-logic/08-feature-specification.md",
    ROOT / "docs/06-technical-logic/12-risks-challenges-and-acceptance.md",
)


def get_slice(phase: int) -> PhaseSlice:
    for item in PHASE_SLICES:
        if item.phase == phase:
            return item
    raise KeyError(f"unknown phase: {phase}")


def required_checks_for_phase(phase: int) -> list[dict[str, str]]:
    item = get_slice(phase)
    return [
        {
            "check_type": check_type,
            "subject_ref": item.service,
            "command": item.pytest_command,
            "documentation_ref": str(item.logic_doc.relative_to(ROOT)),
        }
        for check_type in item.check_types
    ]


def canonical_test_command(phase: int) -> str:
    return get_slice(phase).pytest_command
