"""Inventory word-mode parsing (detail | save <path>)."""

from __future__ import annotations


def parse_inventory_words(words: list[str] | None) -> tuple[bool, str]:
    """Parse inventory word modes: detail | save <path> | detail save <path>.

    No dashed flags. Returns (detail, save_path).
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
            if i + 1 >= len(items):
                raise SystemExit(
                    "error: save requires a file path "
                    "(example: astloom inventory save /tmp/inv.txt)"
                )
            save_path = items[i + 1]
            i += 2
            continue
        raise SystemExit(
            f"error: unknown inventory word {word!r} "
            "(allowed: detail, save <path>)"
        )
    return detail, save_path
