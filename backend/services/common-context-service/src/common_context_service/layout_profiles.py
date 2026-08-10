"""Load guidance export layout profiles from configs/guidance-export/layouts.json.

Role: map AWG kinds to IDE-native paths without hard-coding Claude aliases in code.
SoT: backend/configs/guidance-export/layouts.json
Invariants: unknown layout → empty profile; missing file → built-in cursor defaults.
Allowed failure: JSON/OS errors fall back to defaults.
Forbidden: inventing Claude paths outside the profile file.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULTS: dict[str, Any] = {
    "cursor": {
        "agents_entry_paths": ["AGENTS.md"],
        "always_rule_dir": ".cursor/rules",
        "always_rule_ext": ".mdc",
        "skill_dir": ".cursor/skills",
        "skill_filename": "SKILL.md",
        "cursor_mdc_frontmatter": True,
    },
    "claude_compatible": {
        "agents_entry_paths": ["AGENTS.md", "CLAUDE.md"],
        "always_rule_dir": ".claude/rules",
        "always_rule_ext": ".md",
        "skill_dir": ".claude/skills",
        "skill_filename": "SKILL.md",
        "cursor_mdc_frontmatter": False,
    },
    "generic_agents_md": {
        "agents_entry_paths": ["AGENTS.md"],
        "always_rule_dir": None,
        "always_rule_ext": None,
        "skill_dir": None,
        "skill_filename": None,
        "cursor_mdc_frontmatter": False,
        "embed_catalog_in_agents_entry": True,
    },
}


def _layouts_path() -> Path:
    # common_context_service/src/common_context_service/ → repo root via parents
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "backend" / "configs" / "guidance-export" / "layouts.json"
        if candidate.is_file():
            return candidate
    return here  # missing → defaults only


@lru_cache(maxsize=1)
def load_layout_profiles() -> dict[str, Any]:
    path = _layouts_path()
    if not path.is_file():
        return dict(_DEFAULTS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULTS)
    layouts = raw.get("layouts") if isinstance(raw, dict) else None
    if not isinstance(layouts, dict) or not layouts:
        return dict(_DEFAULTS)
    merged = dict(_DEFAULTS)
    for name, profile in layouts.items():
        if isinstance(profile, dict):
            merged[str(name)] = {**merged.get(str(name), {}), **profile}
    return merged


def get_layout_profile(layout: str) -> dict[str, Any]:
    layouts = load_layout_profiles()
    key = (layout or "cursor").strip() or "cursor"
    profile = layouts.get(key)
    if isinstance(profile, dict):
        return profile
    return dict(layouts.get("cursor") or _DEFAULTS["cursor"])
