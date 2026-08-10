"""Linear GraphQL create adapter for ExternalTicket dispatch."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any


def _http_json(method: str, url: str, body: dict[str, Any] | None, *, headers: dict[str, str]) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "_http.py"
    spec = spec_from_file_location("astloom_tickets_http", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load tickets HTTP helper")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.http_json(method, url, body, headers=headers)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class LinearTrackerAdapter:
    vendor = "linear"

    def __init__(self, api_key: str, team_id: str) -> None:
        self.api_key = api_key
        self.team_id = team_id

    def create_remote(self, ticket: Any, connector: Any = None, mapping: Any = None) -> dict[str, Any]:
        _ = (connector, mapping)
        query = """
        mutation IssueCreate($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue { id identifier url }
          }
        }
        """
        variables = {
            "input": {
                "teamId": self.team_id,
                "title": ticket.title,
                "description": getattr(ticket, "description_summary", None) or ticket.title,
            }
        }
        try:
            data = _http_json(
                "POST",
                "https://api.linear.app/graphql",
                {"query": query, "variables": variables},
                headers={
                    "Authorization": self.api_key,
                    "Content-Type": "application/json",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:500]}
        payload = ((data.get("data") or {}).get("issueCreate") or {})
        issue = payload.get("issue") or {}
        if not payload.get("success") or not issue.get("id"):
            return {"ok": False, "error": "linear issueCreate failed"}
        return {
            "ok": True,
            "external_ref": str(issue.get("identifier") or issue.get("id")),
            "remote_url": str(issue.get("url") or ""),
            "external_updated_at": _now(),
            "error": None,
        }

    def update_remote_status(
        self,
        ticket: Any,
        connector: Any = None,
        mapping: Any = None,
        vendor_status: str = "",
    ) -> dict[str, Any]:
        _ = (connector, mapping)
        issue_id = getattr(ticket, "external_ref", None) or ""
        if not issue_id:
            return {"ok": False, "error": "linear issue id missing for status update"}
        # Linear GraphQL accepts state by name via issueUpdate when configured with a stateId;
        # sandbox uses state name lookup through workflow states when only a portable/vendor label is known.
        query = """
        mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue { id identifier url }
          }
        }
        """
        # Prefer treating vendor_status as a state name stored in extension-compatible field.
        state_id = None
        extension = getattr(ticket, "extension", None) or {}
        if isinstance(extension, dict):
            state_id = extension.get("linear_state_id")
        input_body: dict[str, Any] = {}
        if state_id:
            input_body["stateId"] = state_id
        else:
            # Best-effort: Linear accepts some teams' state names via description annotation only;
            # without stateId, record a failed update rather than inventing IDs.
            lowered = str(vendor_status or "").strip().lower()
            if lowered in {"done", "completed", "canceled", "cancelled"}:
                return {"ok": False, "error": "linear status update requires extension.linear_state_id"}
            return {"ok": False, "error": "linear status update requires extension.linear_state_id"}
        try:
            data = _http_json(
                "POST",
                "https://api.linear.app/graphql",
                {"query": query, "variables": {"id": issue_id, "input": input_body}},
                headers={
                    "Authorization": self.api_key,
                    "Content-Type": "application/json",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:500]}
        payload = ((data.get("data") or {}).get("issueUpdate") or {})
        issue = payload.get("issue") or {}
        if not payload.get("success"):
            return {"ok": False, "error": "linear issueUpdate failed"}
        return {
            "ok": True,
            "external_ref": str(issue.get("identifier") or issue.get("id") or issue_id),
            "remote_url": str(issue.get("url") or ""),
            "external_updated_at": _now(),
            "error": None,
        }
