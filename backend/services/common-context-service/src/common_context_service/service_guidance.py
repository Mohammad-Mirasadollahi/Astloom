"""Agent Workspace Guidance resolve, skill catalog, and skill fetch."""

from __future__ import annotations

from typing import Any

from .constants import (
    DEFAULT_ALWAYS_RULES_BUDGET,
    DEFAULT_ENTRY_BUDGET,
    DEFAULT_SKILL_CATALOG_BUDGET,
    GUIDANCE_KINDS,
)
from .errors import NotFoundError, ValidationError
from .scope import Scope, org_scope, project_scope, user_scope
from .util import (
    item_layer,
    merge_by_key,
    new_id,
    normalize_task_overrides,
    now_iso,
    rule_key,
    skill_key,
    token_estimate,
)


class GuidanceMixin:
    def _layer_scopes(
        self, resolve_scope: Scope, *, user_id: str | None
    ) -> list[tuple[str, Scope]]:
        layers: list[tuple[str, Scope]] = [
            ("org", org_scope(resolve_scope.tenant_id, resolve_scope.workspace_id)),
            ("project", project_scope(resolve_scope.tenant_id, resolve_scope.workspace_id, resolve_scope.project_id)),
        ]
        uid = (user_id or "").strip()
        if uid:
            layers.append(("user", user_scope(resolve_scope.tenant_id, resolve_scope.workspace_id, uid)))
        return layers

    def _load_layered_guidance(
        self,
        resolve_scope: Scope,
        *,
        user_id: str | None,
        include_general_common_context: bool,
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        layered: list[tuple[str, dict[str, Any]]] = []
        considered: list[str] = []
        for layer, layer_scope in self._layer_scopes(resolve_scope, user_id=user_id):
            considered.append(layer)
            for item in self.store.list_items(layer_scope, status="approved"):
                kind = str(item.get("item_type") or "general")
                if kind in GUIDANCE_KINDS or (include_general_common_context and kind == "general"):
                    layered.append((layer, item))
        return layered, considered

    def resolve_guidance(
        self,
        scope: Scope,
        *,
        task_summary: str = "",
        workflow_type: str = "coding",
        include_skill_bodies: bool = False,
        budget_overrides: dict[str, Any] | None = None,
        include_general_common_context: bool = False,
        user_id: str | None = None,
        task_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = workflow_type
        budgets = {
            "entry_budget": DEFAULT_ENTRY_BUDGET,
            "always_rules_budget": DEFAULT_ALWAYS_RULES_BUDGET,
            "skill_catalog_budget": DEFAULT_SKILL_CATALOG_BUDGET,
        }
        if budget_overrides:
            for key, value in budget_overrides.items():
                if key in budgets:
                    budgets[key] = max(1, int(value))
        overrides = normalize_task_overrides(task_overrides)

        resolve_scope = project_scope(scope.tenant_id, scope.workspace_id, scope.project_id)
        uid = (user_id or scope.user_id or "").strip() or None
        layered, layers_considered = self._load_layered_guidance(
            resolve_scope,
            user_id=uid,
            include_general_common_context=include_general_common_context,
        )

        entry_candidates = [(layer, i) for layer, i in layered if str(i.get("item_type") or "") == "agents_entry"]
        rule_candidates = [(layer, i) for layer, i in layered if str(i.get("item_type") or "") == "always_rule"]
        skill_candidates = [(layer, i) for layer, i in layered if str(i.get("item_type") or "") == "skill"]

        conflicts: list[dict[str, Any]] = []
        agents_entry = None
        tokens_used = 0
        suppressed: list[dict[str, Any]] = []

        # agents_entry: project wins over org; user never authors entry
        entry_by_layer: dict[str, list[dict[str, Any]]] = {"project": [], "org": []}
        for layer, item in entry_candidates:
            if layer in entry_by_layer:
                entry_by_layer[layer].append(item)
        chosen_entry = None
        chosen_layer = None
        for layer in ("project", "org"):
            entries = entry_by_layer[layer]
            if not entries:
                continue
            if len(entries) > 1:
                conflicts.append(
                    {
                        "reason_code": "multiple_agents_entry",
                        "layer": layer,
                        "item_ids": [e["id"] for e in entries],
                    }
                )
            entries.sort(key=lambda i: (-float(i.get("score") or 0), i["id"]))
            chosen_entry = entries[0]
            chosen_layer = layer
            for extra in entries[1:]:
                suppressed.append({"item_id": extra["id"], "reason_code": "duplicate_agents_entry", "layer": layer})
            break
        if chosen_entry is not None and chosen_layer is not None:
            cost = token_estimate(chosen_entry["body"])
            if cost <= budgets["entry_budget"]:
                agents_entry = {
                    "item_id": chosen_entry["id"],
                    "version": int(chosen_entry.get("version") or 1),
                    "title": chosen_entry["title"],
                    "body": chosen_entry["body"],
                    "layer": chosen_layer,
                    "token_estimate": cost,
                }
                tokens_used += cost
            else:
                suppressed.append(
                    {
                        "item_id": chosen_entry["id"],
                        "reason_code": "budget_exceeded",
                        "layer": chosen_layer,
                    }
                )

        merged_rules, rule_conflicts = merge_by_key(rule_candidates, key_fn=rule_key)
        conflicts.extend(rule_conflicts)
        query = task_summary.strip().lower()
        merged_rules.sort(
            key=lambda i: (
                -int(bool(i.get("mandatory"))),
                -int(i.get("priority") or 0),
                -float(i.get("score") or 0),
                i["id"],
            )
        )
        always_rules: list[dict[str, Any]] = []
        rules_used = 0
        for rule in merged_rules:
            cost = token_estimate(rule["body"])
            if rules_used + cost > budgets["always_rules_budget"]:
                suppressed.append(
                    {
                        "item_id": rule["id"],
                        "reason_code": "budget_exceeded",
                        "layer": item_layer(rule),
                    }
                )
                continue
            reason = "applicability_match"
            if query and rule.get("body") and query not in str(rule.get("body")).lower():
                reason = "always_on"
            always_rules.append(
                {
                    "item_id": rule["id"],
                    "version": int(rule.get("version") or 1),
                    "title": rule["title"],
                    "body": rule["body"],
                    "slug": rule.get("slug"),
                    "priority": int(rule.get("priority") or 0),
                    "mandatory": bool(rule.get("mandatory")),
                    "layer": item_layer(rule),
                    "reason_code": reason,
                    "token_estimate": cost,
                }
            )
            rules_used += cost
            tokens_used += cost

        if overrides["suppress_rule_slugs"]:
            kept_rules: list[dict[str, Any]] = []
            for rule in always_rules:
                slug = str(rule.get("slug") or "").strip()
                if slug and slug in overrides["suppress_rule_slugs"]:
                    if rule.get("mandatory"):
                        conflicts.append(
                            {
                                "reason_code": "task_override_blocked",
                                "item_id": rule["item_id"],
                                "slug": slug,
                                "layer": rule.get("layer"),
                            }
                        )
                        kept_rules.append(rule)
                    else:
                        suppressed.append(
                            {
                                "item_id": rule["item_id"],
                                "reason_code": "task_override",
                                "layer": rule.get("layer"),
                                "slug": slug,
                            }
                        )
                        tokens_used -= int(rule.get("token_estimate") or 0)
                else:
                    kept_rules.append(rule)
            always_rules = kept_rules

        merged_skills, skill_conflicts = merge_by_key(skill_candidates, key_fn=skill_key)
        conflicts.extend(skill_conflicts)
        merged_skills.sort(key=lambda i: (-float(i.get("score") or 0), str(i.get("name") or ""), i["id"]))
        skill_catalog: list[dict[str, Any]] = []
        catalog_used = 0
        for skill in merged_skills:
            descriptor = {
                "item_id": skill["id"],
                "name": skill.get("name"),
                "description": skill.get("description") or skill["title"],
                "version": int(skill.get("version") or 1),
                "when_to_use": skill.get("when_to_use") or [],
                "layer": item_layer(skill),
                "reason_code": "catalog_match",
            }
            if include_skill_bodies:
                descriptor["body"] = skill["body"]
            cost = token_estimate(str(descriptor.get("description") or "") + str(descriptor.get("name") or ""))
            if include_skill_bodies:
                cost += token_estimate(skill["body"])
            if catalog_used + cost > budgets["skill_catalog_budget"]:
                suppressed.append(
                    {
                        "item_id": skill["id"],
                        "reason_code": "budget_exceeded",
                        "layer": item_layer(skill),
                    }
                )
                continue
            skill_catalog.append(descriptor)
            catalog_used += cost
            tokens_used += cost

        if overrides["suppress_skill_names"]:
            kept_skills: list[dict[str, Any]] = []
            for skill in skill_catalog:
                name = str(skill.get("name") or "").strip()
                if name and name in overrides["suppress_skill_names"]:
                    suppressed.append(
                        {
                            "item_id": skill["item_id"],
                            "reason_code": "task_override",
                            "layer": skill.get("layer"),
                            "name": name,
                        }
                    )
                else:
                    kept_skills.append(skill)
            skill_catalog = kept_skills

        empty_reason = None
        if agents_entry is None and not always_rules and not skill_catalog:
            empty_reason = "no_approved_guidance"

        bundle_id = new_id("bnd")
        audit_id = new_id("aud")
        bundle = {
            "bundle_id": bundle_id,
            "schema_version": "1.0",
            "read_model_id": "common_context.guidance",
            "project_id": resolve_scope.project_id,
            "user_id": uid,
            "layers_considered": layers_considered,
            "resolved_at": now_iso(),
            "agents_entry": agents_entry,
            "always_rules": always_rules,
            "skills": skill_catalog,
            "suppressed_items": suppressed,
            "conflicts": conflicts,
            "token_estimate": max(0, tokens_used),
            "audit_record_id": audit_id,
            "empty_reason": empty_reason,
            "budgets": budgets,
            "task_summary": task_summary or None,
            "task_overrides": {
                "suppress_rule_slugs": sorted(overrides["suppress_rule_slugs"]),
                "suppress_skill_names": sorted(overrides["suppress_skill_names"]),
            }
            if (overrides["suppress_rule_slugs"] or overrides["suppress_skill_names"])
            else None,
        }
        self.store.append_event(
            {
                "event_type": "AgentWorkspaceGuidanceBundleResolved",
                "bundle_id": bundle_id,
                "project_id": resolve_scope.project_id,
                "user_id": uid,
                "layers_considered": layers_considered,
                "audit_record_id": audit_id,
                "counts": {
                    "always_rules": len(always_rules),
                    "skills": len(skill_catalog),
                    "suppressed": len(suppressed),
                    "conflicts": len(conflicts),
                },
            }
        )
        return bundle

    def list_skills(
        self,
        scope: Scope,
        query: str = "",
        *,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        resolve_scope = project_scope(scope.tenant_id, scope.workspace_id, scope.project_id)
        uid = (user_id or scope.user_id or "").strip() or None
        layered, _ = self._load_layered_guidance(
            resolve_scope, user_id=uid, include_general_common_context=False
        )
        skill_candidates = [(layer, i) for layer, i in layered if str(i.get("item_type") or "") == "skill"]
        merged, _ = merge_by_key(skill_candidates, key_fn=skill_key)
        q = query.strip().lower()
        out: list[dict[str, Any]] = []
        for skill in merged:
            name = str(skill.get("name") or "")
            description = str(skill.get("description") or skill.get("title") or "")
            when = skill.get("when_to_use") or []
            hay = " ".join([name, description, " ".join(str(x) for x in when)]).lower()
            if q and q not in hay:
                continue
            out.append(
                {
                    "item_id": skill["id"],
                    "name": name,
                    "description": description,
                    "version": int(skill.get("version") or 1),
                    "when_to_use": when,
                    "layer": item_layer(skill),
                    "reason_code": "catalog_match",
                }
            )
        out.sort(key=lambda s: s["name"] or "")
        return out

    def get_skill(
        self,
        scope: Scope,
        *,
        skill_id: str | None = None,
        name: str | None = None,
        bundle_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        sid = (skill_id or "").strip()
        sname = (name or "").strip()
        if not sid and not sname:
            raise ValidationError("skill_id or name is required")
        resolve_scope = project_scope(scope.tenant_id, scope.workspace_id, scope.project_id)
        uid = (user_id or scope.user_id or "").strip() or None
        layered, _ = self._load_layered_guidance(
            resolve_scope, user_id=uid, include_general_common_context=False
        )
        skill_candidates = [(layer, i) for layer, i in layered if str(i.get("item_type") or "") == "skill"]
        merged, _ = merge_by_key(skill_candidates, key_fn=skill_key)
        item = None
        if sid:
            for candidate in merged:
                if candidate["id"] == sid:
                    item = candidate
                    break
            if item is None:
                # Fallback: id may exist on a layer but lost merge race — still allow fetch by id
                for layer, layer_scope in self._layer_scopes(resolve_scope, user_id=uid):
                    _ = layer
                    try:
                        found = self.store.get_item(sid, layer_scope)
                    except NotFoundError:
                        continue
                    if str(found.get("item_type") or "") == "skill" and found.get("status") == "approved":
                        item = found
                        break
        else:
            matches = [i for i in merged if str(i.get("name") or "") == sname]
            if matches:
                item = matches[0]
        if item is None or str(item.get("item_type") or "") != "skill" or item.get("status") != "approved":
            raise NotFoundError("skill not found")
        result = {
            "item_id": item["id"],
            "name": item.get("name"),
            "version": int(item.get("version") or 1),
            "body": item["body"],
            "content_hash": f"sha256:{len(item['body'])}:{item['id']}",
            "description": item.get("description") or item.get("title"),
            "when_to_use": item.get("when_to_use") or [],
            "layer": item_layer(item),
        }
        self.store.append_event(
            {
                "event_type": "AgentWorkspaceGuidanceSkillFetched",
                "item_id": item["id"],
                "name": item.get("name"),
                "bundle_id": bundle_id,
                "project_id": resolve_scope.project_id,
                "layer": result["layer"],
            }
        )
        return result

