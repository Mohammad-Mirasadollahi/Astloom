"""Technical logic verification harness for owned vertical-slice services."""
from .catalog import PHASE_SLICES, required_checks_for_phase
from .gate import PhaseGateDecision, check_phase_gate
from .runtime_scenario import RuntimeScenarioReport, run_runtime_scenario

__all__ = [
    "PHASE_SLICES",
    "PhaseGateDecision",
    "RuntimeScenarioReport",
    "check_phase_gate",
    "required_checks_for_phase",
    "run_runtime_scenario",
]
