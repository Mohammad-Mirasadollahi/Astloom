import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SUPPORT = ROOT / "tests" / "support"
for path in (SUPPORT,):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from di_composition_gate.catalog import REQUIRED_DOCS
from di_composition_gate.checks import run_all_checks
from di_composition_gate.gate import check_phase_gate, explain_failed_check


def test_catalog_includes_migration_docs():
    names = {path.name for path in REQUIRED_DOCS}
    assert "45-backend-di-composition-feature-specification.md" in names
    assert "30-dependency-injection-and-composition-root.md" in names


def test_di_composition_gate_passes_phase_a_d():
    decision = check_phase_gate()
    assert decision.status == "pass", [
        item.public() for item in decision.checks if item.status == "failed"
    ]
    report = decision.public()
    assert report["blocked"] is False
    assert report["failed_count"] == 0
    assert report["passed_count"] >= 14
    ids = {item.check_id for item in decision.checks}
    assert "di-thin-ports-phase-c" in ids
    assert "di-cli-process-containers-phase-d" in ids


def test_di_composition_checks_cover_composition_and_imports():
    results = run_all_checks()
    assert results
    assert all(item.status == "passed" for item in results), [
        item.public() for item in results if item.status != "passed"
    ]
    types = {item.check_type for item in results}
    assert {"documentation", "composition", "import_boundary"} <= types


def test_waiver_marks_gate_waived_when_forced_failure(monkeypatch):
    from di_composition_gate import gate

    original = gate.check_phase_gate

    def flaky(**kwargs):
        decision = original(**kwargs)
        # Force one failure via monkeypatch on checks instead
        return decision

    # Directly force a failed check in run_all_checks
    from di_composition_gate import checks

    real = checks.verify_docs_exist

    def bad_docs():
        items = real()
        items[0].status = "failed"
        items[0].detail = "forced"
        return items

    monkeypatch.setattr(checks, "verify_docs_exist", bad_docs)
    decision = check_phase_gate(waiver_ref="issue:di-composition-temp")
    assert decision.status == "waived"
    explained = explain_failed_check(decision, "di-doc-1")
    assert explained["check"]["status"] == "failed"
