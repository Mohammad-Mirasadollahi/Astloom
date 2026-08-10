from __future__ import annotations

from typing import Any

from .types import OutboxRow, utc_now


class InMemoryOutboxSource:
    """Test double that mirrors the postgres unpublished / mark_published contract."""

    def __init__(self, name: str, events: list[dict[str, Any]] | None = None) -> None:
        self.name = name
        self._rows: list[dict[str, Any]] = []
        self._seq = 0
        for event in events or []:
            self.append(event)

    def append(self, event: dict[str, Any]) -> None:
        self._seq += 1
        event_id = str(event.get("event_id") or f"{self.name}-{self._seq}")
        self._rows.append(
            {
                "mark_key": event_id,
                "event_id": event_id,
                "event_type": str(event.get("event_type") or ""),
                "payload": dict(event),
                "occurred_at": str(event.get("occurred_at") or utc_now()),
                "published_at": None,
            }
        )

    def list_unpublished(self, limit: int) -> list[OutboxRow]:
        rows = [row for row in self._rows if row["published_at"] is None]
        rows.sort(key=lambda row: (row["occurred_at"], row["event_id"]))
        selected = rows[:limit]
        return [
            OutboxRow(
                source=self.name,
                event_id=row["event_id"],
                event_type=row["event_type"],
                payload=dict(row["payload"]),
                occurred_at=row["occurred_at"],
                mark_key=row["mark_key"],
            )
            for row in selected
        ]

    def mark_published(self, mark_keys: list[str]) -> None:
        wanted = set(mark_keys)
        stamp = utc_now()
        for row in self._rows:
            if row["mark_key"] in wanted:
                row["published_at"] = stamp

    def close(self) -> None:
        return None
