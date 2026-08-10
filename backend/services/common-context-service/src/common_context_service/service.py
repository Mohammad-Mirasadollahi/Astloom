"""Composition root for CommonContextService use-case mixins."""

from __future__ import annotations

from .ports import Store
from .service_export import ExportMixin
from .service_guidance import GuidanceMixin
from .service_items import ItemsMixin
from .service_seed import SeedMixin


class CommonContextService(ItemsMixin, GuidanceMixin, SeedMixin, ExportMixin):
    """Governed common-context items + Agent Workspace Guidance projection."""

    def __init__(self, store: Store):
        self.store = store
