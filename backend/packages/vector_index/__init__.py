"""Optional ANN acceleration port (VectorIndexPort) for Astloom RAG."""

from __future__ import annotations

from typing import Any

from .config import AnnAcceleratorConfig, ann_accelerator_enabled, load_accelerator_config
from .factory import try_build_accelerator
from .id_map import (
    ENTITY_ID_MAP_TABLE_SQL,
    InMemoryEntityIdMap,
    PostgresEntityIdMap,
    entity_ref_to_uint64,
    stable_hash_uint64,
)
from .in_memory import InMemoryVectorIndex
from .metrics import (
    AcceleratorMetrics,
    InstrumentedVectorIndex,
    get_accelerator_metrics,
    reset_accelerator_metrics,
)
from .port import VectorIndexPort
from .turbovec_adapter import (
    TurboVecIndexAdapter,
    TurboVecUnavailable,
    turbovec_available,
    turbovec_importable,
)

__all__ = [
    "ENTITY_ID_MAP_TABLE_SQL",
    "AcceleratorMetrics",
    "AnnAcceleratorConfig",
    "InMemoryEntityIdMap",
    "InMemoryVectorIndex",
    "InstrumentedVectorIndex",
    "PostgresEntityIdMap",
    "PromotionGateResult",
    "TurboVecIndexAdapter",
    "TurboVecUnavailable",
    "VectorIndexPort",
    "ann_accelerator_enabled",
    "entity_ref_to_uint64",
    "get_accelerator_metrics",
    "load_accelerator_config",
    "reset_accelerator_metrics",
    "run_promotion_gate",
    "stable_hash_uint64",
    "try_build_accelerator",
    "turbovec_available",
    "turbovec_importable",
]


def __getattr__(name: str) -> Any:
    if name in {"PromotionGateResult", "run_promotion_gate"}:
        from . import promotion_gate

        return getattr(promotion_gate, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name}")
