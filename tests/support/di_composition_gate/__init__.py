"""DI composition Phase A verification gate."""

from .checks import run_all_checks
from .gate import check_phase_gate, explain_failed_check

__all__ = ["check_phase_gate", "explain_failed_check", "run_all_checks"]
