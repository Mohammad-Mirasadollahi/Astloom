"""Terminal presentation for astloom CLI (ANSI when TTY; respects NO_COLOR)."""

from __future__ import annotations

import os
import sys
from typing import Iterable, Sequence


def _use_color() -> bool:
    if os.environ.get("NO_COLOR", "").strip():
        return False
    if os.environ.get("ASTLOOM_CLI_COLOR", "").strip().lower() in {"0", "false", "no", "off"}:
        return False
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


class _Codes:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    WHITE = "\033[37m"


def paint(text: str, *styles: str) -> str:
    if not _use_color() or not styles:
        return text
    return f"{''.join(styles)}{text}{_Codes.RESET}"


def bold(text: str) -> str:
    return paint(text, _Codes.BOLD)


def dim(text: str) -> str:
    return paint(text, _Codes.DIM)


def ok(text: str) -> str:
    return paint(text, _Codes.GREEN, _Codes.BOLD)


def warn(text: str) -> str:
    return paint(text, _Codes.YELLOW, _Codes.BOLD)


def err(text: str) -> str:
    return paint(text, _Codes.RED, _Codes.BOLD)


def accent(text: str) -> str:
    return paint(text, _Codes.CYAN, _Codes.BOLD)


def label(text: str) -> str:
    return paint(f"{text:<12}", _Codes.DIM)


def heading(title: str, *, success: bool = True) -> None:
    mark = ok("✔") if success else err("✖")
    print(f"{mark}  {bold(title)}")


def blank() -> None:
    print()


def kv(key: str, value: str) -> None:
    print(f"   {label(key)} {value}")


def bullet(text: str, *, indent: int = 3) -> None:
    pad = " " * indent
    print(f"{pad}{dim('·')} {text}")


def section(title: str) -> None:
    print(f"   {accent(title)}")


def next_steps(lines: Sequence[str]) -> None:
    blank()
    print(f"   {bold('Next')}")
    for line in lines:
        bullet(line)


def rule(width: int = 56) -> None:
    print(dim("─" * width))


def scope_line(tenant: str, workspace: str, project: str) -> str:
    return (
        f"{accent(tenant)}{dim(' / ')}{accent(workspace)}{dim(' / ')}{accent(project)}"
    )


def status_badge(status: str) -> str:
    key = (status or "").strip().lower()
    if key in {"ready", "ok", "active", "all running"}:
        return ok(status)
    if key in {"pending_sync", "empty"}:
        return warn(status)
    if key in {"error", "down", "stopped"} or "not" in key or "stopped" in key:
        return err(status)
    return bold(status)


def summarize_paths(paths: Iterable[str | object], *, relative_to: str | None = None) -> list[str]:
    out: list[str] = []
    for raw in paths:
        text = str(raw)
        if relative_to and text.startswith(relative_to.rstrip("/") + "/"):
            text = text[len(relative_to.rstrip("/")) + 1 :]
        out.append(text)
    return out
