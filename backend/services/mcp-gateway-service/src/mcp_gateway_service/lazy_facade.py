"""MCP-lazy style facade: expose search + execute instead of the full tool catalog."""

from __future__ import annotations

import re
from typing import Any

LAZY_SEARCH_TOOL = "mcp_search_tools"
LAZY_EXECUTE_TOOL = "mcp_execute_tool"

_LAZY_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "What you want to do in natural language",
        },
        "limit": {
            "type": "number",
            "default": 5,
            "description": "Max results to return (default: 5)",
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}

_LAZY_EXECUTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tool_name": {
            "type": "string",
            "description": "Tool name from mcp_search_tools",
        },
        "server_name": {
            "type": "string",
            "description": "Server name from mcp_search_tools",
        },
        "tool": {
            "type": "string",
            "description": "Alias for tool_name",
        },
        "server": {
            "type": "string",
            "description": "Alias for server_name",
        },
        "arguments": {
            "type": "object",
            "additionalProperties": True,
            "description": "Tool arguments",
        },
    },
    "additionalProperties": False,
}


def lazy_tools_list(*, server_name: str) -> list[dict[str, Any]]:
    """Return the two facade tools Cursor should load into context."""
    _ = server_name
    return [
        {
            "name": LAZY_SEARCH_TOOL,
            "description": (
                "Search available Astloom MCP tools by keyword. "
                "Use this BEFORE calling any capability tool. "
                "Returns matching tool names, server names, descriptions, and input schemas. "
                f'Example: mcp_search_tools("guidance resolve") → {server_name}.astloom_guidance_resolve'
            ),
            "inputSchema": _LAZY_SEARCH_SCHEMA,
        },
        {
            "name": LAZY_EXECUTE_TOOL,
            "description": (
                "Execute a specific Astloom MCP tool. "
                "Use tool_name and server_name from mcp_search_tools results."
            ),
            "inputSchema": _LAZY_EXECUTE_SCHEMA,
        },
    ]


def is_lazy_facade_tool(name: str) -> bool:
    return name in (LAZY_SEARCH_TOOL, LAZY_EXECUTE_TOOL)


def normalize_execute_args(arguments: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    tool_name = str(arguments.get("tool_name") or arguments.get("tool") or "").strip()
    server_name = str(arguments.get("server_name") or arguments.get("server") or "").strip()
    args = arguments.get("arguments")
    if not isinstance(args, dict):
        args = {}
    return tool_name, server_name, args


def server_name_aliases(canonical: str) -> set[str]:
    """Accepted server_name values for mcp_execute_tool."""
    name = str(canonical or "").strip()
    return {a for a in {name, name.lower()} if a}


def search_catalog(
    tools: list[dict[str, Any]],
    *,
    server_name: str,
    query: str,
    limit: int = 5,
) -> dict[str, Any]:
    query_lower = str(query or "").strip().lower()
    tokens = [t for t in re.findall(r"[a-z0-9]+", query_lower) if t]
    destructive_intent = bool(
        set(tokens) & {"purge", "delete", "wipe", "destroy", "remove"}
    )
    capped = max(1, min(int(limit or 5), 50))
    scored: list[tuple[float, dict[str, Any]]] = []
    for tool in tools:
        name = str(tool.get("name") or "")
        desc = str(tool.get("description") or "")
        name_lower = name.lower()
        desc_lower = desc.lower()
        name_tokens = set(re.findall(r"[a-z0-9]+", name_lower))
        score = 0.0
        if not query_lower:
            score = 0.1
        elif name_lower == query_lower:
            score += 1.0
        elif query_lower.replace(" ", "_") in name_lower:
            score += 2.0
        if tokens:
            name_matches = sum(1 for token in tokens if token in name_tokens)
            desc_matches = sum(1 for token in tokens if token in desc_lower)
            score += 1.5 * name_matches / len(tokens)
            score += 0.4 * desc_matches / len(tokens)
        for token in tokens:
            if token in name_lower:
                score += 0.2
        if not destructive_intent and name_tokens & {
            "purge",
            "delete",
            "wipe",
            "destroy",
        }:
            score -= 3.0
        if score <= 0:
            continue
        scored.append(
            (
                score,
                {
                    "tool_name": name,
                    "server_name": server_name,
                    "description": desc,
                    "inputSchema": tool.get("input_schema") or tool.get("inputSchema") or {},
                    "relevance_score": round(score, 2),
                },
            )
        )
    scored.sort(key=lambda item: (-item[0], item[1]["tool_name"]))
    results = [item[1] for item in scored[:capped]]
    if results:
        return {"results": results}
    return {
        "results": [],
        "suggestion": (
            f'No tools found for "{query}". '
            f"Available server: {server_name}. Try different keywords "
            "(guidance, memory, code graph, docs, write, task)."
        ),
    }
