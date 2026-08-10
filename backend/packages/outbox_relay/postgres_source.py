from __future__ import annotations

from typing import Any

from .config import OutboxSourceSpec
from .types import OutboxRow, utc_now


class PostgresOutboxSource:
    """Reads/marks rows in `<schema>.outbox` for either event_id or seq DDL shapes."""

    def __init__(self, spec: OutboxSourceSpec, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("outbox relay database URL must use PostgreSQL")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for the outbox relay") from exc
        normalized = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self.spec = spec
        self.name = spec.name
        self.schema = spec.schema
        self._connection = psycopg.connect(normalized, autocommit=True, row_factory=dict_row)

    def list_unpublished(self, limit: int) -> list[OutboxRow]:
        if self.spec.shape == "event_id":
            return self._list_event_id(limit)
        return self._list_seq(limit)

    def mark_published(self, mark_keys: list[str]) -> None:
        if not mark_keys:
            return
        if self.spec.shape == "event_id":
            sql = f"""
                UPDATE {self.schema}.outbox
                SET published_at = %s
                WHERE event_id = ANY(%s) AND published_at IS NULL
            """
            params: tuple[Any, ...] = (utc_now(), list(mark_keys))
        else:
            sql = f"""
                UPDATE {self.schema}.outbox
                SET published_at = %s
                WHERE seq = ANY(%s::bigint[]) AND published_at IS NULL
            """
            params = (utc_now(), [int(key) for key in mark_keys])
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)

    def close(self) -> None:
        self._connection.close()

    def _list_event_id(self, limit: int) -> list[OutboxRow]:
        time_col = self.spec.time_column
        sql = f"""
            SELECT event_id, event_type, payload, {time_col} AS occurred_at
            FROM {self.schema}.outbox
            WHERE published_at IS NULL
            ORDER BY {time_col}, event_id
            LIMIT %s
        """
        with self._connection.cursor() as cursor:
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()
        result: list[OutboxRow] = []
        for row in rows:
            payload = _as_dict(row["payload"])
            event_id = str(row["event_id"])
            result.append(
                OutboxRow(
                    source=self.name,
                    event_id=event_id,
                    event_type=str(row["event_type"] or payload.get("event_type") or ""),
                    payload=payload,
                    occurred_at=_as_iso(row["occurred_at"]),
                    mark_key=event_id,
                )
            )
        return result

    def _list_seq(self, limit: int) -> list[OutboxRow]:
        sql = f"""
            SELECT seq, payload, occurred_at
            FROM {self.schema}.outbox
            WHERE published_at IS NULL
            ORDER BY occurred_at, seq
            LIMIT %s
        """
        with self._connection.cursor() as cursor:
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()
        result: list[OutboxRow] = []
        for row in rows:
            payload = _as_dict(row["payload"])
            seq = str(row["seq"])
            event_id = str(payload.get("event_id") or f"{self.name}-seq-{seq}")
            event_type = str(payload.get("event_type") or "")
            # Seq tables store the envelope (or a thin dict) in payload only.
            envelope = dict(payload)
            envelope.setdefault("event_id", event_id)
            envelope.setdefault("event_type", event_type)
            envelope.setdefault("occurred_at", _as_iso(row["occurred_at"]))
            result.append(
                OutboxRow(
                    source=self.name,
                    event_id=event_id,
                    event_type=event_type,
                    payload=envelope,
                    occurred_at=_as_iso(row["occurred_at"]),
                    mark_key=seq,
                )
            )
        return result


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return dict(value)


def _as_iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
