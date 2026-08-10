"""Framework HTTP route extraction (Wave 1 — CodeGraph-inspired).

Detects common decorator / registration patterns and returns route→handler
bindings for ingest to emit ROUTES_TO edges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# FastAPI / Starlette / Flask-style method decorators
_PY_ROUTE_DECORATOR = re.compile(
    r"@(?:(?P<app>\w+)\.)?(?P<method>get|post|put|delete|patch|options|head|route|"
    r"api_route|websocket)\(\s*[\"'](?P<path>[^\"']+)[\"']",
    re.IGNORECASE | re.MULTILINE,
)

# Django urls.py: path("...", view) / re_path / url
_DJANGO_PATH = re.compile(
    r"(?:path|re_path|url)\(\s*[\"'](?P<path>[^\"']+)[\"']\s*,\s*(?P<handler>[A-Za-z_][\w.]*)",
    re.MULTILINE,
)

# Express / Nest-ish JS: app.get('/x', handler) or router.post("...", fn)
_JS_ROUTE = re.compile(
    r"(?:app|router|Router)\.(?P<method>get|post|put|delete|patch|use|all)\(\s*"
    r"[\"'`](?P<path>[^\"'`]+)[\"'`]\s*,\s*(?P<handler>[A-Za-z_][\w.]*)",
    re.IGNORECASE | re.MULTILINE,
)

# Next function/def after a decorator block (best-effort)
_PY_DEF_AFTER = re.compile(
    r"^(?:async\s+)?def\s+(?P<name>[A-Za-z_]\w*)\s*\(",
    re.MULTILINE,
)


@dataclass(frozen=True)
class ExtractedRoute:
    method: str
    path: str
    handler_name: str
    framework: str
    line_hint: int = 0


def extract_routes(source: str, *, language: str, file_path: str = "") -> list[ExtractedRoute]:
    """Extract framework routes from a source file (deterministic, no LLM)."""
    lang = (language or "").lower().strip()
    if lang in {"python", "py"}:
        return _extract_python(source, file_path)
    if lang in {"javascript", "js", "typescript", "ts", "tsx", "jsx"}:
        return _extract_js(source)
    return []


def _extract_python(source: str, file_path: str) -> list[ExtractedRoute]:
    routes: list[ExtractedRoute] = []
    lower_path = file_path.replace("\\", "/").lower()
    is_urls = lower_path.endswith("urls.py") or "/urls.py" in lower_path

    for match in _PY_ROUTE_DECORATOR.finditer(source):
        method = (match.group("method") or "route").upper()
        if method == "ROUTE":
            method = "ANY"
        if method == "API_ROUTE":
            method = "ANY"
        path = match.group("path")
        # Find next def after decorator
        tail = source[match.end() :]
        def_match = _PY_DEF_AFTER.search(tail)
        if not def_match:
            continue
        handler = def_match.group("name")
        framework = "fastapi" if match.group("app") else "flask_or_fastapi"
        line_hint = source[: match.start()].count("\n") + 1
        routes.append(
            ExtractedRoute(
                method=method,
                path=path,
                handler_name=handler,
                framework=framework,
                line_hint=line_hint,
            )
        )

    if is_urls or "path(" in source or "re_path(" in source:
        for match in _DJANGO_PATH.finditer(source):
            handler = match.group("handler").split(".")[-1]
            line_hint = source[: match.start()].count("\n") + 1
            routes.append(
                ExtractedRoute(
                    method="ANY",
                    path=match.group("path"),
                    handler_name=handler,
                    framework="django",
                    line_hint=line_hint,
                )
            )
    return routes


def _extract_js(source: str) -> list[ExtractedRoute]:
    routes: list[ExtractedRoute] = []
    for match in _JS_ROUTE.finditer(source):
        handler = match.group("handler").split(".")[-1]
        line_hint = source[: match.start()].count("\n") + 1
        routes.append(
            ExtractedRoute(
                method=match.group("method").upper(),
                path=match.group("path"),
                handler_name=handler,
                framework="express",
                line_hint=line_hint,
            )
        )
    return routes


def route_symbol_id(project_id: str, method: str, path: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_./\-]", "_", f"{method}:{path}")
    return f"route:{project_id}:{safe}"
