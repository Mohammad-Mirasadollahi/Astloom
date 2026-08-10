import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SUPPORT = ROOT / "tests" / "support"
PACKAGES = ROOT / "backend" / "packages"
for path in (SUPPORT, PACKAGES):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from port_profile_gate.catalog import OWNED_SERVICES, REQUIRED_DOCS
from port_profile_gate.checks import run_all_checks
from port_profile_gate.gate import check_phase_gate, explain_failed_check


def test_catalog_covers_owned_runtime_services():
    names = [item.name for item in OWNED_SERVICES]
    assert names == [
        "core-data-service",
        "memory-service",
        "docs-sync-service",
        "rule-engine-service",
        "adapter-service",
        "code-graph-service",
    ]
    assert any(path.name == "34-phase8-verification-and-acceptance.md" for path in REQUIRED_DOCS)


def test_port_profile_gate_passes_documentation_ownership_and_ports():
    decision = check_phase_gate(run_suites=False)
    report = decision.public()
    assert decision.status == "pass", [item.public() for item in decision.checks if item.status == "failed"]
    assert report["blocked"] is False
    assert report["failed_count"] == 0
    assert report["passed_count"] >= 20


def test_port_profile_verification_checks_ports_boundaries_contracts():
    results = run_all_checks()
    assert results
    assert all(item.status == "passed" for item in results), [item.public() for item in results if item.status != "passed"]
    types = {item.check_type for item in results}
    assert {"port_profile", "ownership", "contract"} <= types


def test_waiver_marks_gate_waived_when_forced_failure(monkeypatch):
    from port_profile_gate import gate

    original = gate._path_check

    def flaky(check_id, check_type, subject, path, doc_ref):
        if check_id == "port-profile-doc-1":
            return gate.CheckResult(check_id, check_type, subject, "failed", "forced", [], doc_ref)
        return original(check_id, check_type, subject, path, doc_ref)

    monkeypatch.setattr(gate, "_path_check", flaky)
    decision = check_phase_gate(run_suites=False, waiver_ref="issue:port-profile-temp")
    assert decision.status == "waived"
    explained = explain_failed_check(decision, "port-profile-doc-1")
    assert explained["check"]["status"] == "failed"
