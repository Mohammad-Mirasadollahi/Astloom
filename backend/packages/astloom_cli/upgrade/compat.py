"""Server↔client version compatibility (contract hard, product advisory)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CompatibilityResult:
    ok: bool
    status: str  # compatible | advisory | incompatible
    reason: str
    client: dict[str, str]
    server: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _major(version: str) -> str:
    text = (version or "").strip()
    if not text:
        return ""
    return text.split(".", 1)[0]


def check_compatibility(
    *,
    client_contract: str,
    server_contract: str,
    min_client_contract: str = "",
    client_product: str = "",
    server_product: str = "",
) -> CompatibilityResult:
    """Fail closed when MCP contract majors diverge; product mismatch is advisory."""
    client = {
        "contract_version": (client_contract or "").strip(),
        "product_version": (client_product or "").strip(),
    }
    server = {
        "contract_version": (server_contract or "").strip(),
        "product_version": (server_product or "").strip(),
        "min_client_contract": (min_client_contract or "").strip(),
    }

    if not server["contract_version"]:
        return CompatibilityResult(
            ok=False,
            status="incompatible",
            reason="server did not advertise contract_version",
            client=client,
            server=server,
        )
    if not client["contract_version"]:
        return CompatibilityResult(
            ok=False,
            status="incompatible",
            reason="client contract_version missing",
            client=client,
            server=server,
        )

    min_req = server["min_client_contract"] or server["contract_version"]
    if client["contract_version"] != server["contract_version"]:
        # Allow client ahead of min when majors match min_req major.
        if _major(client["contract_version"]) != _major(min_req):
            return CompatibilityResult(
                ok=False,
                status="incompatible",
                reason=(
                    f"contract mismatch: client={client['contract_version']} "
                    f"server={server['contract_version']} min_client={min_req}"
                ),
                client=client,
                server=server,
            )

    if (
        client["product_version"]
        and server["product_version"]
        and client["product_version"] != server["product_version"]
    ):
        return CompatibilityResult(
            ok=True,
            status="advisory",
            reason=(
                f"product versions differ (client={client['product_version']} "
                f"server={server['product_version']}); upgrade recommended"
            ),
            client=client,
            server=server,
        )

    return CompatibilityResult(
        ok=True,
        status="compatible",
        reason="contract and product aligned",
        client=client,
        server=server,
    )
