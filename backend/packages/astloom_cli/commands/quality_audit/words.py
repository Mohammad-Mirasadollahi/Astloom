"""Word modes for ``astloom quality-audit``."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from astloom_cli.util import repo_root


def default_save_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    return repo_root() / ".astloom" / "quality-audit" / f"{stamp}.txt"


def parse_quality_audit_words(words: list[str] | None) -> tuple[bool, str]:
    """Parse word modes: detail | save [<path>] | detail save [<path>].

    ``save`` without a path writes under ``.astloom/quality-audit/``.
    """
    detail = False
    save_path = ""
    items = [str(w or "").strip() for w in (words or []) if str(w or "").strip()]
    i = 0
    while i < len(items):
        word = items[i]
        if word == "detail":
            if detail:
                raise SystemExit("error: detail specified more than once")
            detail = True
            i += 1
            continue
        if word == "save":
            if save_path:
                raise SystemExit("error: save specified more than once")
            if i + 1 < len(items) and items[i + 1] not in {"detail", "save"}:
                save_path = items[i + 1]
                i += 2
            else:
                save_path = str(default_save_path())
                i += 1
            continue
        raise SystemExit(
            f"error: unknown quality-audit word {word!r} "
            "(allowed: detail, save [<path>])"
        )
    return detail, save_path
