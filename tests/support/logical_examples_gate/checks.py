from __future__ import annotations

import sys
from typing import Any

from .catalog import EXAMPLES_CATALOG, ROOT
from .gate import CheckResult


def _ensure_packages_path() -> None:
    packages = str(ROOT / "backend" / "packages")
    if packages not in sys.path:
        sys.path.insert(0, packages)


def verify_examples_catalog_schema() -> list[CheckResult]:
    _ensure_packages_path()
    from logical_examples import load_examples_catalog, validate_examples_catalog

    catalog = load_examples_catalog(EXAMPLES_CATALOG)
    errors = validate_examples_catalog(catalog)
    return [
        CheckResult(
            "examples-catalog-validate",
            "examples_catalog",
            "examples-catalog",
            "passed" if not errors else "failed",
            "ok" if not errors else "; ".join(errors),
            [str(EXAMPLES_CATALOG.relative_to(ROOT))],
            "docs/11-logical-implementation-examples/07-phase11-verification-and-acceptance.md",
        )
    ]


def verify_subsystem_coverage() -> list[CheckResult]:
    _ensure_packages_path()
    from logical_examples import load_examples_catalog

    catalog = load_examples_catalog(EXAMPLES_CATALOG)
    required = {str(item) for item in catalog.get("required_subsystems", [])}
    covered = {str(item.get("subsystem") or "") for item in catalog.get("examples", [])}
    missing = sorted(required - covered)
    return [
        CheckResult(
            "subsystem-examples-coverage",
            "coverage",
            "subsystems",
            "passed" if required and not missing else "failed",
            (
                f"covered={sorted(required & covered)}"
                if required and not missing
                else f"missing={missing or 'no required subsystems'}"
            ),
            sorted(required & covered),
            "docs/11-logical-implementation-examples/00-index.md",
        )
    ]


def verify_example_sections_and_docs() -> list[CheckResult]:
    _ensure_packages_path()
    from logical_examples import load_examples_catalog

    catalog = load_examples_catalog(EXAMPLES_CATALOG)
    results: list[CheckResult] = []
    required_lists = (
        "inputs",
        "processing_steps",
        "outputs",
        "state_changes",
        "edge_cases",
        "implementation_tasks",
        "test_hooks",
    )
    for item in catalog.get("examples", []):
        example_id = str(item.get("example_id") or "unknown")
        doc_path = ROOT / str(item.get("doc_path") or "")
        doc_ok = doc_path.is_file()
        results.append(
            CheckResult(
                f"{example_id}-doc-exists",
                "documentation",
                example_id,
                "passed" if doc_ok else "failed",
                f"{item.get('doc_path')} {'present' if doc_ok else 'missing'}",
                [str(item.get("doc_path") or "")],
                str(item.get("doc_path") or ""),
            )
        )
        missing = [field for field in required_lists if not item.get(field)]
        results.append(
            CheckResult(
                f"{example_id}-runtime-sections",
                "example_shape",
                example_id,
                "passed" if not missing else "failed",
                "sections complete" if not missing else f"missing={missing}",
                list(required_lists),
                str(item.get("doc_path") or ""),
            )
        )
        if doc_ok:
            text = doc_path.read_text(encoding="utf-8").lower()
            edge_ok = "edge cases" in text
            notes_ok = "developer implementation notes" in text
            results.append(
                CheckResult(
                    f"{example_id}-doc-edge-and-notes",
                    "documentation",
                    example_id,
                    "passed" if edge_ok and notes_ok else "failed",
                    (
                        "edge cases and implementation notes present"
                        if edge_ok and notes_ok
                        else f"edge_cases={edge_ok} notes={notes_ok}"
                    ),
                    [str(doc_path.relative_to(ROOT))],
                    str(doc_path.relative_to(ROOT)),
                )
            )
    return results


def verify_checklist_maps_to_tasks() -> list[CheckResult]:
    _ensure_packages_path()
    from logical_examples import load_examples_catalog

    catalog = load_examples_catalog(EXAMPLES_CATALOG)
    checklist = catalog.get("checklist") or {}
    path = ROOT / str(checklist.get("doc_path") or "")
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    sections = checklist.get("subsystem_sections") or []
    missing = [section for section in sections if section.lower() not in text.lower()]
    return [
        CheckResult(
            "checklist-sections-present",
            "checklist",
            "developer-implementation-checklist",
            "passed" if path.is_file() and not missing else "failed",
            "checklist sections present" if path.is_file() and not missing else f"missing={missing}",
            list(sections),
            str(checklist.get("doc_path") or ""),
        ),
        CheckResult(
            "examples-have-test-hooks",
            "mapping",
            "test_hooks",
            "passed" if all(item.get("test_hooks") for item in catalog.get("examples", [])) else "failed",
            "all examples map to test hooks",
            [item["example_id"] for item in catalog.get("examples", [])],
            "docs/11-logical-implementation-examples/07-phase11-verification-and-acceptance.md",
        ),
    ]


def run_all_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(verify_examples_catalog_schema())
    results.extend(verify_subsystem_coverage())
    results.extend(verify_example_sections_and_docs())
    results.extend(verify_checklist_maps_to_tasks())
    return results


def public_results(results: list[CheckResult]) -> list[dict[str, Any]]:
    return [item.public() for item in results]
