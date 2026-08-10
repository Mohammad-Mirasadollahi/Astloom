from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import OUTBOX_SOURCES, RelayConfig
from .postgres_source import PostgresOutboxSource
from .types import OutboxRow, OutboxSource


@dataclass
class RelayBatchResult:
    polled: int = 0
    published: int = 0
    handler_results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class OutboxRelay:
    """Poll configured outbox sources, run handlers, then mark rows published."""

    def __init__(
        self,
        sources: list[OutboxSource],
        handlers: list[Any],
        *,
        batch_size: int = 100,
    ) -> None:
        self.sources = sources
        self.handlers = handlers
        self.batch_size = batch_size

    @classmethod
    def from_config(cls, config: RelayConfig, handlers: list[Any]) -> OutboxRelay:
        wanted = set(config.enabled_sources)
        sources: list[OutboxSource] = []
        for spec in OUTBOX_SOURCES:
            if spec.name not in wanted:
                continue
            sources.append(PostgresOutboxSource(spec, config.database_url))
        return cls(sources, handlers, batch_size=config.batch_size)

    def run_once(self) -> RelayBatchResult:
        result = RelayBatchResult()
        for source in self.sources:
            try:
                rows = source.list_unpublished(self.batch_size)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"{source.name}:list:{exc}")
                continue
            result.polled += len(rows)
            published_ids: list[str] = []
            for row in rows:
                ok = self._dispatch(row, result)
                if ok:
                    published_ids.append(row.mark_key)
            if published_ids:
                try:
                    source.mark_published(published_ids)
                    result.published += len(published_ids)
                except Exception as exc:  # noqa: BLE001
                    result.errors.append(f"{source.name}:mark:{exc}")
        return result

    def _dispatch(self, row: OutboxRow, result: RelayBatchResult) -> bool:
        event = dict(row.payload)
        event.setdefault("event_id", row.event_id)
        event.setdefault("event_type", row.event_type)
        event.setdefault("occurred_at", row.occurred_at)
        all_ok = True
        for handler in self.handlers:
            try:
                outcome = handler.handle(event, source=row.source)
                result.handler_results.append(
                    {
                        "source": row.source,
                        "event_id": row.event_id,
                        "handler": outcome.handler,
                        "ok": outcome.ok,
                        "detail": outcome.detail,
                    }
                )
                if not outcome.ok:
                    all_ok = False
            except Exception as exc:  # noqa: BLE001
                all_ok = False
                result.errors.append(f"{row.source}:{row.event_id}:{handler.name}:{exc}")
                result.handler_results.append(
                    {
                        "source": row.source,
                        "event_id": row.event_id,
                        "handler": getattr(handler, "name", type(handler).__name__),
                        "ok": False,
                        "detail": str(exc),
                    }
                )
        return all_ok

    def close(self) -> None:
        for source in self.sources:
            closer = getattr(source, "close", None)
            if callable(closer):
                closer()
