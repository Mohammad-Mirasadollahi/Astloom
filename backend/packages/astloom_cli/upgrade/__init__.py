"""Software upgrade: compatibility, local install, client refresh, control-plane jobs."""

from __future__ import annotations

from astloom_cli.upgrade.compat import CompatibilityResult, check_compatibility
from astloom_cli.upgrade.engine import (
    UpgradeError,
    create_upgrade_plan,
    finalize_upgrade_job,
    load_upgrade_job,
    prepare_upgrade_job,
    rollback_upgrade_job,
    run_client_upgrade,
    run_upgrade_job,
    write_evidence_report,
)
from astloom_cli.upgrade.versions import (
    CONTRACT_VERSION,
    MIN_CLIENT_CONTRACT,
    PRODUCT_VERSION,
    read_install_versions,
    server_version_payload,
)

__all__ = [
    "CONTRACT_VERSION",
    "CompatibilityResult",
    "MIN_CLIENT_CONTRACT",
    "PRODUCT_VERSION",
    "UpgradeError",
    "check_compatibility",
    "create_upgrade_plan",
    "finalize_upgrade_job",
    "load_upgrade_job",
    "prepare_upgrade_job",
    "read_install_versions",
    "rollback_upgrade_job",
    "run_client_upgrade",
    "run_upgrade_job",
    "server_version_payload",
    "write_evidence_report",
]
