"""Estimate and report Astloom MCP token cost for coding-agent clients."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, NamedTuple

from astloom_cli.mcp_client_targets import (
    MCP_CLIENT_BY_ID,
    config_paths_for_clients,
    resolve_client_ids,
)
from astloom_cli.mcp_usage_log import approx_tokens_from_obj, load_mcp_usage_events
from astloom_cli.util import repo_root
from usage_profile import load_usage_profile


class TimeRange(NamedTuple):
    start: datetime
    end: datetime
    label: str


_REL = re.compile(r"^(\d+)(h|d|w|m)$", re.I)


def parse_time_range(since: str | None, until: str | None) -> TimeRange:
    now = datetime.now(timezone.utc)
    end = _parse_iso(until) if until else now
    if since:
        m = _REL.match(since.strip())
        if m:
            n, unit = int(m.group(1)), m.group(2).lower()
            delta = {
                "h": timedelta(hours=n),
                "d": timedelta(days=n),
                "w": timedelta(weeks=n),
                "m": timedelta(days=n * 30),
            }[unit]
            start = end - delta
            label = f"last {since}"
        else:
            start = _parse_iso(since)
            label = f"{start.date().isoformat()} → {end.date().isoformat()}"
    else:
        start = end - timedelta(days=7)
        label = "last 7d (default)"
    if start > end:
        start, end = end, start
    return TimeRange(start=start, end=end, label=label)


def _parse_iso(value: str) -> datetime:
    text = value.strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return datetime.fromisoformat(text + "T00:00:00").replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def resolve_scope_ids(raw: str | None) -> list[str] | None:
    """None = all scopes. Otherwise normalized tenant/workspace/project list."""
    text = (raw or "all").strip()
    if text.lower() in ("all", "*", ""):
        return None
    out: list[str] = []
    seen: set[str] = set()
    for part in text.split(","):
        scope = part.strip().strip("/")
        if not scope:
            continue
        key = scope.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(scope)
    if not out:
        return None
    return out


def estimate_connect(profile_id: str) -> dict[str, Any]:
    from mcp_gateway_service.lazy_facade import lazy_tools_list

    profile = load_usage_profile(profile_id)
    server_name = str((profile.get("mcp") or {}).get("server_name") or "Astloom-Programming")
    lazy = lazy_tools_list(server_name=server_name)
    catalog = [
        {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["input_schema"],
        }
        for t in (profile.get("mcp") or {}).get("tools") or []
    ]
    lazy_tokens = approx_tokens_from_obj({"tools": lazy})
    catalog_tokens = approx_tokens_from_obj({"tools": catalog})
    heavy = _heavy_tool_estimates(profile)
    return {
        "usage_profile": profile_id,
        "server_name": server_name,
        "tool_count_catalog": len(catalog),
        "connect": {
            "lazy_tools_list_tokens": lazy_tokens,
            "full_catalog_tools_list_tokens": catalog_tokens,
            "saved_vs_full_catalog": max(0, catalog_tokens - lazy_tokens),
            "note": (
                "Cursor loads tools/list into agent context. Astloom exposes "
                "mcp-lazy facade (2 tools); full catalog stays behind search."
            ),
        },
        "heavy_tools": heavy,
    }


def _heavy_tool_estimates(profile: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tools = (profile.get("mcp") or {}).get("tools") or []
    # Schema-only cost for every tool (what search returns when matched).
    schema_costs = []
    for tool in tools:
        schema_tokens = approx_tokens_from_obj(
            {
                "tool_name": tool.get("name"),
                "description": tool.get("description"),
                "inputSchema": tool.get("input_schema"),
            }
        )
        schema_costs.append((schema_tokens, str(tool.get("name") or "")))
    schema_costs.sort(reverse=True)
    for tokens, name in schema_costs[:8]:
        rows.append({"tool": name, "kind": "search_hit_schema", "tokens_est": tokens})

    # Static full-tier authoring payload (often large).
    try:
        from common_context_service.documentation_authoring_law import authoring_law_payload

        payload_tokens = approx_tokens_from_obj(authoring_law_payload())
        rows.append(
            {
                "tool": "astloom_docs_authoring_standards",
                "kind": "full_response",
                "tokens_est": payload_tokens,
            }
        )
    except Exception:
        pass

    try:
        from astloom_cli.docs_catalog import SCHEMA_VERSION

        enum_tokens = approx_tokens_from_obj(
            {
                "mode": "docs_catalog",
                "schema_version": SCHEMA_VERSION,
                "vocabulary_source": "observed_frontmatter",
            }
        )
        rows.append(
            {
                "tool": "astloom_docs_catalog",
                "kind": "full_response",
                "tokens_est": max(enum_tokens, 200),
            }
        )
    except Exception:
        pass

    # Effective profile dump size.
    rows.append(
        {
            "tool": "astloom_get_effective_profile",
            "kind": "full_response",
            "tokens_est": approx_tokens_from_obj(profile),
        }
    )
    rows.sort(key=lambda r: int(r["tokens_est"]), reverse=True)
    return rows


def client_wiring(
    client_ids: list[str],
    *,
    project_dir: Path,
    server_name: str,
    include_user: bool = True,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cid, path in config_paths_for_clients(
        project_dir, client_ids, include_user=include_user
    ):
        wired = False
        if path.is_file():
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                servers = doc.get(MCP_CLIENT_BY_ID[cid].servers_key) or {}
                wired = server_name in servers
            except Exception:
                wired = False
        rows.append(
            {
                "client_id": cid,
                "title": MCP_CLIENT_BY_ID[cid].title,
                "config_path": str(path),
                "wired": wired,
            }
        )
    # Clients that resolve to no path (skipped user without include) still listed.
    seen = {r["client_id"] for r in rows}
    for cid in client_ids:
        if cid in seen:
            continue
        target = MCP_CLIENT_BY_ID.get(cid)
        if not target:
            continue
        rows.append(
            {
                "client_id": cid,
                "title": target.title,
                "config_path": "",
                "wired": False,
            }
        )
    return rows


def aggregate_history(
    events: list[dict[str, Any]],
    *,
    client_ids: list[str] | None,
    scope_ids: list[str] | None,
) -> dict[str, Any]:
    client_set = {c.lower() for c in client_ids} if client_ids is not None else None
    scope_set = {s.lower() for s in scope_ids} if scope_ids is not None else None

    by_client: dict[str, dict[str, int]] = defaultdict(
        lambda: {"calls": 0, "tokens_in": 0, "tokens_out": 0}
    )
    by_scope: dict[str, dict[str, int]] = defaultdict(
        lambda: {"calls": 0, "tokens_in": 0, "tokens_out": 0}
    )
    by_tool: dict[str, dict[str, int]] = defaultdict(
        lambda: {"calls": 0, "tokens_in": 0, "tokens_out": 0}
    )
    totals = {"calls": 0, "tokens_in": 0, "tokens_out": 0}

    for row in events:
        client = str(row.get("client_id") or "unknown").strip() or "unknown"
        scope = str(row.get("scope") or "unknown").strip() or "unknown"
        if client_set is not None and client.lower() not in client_set:
            continue
        if scope_set is not None and scope.lower() not in scope_set:
            continue
        tin = int(row.get("tokens_in") or 0)
        tout = int(row.get("tokens_out") or 0)
        tool = str(row.get("tool") or row.get("event") or "unknown")
        for bucket in (by_client[client], by_scope[scope], by_tool[tool], totals):
            bucket["calls"] += 1
            bucket["tokens_in"] += tin
            bucket["tokens_out"] += tout

    def _sorted(d: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
        return dict(
            sorted(
                d.items(),
                key=lambda kv: kv[1]["tokens_out"] + kv[1]["tokens_in"],
                reverse=True,
            )
        )

    return {
        "totals": totals,
        "by_client_id": _sorted(by_client),
        "by_scope_id": _sorted(by_scope),
        "by_tool": _sorted(by_tool),
        "event_count": len(events),
    }


def build_report(
    *,
    usage_profile: str,
    since: str | None,
    until: str | None,
    clients_raw: str,
    scope_ids_raw: str | None,
    project_dir: Path | None = None,
    include_user_clients: bool = True,
) -> dict[str, Any]:
    tr = parse_time_range(since, until)
    client_ids = resolve_client_ids(clients_raw)
    # For history filter: if user passed explicit clients (not all), filter;
    # "all" means no client filter on history (include unknown).
    history_clients: list[str] | None
    text = (clients_raw or "all").strip().lower()
    if text in ("all", "*"):
        history_clients = None
    else:
        history_clients = client_ids

    scope_ids = resolve_scope_ids(scope_ids_raw)
    estimate = estimate_connect(usage_profile)
    root = project_dir or Path.cwd()
    wiring = client_wiring(
        client_ids,
        project_dir=root,
        server_name=str(estimate["server_name"]),
        include_user=include_user_clients,
    )
    wired_n = sum(1 for w in wiring if w["wired"])
    connect_tokens = int(estimate["connect"]["lazy_tools_list_tokens"])
    events = load_mcp_usage_events(start=tr.start, end=tr.end)
    history = aggregate_history(events, client_ids=history_clients, scope_ids=scope_ids)

    return {
        "range": tr.label,
        "usage_profile": usage_profile,
        "project_dir": str(root.resolve()),
        "repo_root": str(repo_root()),
        "estimate": estimate,
        "clients": {
            "selected": client_ids,
            "wiring": wiring,
            "wired_count": wired_n,
            "if_each_wired_client_connects_tokens": connect_tokens * max(wired_n, 0),
            "note": (
                "Each coding-agent session that loads Astloom pays the lazy "
                "tools/list cost once per MCP connect."
            ),
        },
        "history": history,
        "filters": {
            "clients": clients_raw or "all",
            "scope_ids": scope_ids_raw or "all",
        },
    }


def format_text(report: dict[str, Any]) -> str:
    est = report["estimate"]
    conn = est["connect"]
    lines = [
        "Astloom MCP Token Report",
        "=" * 72,
        f"Range: {report['range']}",
        f"Profile: {est['usage_profile']}  |  Server: {est['server_name']}",
        f"Catalog tools: {est['tool_count_catalog']}",
        "",
        "Connect cost (tools/list into agent context)",
        "-" * 72,
        f"  Lazy facade (actual):     {conn['lazy_tools_list_tokens']:>8} tokens",
        f"  Full catalog (if dumped): {conn['full_catalog_tools_list_tokens']:>8} tokens",
        f"  Saved by mcp-lazy:        {conn['saved_vs_full_catalog']:>8} tokens",
        f"  {conn['note']}",
        "",
        "Heavy tool payloads (est.)",
        "-" * 72,
    ]
    for row in est["heavy_tools"][:12]:
        lines.append(
            f"  {row['tool']:<42} {row['kind']:<18} {row['tokens_est']:>8}"
        )

    clients = report["clients"]
    lines += [
        "",
        "Clients (IDE ids)",
        "-" * 72,
        f"  Selected: {', '.join(clients['selected'])}",
        f"  Wired now: {clients['wired_count']}  |  "
        f"If each connects: ~{clients['if_each_wired_client_connects_tokens']} tokens",
    ]
    for w in clients["wiring"]:
        flag = "wired" if w["wired"] else "not wired"
        path = w["config_path"] or "(no path)"
        lines.append(f"  {w['client_id']:<16} {flag:<10} {path}")

    hist = report["history"]
    tot = hist["totals"]
    lines += [
        "",
        "History (logged MCP calls in range)",
        "-" * 72,
        f"  Filters: clients={report['filters']['clients']}  "
        f"scope_ids={report['filters']['scope_ids']}",
        f"  Calls: {tot['calls']}  in: {tot['tokens_in']}  out: {tot['tokens_out']}  "
        f"total: {tot['tokens_in'] + tot['tokens_out']}",
    ]
    if tot["calls"] == 0:
        lines.append(
            "  (no events yet — connect an IDE MCP session; gateway appends "
            "<ASTLOOM_DATA_ROOT>/mcp-usage/events.jsonl)"
        )
    else:
        lines.append("  By client_id:")
        for cid, b in list(hist["by_client_id"].items())[:12]:
            lines.append(
                f"    {cid:<20} calls={b['calls']:<5} in={b['tokens_in']:<8} out={b['tokens_out']}"
            )
        lines.append("  By scope_id (tenant/workspace/project):")
        for sid, b in list(hist["by_scope_id"].items())[:12]:
            lines.append(
                f"    {sid:<28} calls={b['calls']:<5} in={b['tokens_in']:<8} out={b['tokens_out']}"
            )
        lines.append("  By tool:")
        for tool, b in list(hist["by_tool"].items())[:12]:
            lines.append(
                f"    {tool:<42} calls={b['calls']:<5} out={b['tokens_out']}"
            )

    lines += [
        "",
        "Notes:",
        "  - Token unit ≈ UTF-8 bytes/4 (same heuristic as sync usage).",
        "  - --clients all|cursor,vscode   --id all|tenant/ws/proj,other/…",
        "  - --since 24h|7d|30d|ISO  --until ISO",
    ]
    return "\n".join(lines)
