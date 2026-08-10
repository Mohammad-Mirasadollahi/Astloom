"""Filesystem export of approved guidance into IDE layouts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ValidationError
from .guidance_export import materialize_planned_files, planned_files_from_items
from .scope import Scope, project_scope
from .util import item_layer, merge_by_key, new_id, rule_key, skill_key


class ExportMixin:
    def export_guidance_layout(
        self,
        scope: Scope,
        *,
        layout: str = "cursor",
        dry_run: bool = True,
        user_id: str | None = None,
        target_root: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Plan (and optionally write) IDE-native guidance files for approved items."""
        if layout not in {"cursor", "claude_compatible", "generic_agents_md"}:
            raise ValidationError("layout must be cursor, claude_compatible, or generic_agents_md")
        resolve_scope = project_scope(scope.tenant_id, scope.workspace_id, scope.project_id)
        uid = (user_id or scope.user_id or "").strip() or None
        layered, _ = self._load_layered_guidance(
            resolve_scope, user_id=uid, include_general_common_context=False
        )
        # Export project+org winners (user personal pack is session-only; exclude from disk export)
        exportable = [(layer, i) for layer, i in layered if layer in {"org", "project"}]
        entry_merged = [i for layer, i in exportable if str(i.get("item_type")) == "agents_entry" and layer == "project"]
        if not entry_merged:
            entry_merged = [i for layer, i in exportable if str(i.get("item_type")) == "agents_entry" and layer == "org"]
        rules, _ = merge_by_key(
            [(layer, i) for layer, i in exportable if str(i.get("item_type")) == "always_rule"],
            key_fn=rule_key,
        )
        skills, _ = merge_by_key(
            [(layer, i) for layer, i in exportable if str(i.get("item_type")) == "skill"],
            key_fn=skill_key,
        )
        approved = entry_merged + rules + skills
        for item in approved:
            item["layer"] = item_layer(item)
        planned = planned_files_from_items(approved, layout)
        export_id = new_id("exp")
        written: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        applied_dry_run = True
        if not dry_run:
            root = (target_root or "").strip()
            if not root:
                raise ValidationError("target_root is required when dry_run is false")
            applied = materialize_planned_files(Path(root), planned, force=force)
            written = applied["written"]
            skipped = applied["skipped"]
            conflicts = applied["conflicts"]
            applied_dry_run = False
        # API responses omit bulky content unless writing (clients use dry-run plan paths)
        planned_out = [
            {k: v for k, v in row.items() if k != "content"}
            for row in planned
        ]
        result = {
            "export_id": export_id,
            "layout": layout,
            "dry_run": applied_dry_run,
            "written": written,
            "skipped": skipped,
            "conflicts": conflicts,
            "planned": planned_out,
            "audit_record_id": new_id("aud"),
        }
        self.store.append_event(
            {
                "event_type": "AgentWorkspaceGuidanceExported",
                "export_id": export_id,
                "project_id": resolve_scope.project_id,
                "layout": layout,
                "planned_count": len(planned),
                "written_count": len(written),
                "conflict_count": len(conflicts),
            }
        )
        return result

