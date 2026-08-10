from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class OutboxRow:
    source: str
    event_id: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: str
    mark_key: str


class OutboxSource(Protocol):
    name: str

    def list_unpublished(self, limit: int) -> list[OutboxRow]: ...

    def mark_published(self, mark_keys: list[str]) -> None: ...

    def close(self) -> None: ...


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
