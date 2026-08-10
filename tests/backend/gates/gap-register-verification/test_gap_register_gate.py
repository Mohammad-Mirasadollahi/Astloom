import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SUPPORT = ROOT / "tests" / "support"
PACKAGES = ROOT / "backend" / "packages"
for path in (SUPPORT, PACKAGES):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import governance_catalog
from gap_register_gate.catalog import REQUIRED_DOCS
from gap_register_gate.checks import run_all_checks
from gap_register_gate.gate import check_phase_gate, explain_failed_check


def test_catalog_includes_acceptance_doc():
    assert any(path.name == "06-phase10-verification-and-acceptance.md" for path in REQUIRED_DOCS)


def test_gap_register_gate_passes_docs_and_register():
    decision = check_phase_gate()
    assert decision.status == "pass", [item.public() for item in decision.checks if item.status == "failed"]
    report = decision.public()
    assert report["blocked"] is False
    assert report["failed_count"] == 0
    assert report["passed_count"] >= 15


def test_gap_register_verification_checks_exit_criteria():
    results = run_all_checks()
    assert results
    assert all(item.status == "passed" for item in results), [
        item.public() for item in results if item.status != "passed"
    ]
    types = {item.check_type for item in results}
    assert {"governance_catalog", "ownership", "triage", "documentation"} <= types
    assert any(item.check_id == "register-md-status-matches-catalog" for item in results)


def test_accepted_risks_check_passes_when_none(monkeypatch):
    from gap_register_gate import checks

    monkeypatch.setattr(
        governance_catalog,
        "load_gap_register",
        lambda _path=None: {"gaps": [{"gap_id": "GAP-X", "status": "CLOSED"}]},
    )
    results = checks.verify_accepted_risks_have_approvers()
    assert len(results) == 1
    assert results[0].status == "passed"
    assert results[0].message == "accepted=0 review_ok"


def test_register_md_status_matches_catalog():
    from gap_register_gate.checks import verify_register_md_statuses_match_catalog

    results = verify_register_md_statuses_match_catalog()
    assert len(results) == 1
    assert results[0].status == "passed", results[0].message


def test_waiver_marks_gate_waived_when_forced_failure(monkeypatch):
    from gap_register_gate import gate

    original = gate._path_check

    def flaky(check_id, check_type, subject, path, doc_ref):
        if check_id == "gap-register-doc-1":
            return gate.CheckResult(check_id, check_type, subject, "failed", "forced", [], doc_ref)
        return original(check_id, check_type, subject, path, doc_ref)

    monkeypatch.setattr(gate, "_path_check", flaky)
    decision = check_phase_gate(waiver_ref="issue:gap-register-temp")
    assert decision.status == "waived"
    explained = explain_failed_check(decision, "gap-register-doc-1")
    assert explained["check"]["status"] == "failed"
