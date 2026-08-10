import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SUPPORT = ROOT / "tests" / "support"
PACKAGES = ROOT / "backend" / "packages"
for path in (SUPPORT, PACKAGES):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from governance_catalog_gate.catalog import REQUIRED_DOCS
from governance_catalog_gate.checks import run_all_checks
from governance_catalog_gate.gate import check_phase_gate, explain_failed_check


def test_catalog_includes_acceptance_doc():
    assert any(path.name == "11-phase9-verification-and-acceptance.md" for path in REQUIRED_DOCS)


def test_governance_catalog_gate_passes_docs_and_catalogs():
    decision = check_phase_gate()
    assert decision.status == "pass", [item.public() for item in decision.checks if item.status == "failed"]
    report = decision.public()
    assert report["blocked"] is False
    assert report["failed_count"] == 0
    assert report["passed_count"] >= 20


def test_governance_catalog_verification_checks_risks_and_kpis():
    results = run_all_checks()
    assert results
    assert all(item.status == "passed" for item in results), [item.public() for item in results if item.status != "passed"]
    types = {item.check_type for item in results}
    assert {"governance_catalog", "ownership", "reporting"} <= types


def test_waiver_marks_gate_waived_when_forced_failure(monkeypatch):
    from governance_catalog_gate import gate

    original = gate._path_check

    def flaky(check_id, check_type, subject, path, doc_ref):
        if check_id == "governance-catalog-doc-1":
            return gate.CheckResult(check_id, check_type, subject, "failed", "forced", [], doc_ref)
        return original(check_id, check_type, subject, path, doc_ref)

    monkeypatch.setattr(gate, "_path_check", flaky)
    decision = check_phase_gate(waiver_ref="issue:governance-catalog-temp")
    assert decision.status == "waived"
    explained = explain_failed_check(decision, "governance-catalog-doc-1")
    assert explained["check"]["status"] == "failed"
