"""Tracker adapters for ExternalTicket remote dispatch.

Vendor HTTP implementations live under ``backend/integrations/tickets/``.
This module owns the local adapter, DispatchAck wrapping, and env-gated registry.
"""

from __future__ import annotations

import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

from .core import AdapterMapping, Connector, DispatchAck, ExternalTicket, TicketState, now

_TICKETS_ROOT = Path(__file__).resolve().parents[4] / "integrations" / "tickets"


def portable_to_vendor_status(status: TicketState, mapping: AdapterMapping | None) -> str:
    """Reverse status_map when present; otherwise use the portable value."""
    status_map = (mapping.status_map if mapping and mapping.status_map else {}) or {}
    for vendor_status, portable in status_map.items():
        if portable == status.value:
            return str(vendor_status)
    return status.value


class LocalTrackerAdapter:
    """Deterministic local adapter for mandatory tests without cloud credentials."""

    vendor = "local"

    def create_remote(
        self,
        ticket: ExternalTicket,
        connector: Connector,
        mapping: AdapterMapping,
    ) -> DispatchAck:
        _ = (connector, mapping)
        ref = ticket.external_ref or f"local:{ticket.id}"
        return DispatchAck(
            ok=True,
            external_ref=ref,
            remote_url=ticket.remote_url or f"https://local.tracker.invalid/tickets/{ref}",
            external_updated_at=now(),
        )

    def update_remote_status(
        self,
        ticket: ExternalTicket,
        connector: Connector,
        mapping: AdapterMapping,
        status: TicketState,
    ) -> DispatchAck:
        _ = (connector, mapping, status)
        ref = ticket.external_ref or f"local:{ticket.id}"
        return DispatchAck(
            ok=True,
            external_ref=ref,
            remote_url=ticket.remote_url or f"https://local.tracker.invalid/tickets/{ref}",
            external_updated_at=now(),
        )


class _VendorAdapterBridge:
    """Wrap an integrations adapter that returns a dict into TrackerAdapter/DispatchAck."""

    def __init__(self, vendor: str, impl: Any) -> None:
        self.vendor = vendor
        self._impl = impl

    def create_remote(
        self,
        ticket: ExternalTicket,
        connector: Connector,
        mapping: AdapterMapping,
    ) -> DispatchAck:
        result = self._impl.create_remote(ticket, connector, mapping)
        return self._to_ack(result)

    def update_remote_status(
        self,
        ticket: ExternalTicket,
        connector: Connector,
        mapping: AdapterMapping,
        status: TicketState,
    ) -> DispatchAck:
        updater = getattr(self._impl, "update_remote_status", None)
        if not callable(updater):
            return DispatchAck(ok=False, error=f"{self.vendor} adapter does not support status updates")
        vendor_status = portable_to_vendor_status(status, mapping)
        result = updater(ticket, connector, mapping, vendor_status)
        return self._to_ack(result)

    @staticmethod
    def _to_ack(result: Any) -> DispatchAck:
        if not isinstance(result, dict):
            return DispatchAck(ok=False, error="vendor adapter returned a non-object result")
        return DispatchAck(
            ok=bool(result.get("ok")),
            external_ref=result.get("external_ref"),
            remote_url=result.get("remote_url"),
            external_updated_at=result.get("external_updated_at"),
            error=result.get("error"),
        )


def _load_vendor_class(subdir: str, class_name: str) -> Any:
    path = _TICKETS_ROOT / subdir / "adapter.py"
    spec = spec_from_file_location(f"astloom_tickets_{subdir.replace('-', '_')}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load ticket adapter from {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


def build_tracker_registry(environ: dict[str, str] | None = None) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    registry: dict[str, Any] = {"local": LocalTrackerAdapter()}
    jira_url = str(env.get("ASTLOOM_JIRA_BASE_URL") or "").strip()
    jira_email = str(env.get("ASTLOOM_JIRA_EMAIL") or "").strip()
    jira_token = str(env.get("ASTLOOM_JIRA_API_TOKEN") or "").strip()
    jira_project = str(env.get("ASTLOOM_JIRA_PROJECT_KEY") or "").strip()
    if jira_url and jira_email and jira_token and jira_project:
        cls = _load_vendor_class("jira", "JiraTrackerAdapter")
        registry["jira"] = _VendorAdapterBridge("jira", cls(jira_url, jira_email, jira_token, jira_project))
    linear_key = str(env.get("ASTLOOM_LINEAR_API_KEY") or "").strip()
    linear_team = str(env.get("ASTLOOM_LINEAR_TEAM_ID") or "").strip()
    if linear_key and linear_team:
        cls = _load_vendor_class("linear", "LinearTrackerAdapter")
        registry["linear"] = _VendorAdapterBridge("linear", cls(linear_key, linear_team))
    gh_token = str(env.get("ASTLOOM_GITHUB_TOKEN") or "").strip()
    gh_owner = str(env.get("ASTLOOM_GITHUB_OWNER") or "").strip()
    gh_repo = str(env.get("ASTLOOM_GITHUB_REPO") or "").strip()
    if gh_token and gh_owner and gh_repo:
        cls = _load_vendor_class("github-issues", "GitHubIssuesTrackerAdapter")
        registry["github-issues"] = _VendorAdapterBridge(
            "github-issues", cls(gh_token, gh_owner, gh_repo)
        )
    return registry
