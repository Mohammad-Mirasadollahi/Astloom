"""Common-item lifecycle: propose, approve, suppress, reject, generic bundle."""

from __future__ import annotations

from typing import Any

from common_context import load_profile, score_item, select_within_budget

from .constants import ITEM_TYPES
from .errors import ConflictError, ValidationError
from .scope import Scope
from .util import new_id, now_iso, token_estimate


class ItemsMixin:
    def propose_item(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        title = str(payload.get("title") or "").strip()
        body = str(payload.get("body") or "").strip()
        if not title or not body:
            raise ValidationError("title and body are required")
        item_type = str(payload.get("item_type") or "general").strip() or "general"
        if item_type not in ITEM_TYPES:
            raise ValidationError(f"item_type must be one of: {', '.join(sorted(ITEM_TYPES))}")
        skill_name = str(payload.get("name") or "").strip() or None
        if item_type == "skill" and not skill_name:
            raise ValidationError("skill items require name")
        mandatory = bool(payload.get("mandatory") or False)
        if scope.scope_kind == "user":
            if item_type == "agents_entry":
                raise ValidationError("user scope cannot author agents_entry")
            if item_type == "general":
                raise ValidationError("user scope cannot author general items")
            if mandatory:
                raise ValidationError("user scope cannot set mandatory=true")
        existing = self.store.begin_idempotency(scope, idempotency_key, "common_item")
        if existing:
            return self.store.get_item(existing, scope)
        item_id = new_id("cci")
        scores = {
            "frequency": float(payload.get("frequency") or 1.0),
            "recency": float(payload.get("recency") or 1.0),
            "confidence": float(payload.get("confidence") or 0.5),
            "user_pinning": float(payload.get("user_pinning") or 0.0),
            "task_similarity": float(payload.get("task_similarity") or 0.5),
            "project_relevance": float(payload.get("project_relevance") or 0.5),
            "effectiveness": float(payload.get("effectiveness") or 0.5),
        }
        profile = load_profile()
        score = score_item(profile["weights"], scores)
        when_to_use = payload.get("when_to_use")
        if when_to_use is not None and not isinstance(when_to_use, list):
            raise ValidationError("when_to_use must be a list of strings")
        item = {
            "id": item_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "scope_kind": scope.scope_kind,
            "user_id": scope.user_id,
            "item_type": item_type,
            "title": title,
            "body": body,
            "status": "proposed",
            "version": 1,
            "score": score,
            "score_components": scores,
            "workflow_type": payload.get("workflow_type"),
            "task_type": payload.get("task_type"),
            "slug": str(payload.get("slug") or "").strip() or None,
            "name": skill_name,
            "description": str(payload.get("description") or "").strip() or None,
            "when_to_use": when_to_use,
            "priority": int(payload.get("priority") or 0),
            "mandatory": mandatory,
            "applicability": payload.get("applicability"),
            "seed_pack": str(payload.get("seed_pack") or "").strip() or None,
            "seed_pack_version": str(payload.get("seed_pack_version") or "").strip() or None,
            "created_by": actor_id,
            "correlation_id": correlation_id,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.put_item(item)
        self.store.complete_idempotency(scope, idempotency_key, "common_item", item_id)
        self.store.append_event(
            {
                "event_type": "common_item.proposed",
                "item_id": item_id,
                "item_type": item_type,
                "scope_kind": scope.scope_kind,
            }
        )
        return item

    def approve_item(self, scope: Scope, item_id: str, actor_id: str) -> dict[str, Any]:
        item = self.store.get_item(item_id, scope)
        if item["status"] == "approved":
            return item
        if item["status"] not in {"proposed", "under_review"}:
            raise ConflictError("item cannot be approved from current status")
        item_type = str(item.get("item_type") or "general")
        if item_type == "agents_entry":
            for other in self.store.list_items(scope, status="approved"):
                if other["id"] != item_id and str(other.get("item_type") or "") == "agents_entry":
                    raise ConflictError("project already has an approved agents_entry")
        if item_type == "skill":
            name = str(item.get("name") or "").strip()
            for other in self.store.list_items(scope, status="approved"):
                if (
                    other["id"] != item_id
                    and str(other.get("item_type") or "") == "skill"
                    and str(other.get("name") or "").strip() == name
                ):
                    raise ConflictError(f"approved skill name already exists: {name}")
        item["status"] = "approved"
        item["approved_by"] = actor_id
        item["updated_at"] = now_iso()
        self.store.put_item(item)
        self.store.append_event(
            {"event_type": "common_item.approved", "item_id": item_id, "item_type": item_type}
        )
        return item

    def suppress_item(self, scope: Scope, item_id: str, actor_id: str, reason: str = "") -> dict[str, Any]:
        item = self.store.get_item(item_id, scope)
        if item["status"] == "suppressed":
            return item
        if item["status"] in {"archived", "deprecated"}:
            raise ConflictError("item cannot be suppressed from current status")
        item["status"] = "suppressed"
        item["suppressed_by"] = actor_id
        item["suppress_reason"] = reason.strip()
        item["updated_at"] = now_iso()
        self.store.put_item(item)
        self.store.append_event(
            {"event_type": "common_item.suppressed", "item_id": item_id, "reason": item["suppress_reason"]}
        )
        return item

    def reject_item(self, scope: Scope, item_id: str, actor_id: str, reason: str = "") -> dict[str, Any]:
        item = self.store.get_item(item_id, scope)
        if item["status"] == "rejected":
            return item
        if item["status"] not in {"proposed", "under_review"}:
            raise ConflictError("item cannot be rejected from current status")
        item["status"] = "rejected"
        item["rejected_by"] = actor_id
        item["reject_reason"] = reason.strip()
        item["updated_at"] = now_iso()
        self.store.put_item(item)
        self.store.append_event(
            {"event_type": "common_item.rejected", "item_id": item_id, "reason": item["reject_reason"]}
        )
        return item

    def resolve_bundle(self, scope: Scope, token_budget: int = 800) -> dict[str, Any]:
        if token_budget < 1:
            raise ValidationError("token_budget must be >= 1")
        approved = [i for i in self.store.list_items(scope, status="approved")]
        candidates = [
            {
                "id": item["id"],
                "title": item["title"],
                "body": item["body"],
                "score": item["score"],
                "item_type": item.get("item_type") or "general",
                "token_estimate": token_estimate(item["body"]),
            }
            for item in approved
        ]
        selected = select_within_budget(candidates, token_budget=token_budget)
        included = [
            {
                "id": row["id"],
                "title": row["title"],
                "body": row["body"],
                "score": row["score"],
                "item_type": row["item_type"],
            }
            for row in selected
        ]
        used = sum(int(row.get("token_estimate") or 0) for row in selected)
        return {
            "project_id": scope.project_id,
            "token_budget": token_budget,
            "tokens_used": used,
            "included": included,
            "omitted_count": max(0, len(approved) - len(included)),
            "selection_reason": "score_desc_within_token_budget",
        }

