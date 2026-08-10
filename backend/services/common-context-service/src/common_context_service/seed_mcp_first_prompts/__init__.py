"""Load MCP-first seed prompt Markdown from dedicated files (one body per file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=32)
def load_prompt(*parts: str) -> str:
    """Return one prompt file body. Does not concatenate multiple prompts."""
    path = _PROMPTS_ROOT.joinpath(*parts)
    if not path.is_file():
        raise FileNotFoundError(f"seed prompt missing: {path}")
    return path.read_text(encoding="utf-8").strip() + "\n"


def prompts_root() -> Path:
    return _PROMPTS_ROOT
