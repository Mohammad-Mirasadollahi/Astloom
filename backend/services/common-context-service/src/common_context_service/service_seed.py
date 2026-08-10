"""Platform MCP-first guidance seed pack application and upgrades."""

from __future__ import annotations

from typing import Any

from .constants import GUIDANCE_KINDS
from .scope import Scope, project_scope
from .seed_mcp_first import (
    SEED_PACK_ID,
    SEED_PACK_VERSION,
    mcp_first_seed_payloads,
    mcp_first_seed_skill_names,
)
from .util import now_iso


class SeedMixin:
    def ensure_mcp_first_seed(self, scope: Scope, actor_id: str, correlation_id: str) -> dict[str, Any]:
        """Idempotently seed MCP-first pack; add missing skills and refresh stale pack bodies."""
        seed_scope = (
            scope
            if scope.scope_kind in {"org", "project"}
            else project_scope(scope.tenant_id, scope.workspace_id, scope.project_id)
        )
        all_items = self.store.list_items(seed_scope)
        guidance_items = [i for i in all_items if str(i.get("item_type") or "") in GUIDANCE_KINDS]
        if not guidance_items:
            item_ids: list[str] = []
            seed_key = (
                seed_scope.project_id if seed_scope.scope_kind == "project" else f"org:{seed_scope.workspace_id}"
            )
            for index, payload in enumerate(mcp_first_seed_payloads()):
                item = self.propose_item(
                    seed_scope,
                    actor_id,
                    correlation_id,
                    f"awg-seed-mcp-first:{seed_key}:{index}:{payload.get('item_type')}:"
                    f"{payload.get('name') or payload.get('slug') or 'entry'}",
                    payload,
                )
                approved_item = self.approve_item(seed_scope, item["id"], actor_id)
                item_ids.append(approved_item["id"])
            self.store.append_event(
                {
                    "event_type": "AgentWorkspaceGuidanceSeedApplied",
                    "project_id": seed_scope.project_id,
                    "scope_kind": seed_scope.scope_kind,
                    "seed_pack": SEED_PACK_ID,
                    "seed_pack_version": SEED_PACK_VERSION,
                    "item_ids": item_ids,
                }
            )
            return {
                "seeded": True,
                "reason": "applied",
                "item_ids": item_ids,
                "seed_pack": SEED_PACK_ID,
                "seed_pack_version": SEED_PACK_VERSION,
                "scope_kind": seed_scope.scope_kind,
            }

        return self._upgrade_mcp_first_seed(seed_scope, actor_id, correlation_id)

    def _upgrade_mcp_first_seed(
        self, seed_scope: Scope, actor_id: str, correlation_id: str
    ) -> dict[str, Any]:
        """Add missing pack skills, refresh outdated pack bodies, suppress retired pack skills."""
        added = self._ensure_missing_mcp_first_skills(seed_scope, actor_id, correlation_id)
        refreshed = self._refresh_mcp_first_seed_bodies(seed_scope)
        suppressed = self._suppress_retired_mcp_first_skills(seed_scope, actor_id)
        item_ids = [*added, *refreshed, *suppressed]
        if not item_ids:
            return {
                "seeded": False,
                "reason": "guidance_already_present",
                "item_ids": [],
                "seed_pack": SEED_PACK_ID,
                "seed_pack_version": SEED_PACK_VERSION,
                "scope_kind": seed_scope.scope_kind,
            }
        reasons: list[str] = []
        if added:
            reasons.append("skills_added")
        if refreshed:
            reasons.append("bodies_refreshed")
        if suppressed:
            reasons.append("retired_suppressed")
        self.store.append_event(
            {
                "event_type": "AgentWorkspaceGuidanceSeedUpgraded",
                "project_id": seed_scope.project_id,
                "scope_kind": seed_scope.scope_kind,
                "seed_pack": SEED_PACK_ID,
                "seed_pack_version": SEED_PACK_VERSION,
                "item_ids": item_ids,
                "added": added,
                "refreshed": refreshed,
                "suppressed": suppressed,
            }
        )
        return {
            "seeded": True,
            "reason": "+".join(reasons),
            "item_ids": item_ids,
            "seed_pack": SEED_PACK_ID,
            "seed_pack_version": SEED_PACK_VERSION,
            "scope_kind": seed_scope.scope_kind,
            "added": added,
            "refreshed": refreshed,
            "suppressed": suppressed,
        }

    def _ensure_missing_mcp_first_skills(
        self, seed_scope: Scope, actor_id: str, correlation_id: str
    ) -> list[str]:
        existing_names = {
            str(i.get("name") or "").strip()
            for i in self.store.list_items(seed_scope)
            if str(i.get("item_type") or "") == "skill" and str(i.get("name") or "").strip()
        }
        seed_key = seed_scope.project_id if seed_scope.scope_kind == "project" else f"org:{seed_scope.workspace_id}"
        added: list[str] = []
        for index, payload in enumerate(mcp_first_seed_payloads()):
            if payload.get("item_type") != "skill":
                continue
            name = str(payload.get("name") or "").strip()
            if not name or name in existing_names:
                continue
            item = self.propose_item(
                seed_scope,
                actor_id,
                correlation_id,
                f"awg-seed-mcp-first-skill-upgrade:{seed_key}:{index}:{name}:{SEED_PACK_VERSION}",
                payload,
            )
            approved_item = self.approve_item(seed_scope, item["id"], actor_id)
            added.append(approved_item["id"])
            existing_names.add(name)
        return added

    def _seed_item_key(self, item: dict[str, Any]) -> str | None:
        kind = str(item.get("item_type") or "")
        if kind == "agents_entry":
            return "agents_entry"
        if kind == "always_rule":
            slug = str(item.get("slug") or "").strip()
            return f"rule:{slug}" if slug else None
        if kind == "skill":
            name = str(item.get("name") or "").strip()
            return f"skill:{name}" if name else None
        return None

    def _is_platform_seed_item(self, item: dict[str, Any]) -> bool:
        if str(item.get("seed_pack") or "") == SEED_PACK_ID:
            return True
        kind = str(item.get("item_type") or "")
        if kind == "always_rule" and str(item.get("slug") or "") == "mcp-first-astloom":
            return True
        if kind == "agents_entry" and "mcp-first-astloom" in str(item.get("body") or ""):
            return True
        if kind == "skill" and str(item.get("name") or "") in mcp_first_seed_skill_names():
            # Legacy installs without seed_pack stamp — still refresh known pack skill names.
            return True
        return False

    def _refresh_mcp_first_seed_bodies(self, seed_scope: Scope) -> list[str]:
        """Overwrite platform seed bodies when pack content advanced (prevents stale MCP guidance)."""
        payloads = {self._seed_item_key(p): p for p in mcp_first_seed_payloads() if self._seed_item_key(p)}
        refreshed: list[str] = []
        for item in self.store.list_items(seed_scope, status="approved"):
            if not self._is_platform_seed_item(item):
                continue
            key = self._seed_item_key(item)
            if not key or key not in payloads:
                continue
            payload = payloads[key]
            desired_body = str(payload.get("body") or "").strip()
            desired_title = str(payload.get("title") or item.get("title") or "").strip()
            desired_desc = str(payload.get("description") or "").strip() or None
            desired_when = payload.get("when_to_use")
            desired_priority = int(payload.get("priority") or 0)
            desired_mandatory = bool(payload.get("mandatory") or False)
            changed = (
                str(item.get("body") or "").strip() != desired_body
                or str(item.get("title") or "").strip() != desired_title
                or (item.get("description") or None) != desired_desc
                or (item.get("when_to_use") or None) != desired_when
                or int(item.get("priority") or 0) != desired_priority
                or bool(item.get("mandatory")) != desired_mandatory
                or str(item.get("seed_pack") or "") != SEED_PACK_ID
                or str(item.get("seed_pack_version") or "") != SEED_PACK_VERSION
            )
            if not changed:
                continue
            updated = dict(item)
            updated["body"] = desired_body
            updated["title"] = desired_title
            updated["description"] = desired_desc
            updated["when_to_use"] = desired_when
            updated["priority"] = desired_priority
            updated["mandatory"] = desired_mandatory
            updated["seed_pack"] = SEED_PACK_ID
            updated["seed_pack_version"] = SEED_PACK_VERSION
            updated["version"] = int(item.get("version") or 1) + 1
            updated["updated_at"] = now_iso()
            self.store.put_item(updated)
            refreshed.append(updated["id"])
        return refreshed

    def _suppress_retired_mcp_first_skills(self, seed_scope: Scope, actor_id: str) -> list[str]:
        """Suppress pack-stamped skills removed from the current seed catalog."""
        current = mcp_first_seed_skill_names()
        suppressed: list[str] = []
        for item in self.store.list_items(seed_scope, status="approved"):
            if str(item.get("item_type") or "") != "skill":
                continue
            if str(item.get("seed_pack") or "") != SEED_PACK_ID:
                continue
            name = str(item.get("name") or "").strip()
            if not name or name in current:
                continue
            result = self.suppress_item(
                seed_scope,
                item["id"],
                actor_id,
                reason=f"removed_from_{SEED_PACK_ID}@{SEED_PACK_VERSION}",
            )
            suppressed.append(result["id"])
        return suppressed
