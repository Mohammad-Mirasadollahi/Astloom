"""Ingest use cases (modular)."""

from __future__ import annotations

from ..support import GraphServiceSupport
from .file_ingest import FileIngestMixin
from .human_docs import HumanDocIngestMixin
from .pushed import PushedIngestMixin
from .repo_ingest import RepoIngestMixin
from .runtime_traces import RuntimeTraceIngestMixin
from .sync import SyncMixin


class IngestUseCases(
    FileIngestMixin,
    HumanDocIngestMixin,
    PushedIngestMixin,
    RepoIngestMixin,
    RuntimeTraceIngestMixin,
    SyncMixin,
    GraphServiceSupport,
):
    """Application ingest surface composed from focused mixins."""

    pass

__all__ = [
    "IngestUseCases",
    "FileIngestMixin",
    "HumanDocIngestMixin",
    "PushedIngestMixin",
    "RepoIngestMixin",
    "RuntimeTraceIngestMixin",
    "SyncMixin",
]
