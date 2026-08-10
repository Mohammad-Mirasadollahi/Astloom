"""Persistence ports for this service (Phase C DI hygiene).

The ``Store`` protocol lives in ``core.protocols`` (re-exported from
``adapter_service.core``). Concrete adapters (``postgres_store.py``) must be
constructed only from ``bootstrap.py`` — not from API handlers or domain helpers.
"""

from __future__ import annotations

from .core import Store

__all__ = ["Store"]
