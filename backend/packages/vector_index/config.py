"""ANN accelerator env config (ASTLOOM_RAG_ANN_* / ASTLOOM_TURBOVEC_*)."""

from __future__ import annotations

import os
from dataclasses import dataclass

_ALLOWED_ACCELERATORS = frozenset({"off", "turbovec"})
_ALLOWED_BIT_WIDTHS = frozenset({2, 3, 4})
_ALLOWED_SYNC_MODES = frozenset({"sync_on_write", "async_job"})


@dataclass(frozen=True)
class AnnAcceleratorConfig:
    """Resolved deployment flags for optional ANN acceleration."""

    accelerator: str = "off"
    bit_width: int = 4
    snapshot_uri: str = ""
    sync_mode: str = "sync_on_write"

    @property
    def enabled(self) -> bool:
        return self.accelerator == "turbovec"

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> AnnAcceleratorConfig:
        env = environ if environ is not None else os.environ
        raw_acc = str(env.get("ASTLOOM_RAG_ANN_ACCELERATOR", "off")).strip().lower() or "off"
        if raw_acc not in _ALLOWED_ACCELERATORS:
            raise ValueError(
                "ASTLOOM_RAG_ANN_ACCELERATOR must be 'off' or 'turbovec', "
                f"got {raw_acc!r}"
            )
        raw_bw = str(env.get("ASTLOOM_TURBOVEC_BIT_WIDTH", "4")).strip() or "4"
        try:
            bit_width = int(raw_bw)
        except ValueError as exc:
            raise ValueError("ASTLOOM_TURBOVEC_BIT_WIDTH must be 2, 3, or 4") from exc
        if bit_width not in _ALLOWED_BIT_WIDTHS:
            raise ValueError("ASTLOOM_TURBOVEC_BIT_WIDTH must be 2, 3, or 4")
        snapshot_uri = str(env.get("ASTLOOM_TURBOVEC_SNAPSHOT_URI", "")).strip()
        sync_mode = str(env.get("ASTLOOM_TURBOVEC_SYNC_MODE", "sync_on_write")).strip().lower() or "sync_on_write"
        if sync_mode not in _ALLOWED_SYNC_MODES:
            raise ValueError(
                "ASTLOOM_TURBOVEC_SYNC_MODE must be 'sync_on_write' or 'async_job', "
                f"got {sync_mode!r}"
            )
        return cls(
            accelerator=raw_acc,
            bit_width=bit_width,
            snapshot_uri=snapshot_uri,
            sync_mode=sync_mode,
        )


def ann_accelerator_enabled(environ: dict[str, str] | None = None) -> bool:
    return AnnAcceleratorConfig.from_environment(environ).enabled


def load_accelerator_config(environ: dict[str, str] | None = None) -> AnnAcceleratorConfig:
    """Alias for service hooks / ADR naming."""
    return AnnAcceleratorConfig.from_environment(environ)
