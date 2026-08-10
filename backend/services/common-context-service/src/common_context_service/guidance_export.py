"""Filesystem materialize for Agent Workspace Guidance (Cursor / agents layouts).

Role: plan and write IDE-native guidance files from typed CommonItems / seed pack.
SoT: layout profiles under backend/configs/guidance-export/layouts.json.
Invariants: never silent-overwrite unmanaged locals; Claude paths come from profile.
Allowed failure: missing profile keys skip that kind; conflict list on drift.
Forbidden: hard-coding Claude directory aliases outside the layout profile.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from common_context_service.layout_profiles import get_layout_profile
from common_context_service.seed_mcp_first import (
    SEED_PACK_ID,
    SEED_PACK_VERSION,
    mcp_first_seed_payloads,
)

MANIFEST_REL = ".astloom/guidance-export-manifest.json"


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slugify(raw: str) -> str:
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in raw.lower()).strip("-")
    return slug or "item"


def relative_paths_for_item(item: dict[str, Any], layout: str) -> list[str]:
    """Return one or more relative export paths for an item under a layout profile."""
    kind = str(item.get("item_type") or "")
    profile = get_layout_profile(layout)
    if kind == "agents_entry":
        paths = profile.get("agents_entry_paths") or ["AGENTS.md"]
        return [str(p).strip() for p in paths if str(p).strip()]
    if kind == "always_rule":
        rule_dir = profile.get("always_rule_dir")
        if not rule_dir:
            return []
        ext = str(profile.get("always_rule_ext") or ".md")
        if not ext.startswith("."):
            ext = f".{ext}"
        slug = _slugify(str(item.get("slug") or item.get("title") or item.get("id") or "rule"))
        return [f"{str(rule_dir).rstrip('/')}/{slug}{ext}"]
    if kind == "skill":
        skill_dir = profile.get("skill_dir")
        if not skill_dir:
            return []
        name = str(item.get("name") or item.get("id") or "skill")
        filename = str(profile.get("skill_filename") or "SKILL.md")
        return [f"{str(skill_dir).rstrip('/')}/{name}/{filename}"]
    return []


def render_file_content(item: dict[str, Any], layout: str) -> str:
    body = str(item.get("body") or "").strip() + "\n"
    kind = str(item.get("item_type") or "")
    profile = get_layout_profile(layout)
    if kind == "always_rule" and profile.get("cursor_mdc_frontmatter"):
        title = str(item.get("title") or item.get("slug") or "Astloom rule").replace("\n", " ")
        return (
            "---\n"
            f"description: {title}\n"
            "alwaysApply: true\n"
            "---\n\n"
            f"{body}"
        )
    return body


def planned_files_from_items(items: list[dict[str, Any]], layout: str) -> list[dict[str, Any]]:
    planned: list[dict[str, Any]] = []
    for item in items:
        paths = relative_paths_for_item(item, layout)
        if not paths:
            continue
        content = render_file_content(item, layout)
        for path in paths:
            planned.append(
                {
                    "item_id": item.get("id") or item.get("name") or item.get("slug") or path,
                    "item_type": item.get("item_type"),
                    "path": path,
                    "layer": item.get("layer"),
                    "action": "create_or_update_managed",
                    "content": content,
                    "content_hash": content_sha256(content),
                    "seed_pack": item.get("seed_pack") or SEED_PACK_ID,
                    "seed_pack_version": item.get("seed_pack_version") or SEED_PACK_VERSION,
                }
            )
    return planned


def planned_files_from_seed_pack(layout: str = "cursor") -> list[dict[str, Any]]:
    return planned_files_from_items(mcp_first_seed_payloads(), layout)


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_REL
    if not path.is_file():
        return {"files": {}, "seed_pack": None, "seed_pack_version": None}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"files": {}, "seed_pack": None, "seed_pack_version": None}
    if not isinstance(raw, dict):
        return {"files": {}, "seed_pack": None, "seed_pack_version": None}
    files = raw.get("files")
    return {
        "files": files if isinstance(files, dict) else {},
        "seed_pack": raw.get("seed_pack"),
        "seed_pack_version": raw.get("seed_pack_version"),
    }


def _save_manifest(root: Path, manifest: dict[str, Any]) -> None:
    path = root / MANIFEST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def materialize_planned_files(
    root: Path,
    planned: list[dict[str, Any]],
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Write planned guidance files under root. Never silently overwrite unmanaged locals."""
    root = root.resolve()
    manifest = _load_manifest(root)
    tracked: dict[str, Any] = dict(manifest.get("files") or {})
    written: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for entry in planned:
        rel = str(entry.get("path") or "").strip()
        content = str(entry.get("content") or "")
        if not rel or not content:
            continue
        dest = root / rel
        digest = str(entry.get("content_hash") or content_sha256(content))
        prior = tracked.get(rel) if isinstance(tracked.get(rel), dict) else None

        if dest.exists():
            existing = dest.read_text(encoding="utf-8")
            existing_hash = content_sha256(existing)
            if existing_hash == digest:
                skipped.append({"path": rel, "reason_code": "unchanged"})
                tracked[rel] = {
                    "content_hash": digest,
                    "item_id": entry.get("item_id"),
                    "item_type": entry.get("item_type"),
                    "seed_pack": entry.get("seed_pack") or SEED_PACK_ID,
                    "seed_pack_version": entry.get("seed_pack_version") or SEED_PACK_VERSION,
                }
                continue
            if prior is None and not force:
                conflicts.append(
                    {
                        "path": rel,
                        "reason_code": "unmanaged_local_edit",
                        "item_id": entry.get("item_id"),
                    }
                )
                continue
            if (
                prior is not None
                and prior.get("content_hash") != existing_hash
                and not force
            ):
                conflicts.append(
                    {
                        "path": rel,
                        "reason_code": "managed_local_drift",
                        "item_id": entry.get("item_id"),
                    }
                )
                continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        tracked[rel] = {
            "content_hash": digest,
            "item_id": entry.get("item_id"),
            "item_type": entry.get("item_type"),
            "seed_pack": entry.get("seed_pack") or SEED_PACK_ID,
            "seed_pack_version": entry.get("seed_pack_version") or SEED_PACK_VERSION,
        }
        written.append({"path": rel, "item_id": entry.get("item_id"), "item_type": entry.get("item_type")})

    _save_manifest(
        root,
        {
            "files": tracked,
            "seed_pack": SEED_PACK_ID,
            "seed_pack_version": SEED_PACK_VERSION,
        },
    )
    return {
        "written": written,
        "skipped": skipped,
        "conflicts": conflicts,
        "manifest_path": MANIFEST_REL,
        "seed_pack": SEED_PACK_ID,
        "seed_pack_version": SEED_PACK_VERSION,
    }


def _prune_retired_seed_files(
    root: Path,
    planned_paths: set[str],
    tracked: dict[str, Any],
) -> list[dict[str, Any]]:
    """Delete managed Astloom seed files retired from the current pack."""
    removed: list[dict[str, Any]] = []
    for rel, meta in list(tracked.items()):
        if rel in planned_paths:
            continue
        if not isinstance(meta, dict):
            continue
        pack = str(meta.get("seed_pack") or "")
        # Pack-stamped or legacy unstamped managed entries (pre-version manifests).
        if pack not in ("", SEED_PACK_ID):
            continue
        # Only prune pack-owned layout paths (never arbitrary user files).
        if not (
            rel.startswith(".cursor/skills/astloom-")
            or rel.startswith(".agents/skills/astloom-")
            or rel.startswith(".claude/skills/astloom-")
            or rel == ".cursor/rules/mcp-first-astloom.mdc"
            or rel == ".agent/rules/mcp-first-astloom.md"
            or rel == ".claude/rules/mcp-first-astloom.md"
        ):
            continue
        path = root / rel
        if path.is_file():
            path.unlink()
            removed.append({"path": rel, "reason_code": "retired_from_seed_pack"})
        tracked.pop(rel, None)
        # Remove empty skill directory when possible
        parent = path.parent
        if parent != root and parent.is_dir() and not any(parent.iterdir()):
            try:
                parent.rmdir()
            except OSError:
                pass
    return removed


def materialize_mcp_first_seed(
    root: Path,
    *,
    layout: str = "cursor",
    force: bool = False,
) -> dict[str, Any]:
    """Write platform MCP-first seed pack into a client workspace (connect-time)."""
    planned = planned_files_from_seed_pack(layout)
    result = materialize_planned_files(root, planned, force=force)
    # Reload tracked after write and prune retired pack skills from disk.
    manifest = _load_manifest(root.resolve())
    tracked = dict(manifest.get("files") or {})
    removed = _prune_retired_seed_files(
        root.resolve(),
        {str(p["path"]) for p in planned},
        tracked,
    )
    if removed:
        _save_manifest(
            root.resolve(),
            {
                "files": tracked,
                "seed_pack": SEED_PACK_ID,
                "seed_pack_version": SEED_PACK_VERSION,
            },
        )
    result["planned"] = [{"path": p["path"], "item_type": p["item_type"]} for p in planned]
    result["seed_pack"] = SEED_PACK_ID
    result["seed_pack_version"] = SEED_PACK_VERSION
    result["removed"] = removed
    result["layout"] = layout
    return result
