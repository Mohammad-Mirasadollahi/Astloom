from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CATALOG_DIR = Path(__file__).resolve().parents[2] / "configs" / "logical-examples"
EXAMPLES_CATALOG_PATH = CATALOG_DIR / "examples-catalog.json"

REQUIRED_EXAMPLE_LIST_FIELDS = (
    "inputs",
    "processing_steps",
    "outputs",
    "state_changes",
    "edge_cases",
    "implementation_tasks",
    "test_hooks",
)

REQUIRED_EXAMPLE_SCALAR_FIELDS = (
    "example_id",
    "title",
    "subsystem",
    "doc_path",
)


class LogicalExamplesError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise LogicalExamplesError(f"catalog missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise LogicalExamplesError(f"catalog must be an object: {path}")
    return data


def load_examples_catalog(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or EXAMPLES_CATALOG_PATH)


def validate_examples_catalog(catalog: dict[str, Any]) -> list[str]:
    """Validate Phase 11 exit criteria for logical examples."""
    errors: list[str] = []
    required = catalog.get("required_subsystems")
    if not isinstance(required, list) or not required:
        errors.append("required_subsystems list is required")
        required_set: set[str] = set()
    else:
        required_set = {str(item) for item in required}

    examples = catalog.get("examples")
    if not isinstance(examples, list) or not examples:
        errors.append("examples list is required")
        return errors

    seen_ids: set[str] = set()
    covered: set[str] = set()
    for item in examples:
        if not isinstance(item, dict):
            errors.append("example entry must be an object")
            continue
        example_id = str(item.get("example_id") or "").strip()
        if not example_id:
            errors.append("example missing example_id")
            continue
        if example_id in seen_ids:
            errors.append(f"duplicate example_id: {example_id}")
        seen_ids.add(example_id)

        for field in REQUIRED_EXAMPLE_SCALAR_FIELDS:
            if not str(item.get(field) or "").strip():
                errors.append(f"{example_id} missing {field}")

        subsystem = str(item.get("subsystem") or "").strip()
        if subsystem:
            covered.add(subsystem)

        for field in REQUIRED_EXAMPLE_LIST_FIELDS:
            values = item.get(field)
            if not isinstance(values, list) or not values:
                errors.append(f"{example_id} missing non-empty {field}")
            elif not all(str(v).strip() for v in values):
                errors.append(f"{example_id} {field} contains empty values")

    missing_subsystems = sorted(required_set - covered)
    if missing_subsystems:
        errors.append(f"missing subsystem examples: {', '.join(missing_subsystems)}")

    checklist = catalog.get("checklist")
    if not isinstance(checklist, dict):
        errors.append("checklist object is required")
    else:
        if not str(checklist.get("doc_path") or "").strip():
            errors.append("checklist missing doc_path")
        sections = checklist.get("subsystem_sections")
        if not isinstance(sections, list) or len(sections) < 5:
            errors.append("checklist.subsystem_sections must cover major subsystems")

    return errors
