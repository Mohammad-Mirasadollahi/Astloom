"""Composition-root helper: optional TurboVec accelerator + entity id map.

Role: Single place services call to bind VectorIndexPort when env enables turbovec.
Source of truth: AnnAcceleratorConfig + TurboVecIndexAdapter.try_create (fail-open).
Allowed: return (None, None) when off/unavailable/invalid dim; durable Postgres id map when URL+table set;
  load local snapshot when ASTLOOM_TURBOVEC_SNAPSHOT_URI is set; wrap with process metrics.
Forbidden: raising into service boot for missing optional wheel; using hash id map when DB map is configured.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .config import AnnAcceleratorConfig
from .id_map import InMemoryEntityIdMap, PostgresEntityIdMap
from .metrics import InstrumentedVectorIndex, get_accelerator_metrics
from .turbovec_adapter import TurboVecIndexAdapter

logger = logging.getLogger(__name__)


def try_build_accelerator(
    *,
    dim: int,
    environ: dict[str, str] | None = None,
    database_url: str | None = None,
    id_map_table: str | None = None,
) -> tuple[Any | None, Any | None]:
    """Return (adapter, id_map) or (None, None) when accelerator is off/unavailable."""
    env = environ if environ is not None else os.environ
    metrics = get_accelerator_metrics()
    try:
        cfg = AnnAcceleratorConfig.from_environment(env)
    except ValueError:
        return None, None
    if not cfg.enabled:
        return None, None
    if dim <= 0 or dim % 8 != 0 or dim > 65536:
        return None, None
    adapter = TurboVecIndexAdapter.try_create(dim=dim, bit_width=cfg.bit_width)
    if adapter is None:
        return None, None
    if cfg.snapshot_uri:
        try:
            adapter.load_snapshot(cfg.snapshot_uri)
            metrics.record_snapshot_load(ok=True)
        except Exception as exc:
            metrics.record_snapshot_load(ok=False)
            logger.warning("turbovec snapshot load failed; starting empty replica: %s", exc)
    wrapped: Any = InstrumentedVectorIndex(
        adapter,
        metrics=metrics,
        snapshot_uri=cfg.snapshot_uri,
    )
    table = (id_map_table or str(env.get("ASTLOOM_TURBOVEC_ID_MAP_TABLE", "")).strip() or "")
    url = (database_url or str(env.get("ASTLOOM_TURBOVEC_ID_MAP_DATABASE_URL", "")).strip() or "")
    if url and table:
        try:
            return wrapped, PostgresEntityIdMap(url, table=table)
        except Exception:
            return wrapped, InMemoryEntityIdMap()
    return wrapped, InMemoryEntityIdMap()
