"""Memory item lifecycle commands (create, browse, promote, forget, consolidate, decay)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .enums import MemoryKind, MemoryState
from .errors import ConflictError, ValidationError
from .helpers import normalize_optional_timestamp, now, sanitize, slug, tokenize
from .models import MemoryItem, Scope


class MemoryItemCommands:
    def create_memory(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> MemoryItem:
        self._require_key(key)
        payload = sanitize(payload)
        self._validate_memory_payload(payload)
        prior = self.store.idempotent(scope, "create_memory", key, payload)
        if prior:
            return self.store.get_memory(prior, scope)
        timestamp = now()
        kind = MemoryKind(payload["kind"])
        state = MemoryState.RESTRICTED if kind == MemoryKind.RESTRICTED else MemoryState(payload.get("state") or MemoryState.CANDIDATE.value)
        expires_at = normalize_optional_timestamp(payload.get("expires_at"), "expires_at")
        if kind != MemoryKind.WORKING and expires_at is not None:
            raise ValidationError("expires_at is only valid for working memory")
        item = MemoryItem(
            str(uuid4()),
            scope,
            actor,
            correlation_id,
            kind,
            state,
            payload["title"],
            payload["body"],
            sorted(set(payload.get("tags") or [])),
            sorted(set(payload.get("evidence_refs") or [])),
            sorted(set(payload.get("source_refs") or [])),
            float(payload.get("confidence", 1.0)),
            timestamp,
            timestamp,
            pinned=bool(payload.get("pinned", False)),
            expires_at=expires_at,
        )
        self.store.put_memory(item)
        self._maybe_upsert_embedding(scope, item)
        self.store.remember(scope, "create_memory", key, payload, item.id)
        self.emit("MemoryItemCreated", item.public(), scope, actor, correlation_id, key, item.id, item.evidence_refs)
        return item

    def get_memory(self, scope: Scope, memory_id: str) -> MemoryItem:
        item = self.store.get_memory(memory_id, scope)
        return self._refresh_expired_working(scope, [item])[0]

    def list_memories(
        self,
        scope: Scope,
        *,
        state: str | None = None,
        kind: str | None = None,
        pinned: bool | None = None,
        q: str | None = None,
    ) -> list[MemoryItem]:
        items = self._refresh_expired_working(scope, self.store.list_memory(scope))
        if state:
            try:
                wanted = MemoryState(state)
            except ValueError as exc:
                raise ValidationError("invalid memory state filter") from exc
            items = [item for item in items if item.state == wanted]
        if kind:
            try:
                wanted_kind = MemoryKind(kind)
            except ValueError as exc:
                raise ValidationError("invalid memory kind filter") from exc
            items = [item for item in items if item.kind == wanted_kind]
        if pinned is not None:
            items = [item for item in items if item.pinned is pinned]
        if q and q.strip():
            terms = tokenize(q)
            items = [
                item
                for item in items
                if terms & tokenize(" ".join([item.title, item.body, *item.tags]))
            ]
        return items

    def update_memory(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        memory_id: str,
        payload: dict[str, Any],
    ) -> MemoryItem:
        self._require_key(key)
        payload = sanitize(payload)
        command_payload = {"memory_id": memory_id, **payload}
        prior = self.store.idempotent(scope, "update_memory", key, command_payload)
        if prior:
            return self.store.get_memory(prior, scope)
        item = self.store.get_memory(memory_id, scope)
        expected_version = payload.get("expected_version")
        if expected_version is not None:
            if not isinstance(expected_version, int) or expected_version < 1:
                raise ValidationError("expected_version must be a positive integer")
            if item.version != expected_version:
                raise ConflictError("memory item version does not match")
        if "title" in payload:
            title = str(payload.get("title") or "").strip()
            if not title:
                raise ValidationError("title is required")
            item.title = title
        if "body" in payload:
            body = str(payload.get("body") or "").strip()
            if not body:
                raise ValidationError("body is required")
            item.body = body
        if "tags" in payload:
            if not isinstance(payload["tags"], list):
                raise ValidationError("tags must be a list")
            item.tags = sorted({str(tag).strip() for tag in payload["tags"] if str(tag).strip()})
        if "confidence" in payload:
            confidence = float(payload["confidence"])
            if confidence < 0 or confidence > 1:
                raise ValidationError("confidence must be between 0 and 1")
            item.confidence = confidence
        if "pinned" in payload:
            item.pinned = bool(payload["pinned"])
        if "expires_at" in payload:
            expires_at = normalize_optional_timestamp(payload.get("expires_at"), "expires_at")
            if expires_at is not None and item.kind != MemoryKind.WORKING:
                raise ValidationError("expires_at is only valid for working memory")
            item.expires_at = expires_at
        item.updated_at = now()
        item.version += 1
        self.store.put_memory(item)
        self._maybe_upsert_embedding(scope, item)
        self.store.remember(scope, "update_memory", key, command_payload, item.id)
        self.emit("MemoryItemUpdated", item.public(), scope, actor, correlation_id, key, item.id, item.evidence_refs)
        return item

    def promote_memory(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        memory_ids: list[str],
        reason: str,
    ) -> list[MemoryItem]:
        """Promote items into long-term semantic memory (human 'keep this')."""
        self._require_key(key)
        payload = {"memory_ids": memory_ids, "reason": sanitize(reason)}
        prior = self.store.idempotent(scope, "promote_memory", key, payload)
        if prior:
            return [self.store.get_memory(memory_id, scope) for memory_id in prior.split(",") if memory_id]
        if not memory_ids:
            raise ValidationError("memory_ids are required")
        if not str(reason or "").strip():
            raise ValidationError("reason is required")
        promoted: list[MemoryItem] = []
        timestamp = now()
        for memory_id in memory_ids:
            item = self.store.get_memory(memory_id, scope)
            item.promote_long_term(timestamp, payload["reason"])
            self.store.put_memory(item)
            self._maybe_upsert_embedding(scope, item)
            promoted.append(item)
        joined = ",".join(item.id for item in promoted)
        self.store.remember(scope, "promote_memory", key, payload, joined)
        self.emit(
            "MemoryPromotedToLongTerm",
            {"memory_ids": [item.id for item in promoted], "reason": reason},
            scope,
            actor,
            correlation_id,
            key,
            joined,
            [],
        )
        return promoted

    def deprecate_memory(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        memory_ids: list[str],
        reason: str,
    ) -> list[MemoryItem]:
        """Soft-forget items so they leave default ContextBundles."""
        self._require_key(key)
        payload = {"memory_ids": memory_ids, "reason": sanitize(reason)}
        prior = self.store.idempotent(scope, "deprecate_memory", key, payload)
        if prior:
            return [self.store.get_memory(memory_id, scope) for memory_id in prior.split(",") if memory_id]
        if not memory_ids:
            raise ValidationError("memory_ids are required")
        if not str(reason or "").strip():
            raise ValidationError("reason is required")
        forgotten: list[MemoryItem] = []
        timestamp = now()
        for memory_id in memory_ids:
            item = self.store.get_memory(memory_id, scope)
            item.deprecate(timestamp, payload["reason"])
            self.store.put_memory(item)
            if self.embedding_store is not None:
                try:
                    self.delete_memory_embedding(scope, memory_id)
                except Exception:  # noqa: BLE001 — forget remains durable without embeddings
                    pass
            forgotten.append(item)
        joined = ",".join(item.id for item in forgotten)
        self.store.remember(scope, "deprecate_memory", key, payload, joined)
        self.emit(
            "MemoryItemDeprecated",
            {"memory_ids": [item.id for item in forgotten], "reason": reason},
            scope,
            actor,
            correlation_id,
            key,
            joined,
            [],
        )
        return forgotten

    def consolidate_memory(self, scope: Scope, actor: str, correlation_id: str, key: str, memory_ids: list[str], reason: str) -> list[MemoryItem]:
        self._require_key(key)
        payload = {"memory_ids": memory_ids, "reason": sanitize(reason)}
        prior = self.store.idempotent(scope, "consolidate_memory", key, payload)
        if prior:
            return [self.store.get_memory(memory_id, scope) for memory_id in prior.split(",") if memory_id]
        if not memory_ids:
            raise ValidationError("memory_ids are required")
        consolidated: list[MemoryItem] = []
        timestamp = now()
        for memory_id in memory_ids:
            item = self.store.get_memory(memory_id, scope)
            if item.kind == MemoryKind.RESTRICTED:
                continue
            item.activate(timestamp)
            item.tags = sorted(set([*item.tags, "consolidated:" + slug(reason)]))
            self.store.put_memory(item)
            consolidated.append(item)
        if not consolidated:
            raise ValidationError("no eligible memory items to consolidate")
        joined = ",".join(item.id for item in consolidated)
        self.store.remember(scope, "consolidate_memory", key, payload, joined)
        self.emit("MemoryConsolidationCompleted", {"memory_ids": [item.id for item in consolidated], "reason": reason}, scope, actor, correlation_id, key, joined, [])
        return consolidated

    def decay_memory(self, scope: Scope, actor: str, correlation_id: str, key: str, memory_ids: list[str], reason: str) -> list[MemoryItem]:
        self._require_key(key)
        payload = {"memory_ids": memory_ids, "reason": sanitize(reason)}
        prior = self.store.idempotent(scope, "decay_memory", key, payload)
        if prior:
            return [self.store.get_memory(memory_id, scope) for memory_id in prior.split(",") if memory_id]
        if not memory_ids:
            raise ValidationError("memory_ids are required")
        decayed: list[MemoryItem] = []
        timestamp = now()
        for memory_id in memory_ids:
            item = self.store.get_memory(memory_id, scope)
            if item.kind == MemoryKind.RESTRICTED:
                continue
            item.mark_stale(timestamp, payload["reason"])
            self.store.put_memory(item)
            if self.embedding_store is not None:
                try:
                    self.delete_memory_embedding(scope, memory_id)
                except Exception:  # noqa: BLE001 — decay stays durable without embeddings
                    pass
            decayed.append(item)
        if not decayed:
            raise ValidationError("no eligible memory items to decay")
        joined = ",".join(item.id for item in decayed)
        self.store.remember(scope, "decay_memory", key, payload, joined)
        self.emit("MemoryDecayCompleted", {"memory_ids": [item.id for item in decayed], "reason": reason}, scope, actor, correlation_id, key, joined, [])
        return decayed

    def list_stale_memory(self, scope: Scope) -> list[MemoryItem]:
        items = self._refresh_expired_working(scope, self.store.list_memory(scope))
        return [item for item in items if item.state in {MemoryState.STALE, MemoryState.DEPRECATED}]

    def _refresh_expired_working(self, scope: Scope, items: list[MemoryItem]) -> list[MemoryItem]:
        """Lazily forget expired working memory (stale) so TTL behaves without a sweeper."""
        timestamp = now()
        refreshed: list[MemoryItem] = []
        for item in items:
            if (
                item.kind == MemoryKind.WORKING
                and item.is_expired(timestamp)
                and item.state in {MemoryState.ACTIVE, MemoryState.CANDIDATE}
            ):
                item.mark_stale(timestamp, "working_expired")
                self.store.put_memory(item)
                if self.embedding_store is not None:
                    try:
                        self.delete_memory_embedding(scope, item.id)
                    except Exception:  # noqa: BLE001 — expiry remains durable without embeddings
                        pass
            refreshed.append(item)
        return refreshed

    def _validate_memory_payload(self, payload: dict[str, Any]) -> None:
        missing = [field for field in ("kind", "title", "body") if not payload.get(field)]
        if missing:
            raise ValidationError("missing required fields: " + ", ".join(missing))
        try:
            MemoryKind(payload["kind"])
        except ValueError as exc:
            raise ValidationError("invalid memory kind") from exc
        if "state" in payload and payload["state"] is not None:
            try:
                MemoryState(payload["state"])
            except ValueError as exc:
                raise ValidationError("invalid memory state") from exc
        confidence = float(payload.get("confidence", 1.0))
        if confidence < 0 or confidence > 1:
            raise ValidationError("confidence must be between 0 and 1")
        if "expires_at" in payload:
            normalize_optional_timestamp(payload.get("expires_at"), "expires_at")
