"""Token estimates for packs (RM-02). Heuristic chars/4 — no cloud tokenizer."""

from __future__ import annotations


def tokens_from_chars(char_count: int) -> int:
    n = max(0, int(char_count))
    return (n + 3) // 4


def estimate_tokens(text: str) -> int:
    return tokens_from_chars(len(text or ""))
