"""Jira HTTP create adapter for ExternalTicket dispatch."""

from __future__ import annotations

from base64 import b64encode
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


class JiraTrackerAdapter:
    vendor = "jira"

    def __init__(self, base_url: str, email: str, api_token: str, project_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.project_key = project_key

    def create_remote(self, ticket: Any, connector: Any = None, mapping: Any = None) -> dict[str, Any]:
        _ = (connector, mapping)
        body = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": ticket.title,
                "description": getattr(ticket, "description_summary", None) or ticket.title,
                "issuetype": {"name": "Task"},
            }
        }
        try:
            data = _http_json(
                "POST",
                f"{self.base_url}/rest/api/2/issue",
                body,
                headers={
                    "Authorization": "Basic "
                    + b64encode(f"{self.email}:{self.api_token}".encode()).decode(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:500]}
        key = str(data.get("key") or data.get("id") or "")
        if not key:
            return {"ok": False, "error": "jira create returned no issue key"}
        return {
            "ok": True,
            "external_ref": key,
            "remote_url": f"{self.base_url}/browse/{key}",
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
        issue_key = getattr(ticket, "external_ref", None) or ""
        if not issue_key:
            return {"ok": False, "error": "jira issue key missing for status update"}
        auth = {
            "Authorization": "Basic " + b64encode(f"{self.email}:{self.api_token}".encode()).decode(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            transitions = _http_json(
                "GET",
                f"{self.base_url}/rest/api/2/issue/{issue_key}/transitions",
                None,
                headers=auth,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:500]}
        wanted = str(vendor_status or "").strip().lower()
        transition_id = None
        for item in transitions.get("transitions") or []:
            name = str(item.get("name") or "").strip().lower()
            to_name = str(((item.get("to") or {}).get("name")) or "").strip().lower()
            if wanted and wanted in {name, to_name}:
                transition_id = item.get("id")
                break
        if transition_id is None and wanted in {"done", "closed", "complete", "completed"}:
            for item in transitions.get("transitions") or []:
                name = str(item.get("name") or "").strip().lower()
                if any(token in name for token in ("done", "close", "resolve")):
                    transition_id = item.get("id")
                    break
        if transition_id is None:
            return {"ok": False, "error": f"jira transition not found for status {vendor_status!r}"}
        try:
            _http_json(
                "POST",
                f"{self.base_url}/rest/api/2/issue/{issue_key}/transitions",
                {"transition": {"id": transition_id}},
                headers=auth,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:500]}
        return {
            "ok": True,
            "external_ref": issue_key,
            "remote_url": f"{self.base_url}/browse/{issue_key}",
            "external_updated_at": _now(),
            "error": None,
        }
