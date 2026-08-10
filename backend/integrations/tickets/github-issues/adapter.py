"""GitHub Issues REST create adapter for ExternalTicket dispatch."""

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


class GitHubIssuesTrackerAdapter:
    vendor = "github-issues"

    def __init__(self, token: str, owner: str, repo: str) -> None:
        self.token = token
        self.owner = owner
        self.repo = repo

    def create_remote(self, ticket: Any, connector: Any = None, mapping: Any = None) -> dict[str, Any]:
        _ = (connector, mapping)
        body: dict[str, Any] = {
            "title": ticket.title,
            "body": getattr(ticket, "description_summary", None) or ticket.title,
        }
        labels = getattr(ticket, "labels", None) or []
        if labels:
            body["labels"] = list(labels)
        try:
            data = _http_json(
                "POST",
                f"https://api.github.com/repos/{self.owner}/{self.repo}/issues",
                body,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:500]}
        number = data.get("number")
        if number is None:
            return {"ok": False, "error": "github issues create returned no number"}
        return {
            "ok": True,
            "external_ref": str(number),
            "remote_url": str(data.get("html_url") or ""),
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
        number = getattr(ticket, "external_ref", None)
        if number is None or str(number).strip() == "":
            return {"ok": False, "error": "github issue number missing for status update"}
        lowered = str(vendor_status or "").strip().lower()
        state = "closed" if lowered in {"done", "canceled", "cancelled", "closed", "complete", "completed"} else "open"
        try:
            data = _http_json(
                "PATCH",
                f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{number}",
                {"state": state},
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:500]}
        return {
            "ok": True,
            "external_ref": str(data.get("number") or number),
            "remote_url": str(data.get("html_url") or ""),
            "external_updated_at": _now(),
            "error": None,
        }
