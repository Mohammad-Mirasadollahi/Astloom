"""
Module contract: Astloom native context compression (clean-room, Headroom-inspired).

Role: Shrink bulky JSON/text for LLM/MCP turns; store originals under scoped TTL handles.
SoT/invariants: In-process store only; retrieve requires matching scope; no cloud I/O.
Allowed failures: below-threshold skip; JSON parse miss → text path; expired/missing handle.
Forbidden: LiteLLM bypass; cross-tenant retrieve; treating IDE toolstack as product SoT.
"""

from __future__ import annotations

from .compress import WATERMARK, CompressResult, compress_payload
from .metrics import reset as reset_metrics
from .metrics import snapshot as metrics_snapshot
from .store import ContextCompressionStore, default_store

__all__ = [
    "WATERMARK",
    "CompressResult",
    "ContextCompressionStore",
    "compress_payload",
    "default_store",
    "metrics_snapshot",
    "reset_metrics",
]
