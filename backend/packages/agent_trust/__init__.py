"""Agent trust helpers (GAP-A05).

Re-exports architecture_governance trust APIs under the plan package name.
"""

from __future__ import annotations

from architecture_governance import (
    ArchitectureGovernanceError,
    apply_trust_transition,
    load_agent_trust_policy,
    provider_rank,
    trust_allows_high_risk,
    trust_rank,
)

__all__ = [
    "ArchitectureGovernanceError",
    "apply_trust_transition",
    "load_agent_trust_policy",
    "provider_rank",
    "trust_allows_high_risk",
    "trust_rank",
]
