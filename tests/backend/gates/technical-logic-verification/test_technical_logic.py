import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SUPPORT = ROOT / "tests" / "support"
if str(SUPPORT) not in sys.path:
    sys.path.insert(0, str(SUPPORT))

from technical_logic.catalog import PHASE_SLICES, canonical_test_command, required_checks_for_phase
from technical_logic.checks import run_all_checks
from technical_logic.gate import check_phase_gate, explain_failed_check
from technical_logic.runtime_scenario import run_runtime_scenario


def test_catalog_covers_owned_services():
    assert [item.service for item in PHASE_SLICES] == [
        "core-data-service",
        "memory-service",
        "docs-sync-service",
        "rule-engine-service",
        "adapter-service",
    ]
    checks = required_checks_for_phase(1)
    assert checks[0]["command"] == canonical_test_command(1)
    assert "core-data-service" in checks[0]["subject_ref"]


def test_technical_logic_gate_passes_path_and_readme_checks():
    decision = check_phase_gate(run_suites=False)
    report = decision.public()
    assert decision.status == "pass"
    assert report["blocked"] is False
    assert report["passed_count"] >= 15
    assert report["failed_count"] == 0


def test_verification_checks_contracts_state_idempotency_redaction():
    results = run_all_checks()
    assert results
    assert all(item.status == "passed" for item in results)
    types = {item.check_type for item in results}
    assert {
        "contract",
        "state_machine",
        "idempotency",
        "redaction",
        "retrieval",
        "docs_drift",
        "rule_evaluation",
        "broker_delivery",
        "catalog_coverage",
    } <= types
    subjects = {item.subject_ref for item in results if item.check_type == "broker_delivery"}
    assert "adapter-service" in subjects


def test_runtime_scenario_stitches_services_with_shared_correlation():
    report = run_runtime_scenario("corr-technical-logic-test")
    assert report.status == "passed"
    assert report.correlation_id == "corr-technical-logic-test"
    services = {step["service"] for step in report.steps}
    assert services == {
        "core-data-service",
        "memory-service",
        "docs-sync-service",
        "rule-engine-service",
        "adapter-service",
    }
    assert report.steps[3]["blocked"] is True
    assert {"marketing", "support", "devops"} <= set(report.steps[4]["departments"])


def test_waiver_marks_gate_waived_when_forced_failure(monkeypatch):
    from technical_logic import gate

    original = gate._path_check

    def flaky(check_id, check_type, subject, path, doc_ref):
        if check_id == "technical-logic-doc-1":
            from technical_logic.gate import CheckResult

            return CheckResult(check_id, check_type, subject, "failed", "forced", [], doc_ref)
        return original(check_id, check_type, subject, path, doc_ref)

    monkeypatch.setattr(gate, "_path_check", flaky)
    decision = check_phase_gate(run_suites=False, waiver_ref="issue:technical-logic-temp")
    assert decision.status == "waived"
    explained = explain_failed_check(decision, "technical-logic-doc-1")
    assert explained["check"]["status"] == "failed"
