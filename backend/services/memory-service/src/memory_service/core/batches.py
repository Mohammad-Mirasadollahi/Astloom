"""Work-batch commands."""

from __future__ import annotations

from uuid import uuid4

from .enums import BatchState
from .errors import ValidationError
from .helpers import now, sanitize
from .models import Scope, WorkBatch


class BatchCommands:
    def open_batch(self, scope: Scope, actor: str, correlation_id: str, key: str, title: str, item_refs: list[str], deferred_actions: list[str]) -> WorkBatch:
        self._require_key(key)
        if not title.strip():
            raise ValidationError("title is required")
        payload = {"title": sanitize(title), "item_refs": sorted(set(item_refs)), "deferred_actions": sorted(set(deferred_actions))}
        prior = self.store.idempotent(scope, "open_batch", key, payload)
        if prior:
            return self.store.get_batch(prior, scope)
        timestamp = now()
        batch = WorkBatch(str(uuid4()), scope, actor, correlation_id, payload["title"], payload["item_refs"], payload["deferred_actions"], BatchState.OPEN, timestamp, timestamp)
        self.store.put_batch(batch)
        self.store.remember(scope, "open_batch", key, payload, batch.id)
        return batch

    def mark_batch_ready(self, scope: Scope, actor: str, correlation_id: str, key: str, batch_id: str, reason: str) -> WorkBatch:
        self._require_key(key)
        payload = {"batch_id": batch_id, "reason": sanitize(reason)}
        prior = self.store.idempotent(scope, "mark_batch_ready", key, payload)
        if prior:
            return self.store.get_batch(prior, scope)
        batch = self.store.get_batch(batch_id, scope)
        batch.mark_ready(now(), payload["reason"])
        self.store.put_batch(batch)
        self.store.remember(scope, "mark_batch_ready", key, payload, batch.id)
        self.emit("BatchReadyForConsolidation", batch.public(), scope, actor, correlation_id, key, batch.id, batch.item_refs)
        return batch
